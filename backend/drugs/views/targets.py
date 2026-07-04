import logging
import re

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from config.services.mongo import get_db
from config.services.neo4j_service import get_driver
from config.services.uniprot_service import get_uniprot_entry
from config.services.kegg_service import pathways_for_targets
from config.services.string_service import indirect_neighbors, network_image_url, TAXON_HUMAN
from ._helpers import _is_admin

log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mongo_targets_ready() -> bool:
    """True si la colección targets de MongoDB tiene documentos."""
    try:
        return get_db().targets.estimated_document_count() > 0
    except Exception as e:
        log.debug('_mongo_targets_ready: MongoDB no disponible: %s', e)
        return False


def _serialize_target(doc: dict) -> dict:
    """Convierte un documento MongoDB al formato que espera el frontend."""
    return {
        'id':                  str(doc.get('_id') or ''),
        'name':                doc.get('name', ''),
        'gene_name':           doc.get('gene_name', ''),
        'uniprot_id':          doc.get('uniprot_id', ''),
        'organism':            doc.get('organism', ''),
        'cellular_location':   doc.get('cellular_location', ''),
        'chromosome_location': doc.get('chromosome_location', ''),
        'known_action':        doc.get('known_action', ''),
        'drug_count':          doc.get('drug_count', 0),
    }


def _serialize_target_detail(doc: dict) -> dict:
    """Versión completa con drug_refs."""
    base = _serialize_target(doc)
    base['drugs'] = [
        {
            'drugbank_id': d.get('drugbank_id', ''),
            'drug_name':   d.get('drug_name', ''),
            'rel_type':    d.get('rel_type', ''),
        }
        for d in doc.get('drug_refs', [])
        if d.get('drugbank_id')
    ]
    return base


# ── Neo4j fallback helpers ────────────────────────────────────────────────────

def _neo4j_build_where(search: str, organism: str) -> tuple[str, dict]:
    conditions = []
    params: dict = {}
    if search:
        conditions.append(
            "(toLower(t.name) CONTAINS toLower($search) OR "
            "toLower(coalesce(t.gene_name, '')) CONTAINS toLower($search) OR "
            "toLower(coalesce(t.uniprot_id, '')) CONTAINS toLower($search))"
        )
        params['search'] = search
    if organism:
        conditions.append("t.organism = $organism")
        params['organism'] = organism
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    return where, params


def _neo4j_list(search: str, organism: str, skip: int, per_page: int) -> tuple[int, list]:
    driver = get_driver()
    where, params = _neo4j_build_where(search, organism)
    with driver.session() as session:
        total = session.run(
            f"MATCH (t:Target) {where} RETURN count(t) AS total", **params
        ).single()['total']
        rows = session.run(
            f"""
            MATCH (t:Target) {where}
            WITH t ORDER BY t.name SKIP $skip LIMIT $limit
            OPTIONAL MATCH (d:Drug)-[]->(t)
            WITH t, count(DISTINCT d) AS drug_count
            RETURN
              coalesce(t.drugbank_target_id,'') AS id,
              coalesce(t.name,'')               AS name,
              coalesce(t.gene_name,'')           AS gene_name,
              coalesce(t.uniprot_id,'')          AS uniprot_id,
              coalesce(t.organism,'')            AS organism,
              coalesce(t.cellular_location,'')   AS cellular_location,
              coalesce(t.chromosome_location,'') AS chromosome_location,
              coalesce(t.known_action,'')        AS known_action,
              drug_count
            ORDER BY name
            """,
            skip=skip, limit=per_page, **params
        )
        return total, [dict(r) for r in rows]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def targets_list_view(request):
    if request.method == 'GET':
        search   = request.query_params.get('search', '').strip()
        organism = request.query_params.get('organism', '').strip()
        try:
            page     = max(1, int(request.query_params.get('page', 1)))
            per_page = min(50, max(1, int(request.query_params.get('per_page', 20))))
        except ValueError:
            page, per_page = 1, 20
        skip = (page - 1) * per_page

        # ── MongoDB path ──────────────────────────────────────────────────────
        if _mongo_targets_ready():
            db    = get_db()
            query: dict = {}
            if search:
                pattern = re.compile(re.escape(search), re.IGNORECASE)
                query['$or'] = [
                    {'name':      pattern},
                    {'gene_name': pattern},
                    {'uniprot_id':pattern},
                ]
            if organism:
                query['organism'] = organism
            total   = db.targets.count_documents(query)
            cursor  = db.targets.find(
                query,
                {'_id': 1, 'name': 1, 'gene_name': 1, 'uniprot_id': 1, 'organism': 1,
                 'cellular_location': 1, 'chromosome_location': 1, 'known_action': 1,
                 'drug_count': 1},
            ).sort('name', 1).skip(skip).limit(per_page)
            results = [_serialize_target(doc) for doc in cursor]
            return Response({
                'page': page, 'per_page': per_page, 'total': total,
                'has_next': (page * per_page) < total,
                'has_prev': page > 1,
                'results': results,
            })

        # ── Neo4j fallback ────────────────────────────────────────────────────
        total, results = _neo4j_list(search, organism, skip, per_page)
        return Response({
            'page': page, 'per_page': per_page, 'total': total,
            'has_next': (page * per_page) < total,
            'has_prev': page > 1,
            'results': results,
        })

    # POST — solo admin
    if not _is_admin(request):
        return Response({'error': 'Solo administradores.'}, status=status.HTTP_403_FORBIDDEN)

    data      = request.data
    name      = (data.get('name') or '').strip()
    target_id = (data.get('drugbank_target_id') or '').strip()
    if not name or not target_id:
        return Response(
            {'error': 'name y drugbank_target_id son obligatorios.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with get_driver().session() as session:
        if session.run(
            "MATCH (t:Target {drugbank_target_id: $tid}) RETURN t LIMIT 1", tid=target_id
        ).single():
            return Response(
                {'error': f'Ya existe una diana con ID {target_id}.'},
                status=status.HTTP_409_CONFLICT,
            )
        session.run(
            """
            CREATE (t:Target {
                drugbank_target_id: $tid,
                name: $name,
                gene_name: $gene_name,
                organism: $organism,
                uniprot_id: $uniprot_id,
                cellular_location: $cellular_location,
                known_action: $known_action
            })
            """,
            tid=target_id,
            name=name,
            gene_name=data.get('gene_name', ''),
            organism=data.get('organism', ''),
            uniprot_id=data.get('uniprot_id', ''),
            cellular_location=data.get('cellular_location', ''),
            known_action=data.get('known_action', ''),
        )

    if _mongo_targets_ready():
        try:
            get_db().targets.insert_one({
                '_id':                 target_id,
                'name':                name,
                'gene_name':           data.get('gene_name', ''),
                'organism':            data.get('organism', ''),
                'uniprot_id':          data.get('uniprot_id', ''),
                'cellular_location':   data.get('cellular_location', ''),
                'chromosome_location': '',
                'known_action':        data.get('known_action', ''),
                'drug_count':          0,
                'drug_refs':           [],
            })
        except Exception as e:
            log.warning('No se pudo crear nodo Neo4j para target %s: %s', target_id, e)

    return Response({'ok': True, 'id': target_id}, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def target_detail_view(request, target_id: str):
    if request.method == 'GET':
        # ── MongoDB path ──────────────────────────────────────────────────────
        if _mongo_targets_ready():
            doc = get_db().targets.find_one(
                {'_id': target_id},
                {'_id': 1, 'name': 1, 'gene_name': 1, 'uniprot_id': 1, 'organism': 1,
                 'cellular_location': 1, 'chromosome_location': 1, 'known_action': 1,
                 'drug_count': 1, 'drug_refs': 1},
            )
            if not doc:
                return Response({'error': 'Target no encontrado'}, status=status.HTTP_404_NOT_FOUND)
            return Response(_serialize_target_detail(doc))

        # ── Neo4j fallback ────────────────────────────────────────────────────
        driver = get_driver()
        with driver.session() as session:
            res = session.run(
                """
                MATCH (t:Target {drugbank_target_id: $target_id})
                OPTIONAL MATCH (d:Drug)-[r]->(t)
                WITH t, collect(DISTINCT {
                    drugbank_id: coalesce(d.drugbank_id, ''),
                    drug_name:   coalesce(d.name, ''),
                    rel_type:    type(r)
                }) AS drugs
                RETURN
                  coalesce(t.drugbank_target_id,'') AS id,
                  coalesce(t.name,'')               AS name,
                  coalesce(t.gene_name,'')           AS gene_name,
                  coalesce(t.uniprot_id,'')          AS uniprot_id,
                  coalesce(t.organism,'')            AS organism,
                  coalesce(t.cellular_location,'')   AS cellular_location,
                  coalesce(t.chromosome_location,'') AS chromosome_location,
                  coalesce(t.known_action,'')        AS known_action,
                  drugs
                """,
                target_id=target_id
            )
            record = res.single()

        if not record:
            return Response({'error': 'Target no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        data = dict(record)
        data['drug_count'] = len([d for d in data['drugs'] if d.get('drugbank_id')])
        return Response(data)

    # PATCH / DELETE — solo admin
    if not _is_admin(request):
        return Response({'error': 'Solo administradores.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'PATCH':
        allowed = {'name', 'gene_name', 'organism', 'cellular_location', 'known_action'}
        data = {k: v for k, v in request.data.items() if k in allowed}
        if not data:
            return Response({'error': 'Sin campos válidos para actualizar.'}, status=status.HTTP_400_BAD_REQUEST)

        # Actualiza en Neo4j
        set_clause = ', '.join(f't.{k} = ${k}' for k in data)
        with get_driver().session() as session:
            session.run(
                f"MATCH (t:Target {{drugbank_target_id: $tid}}) SET {set_clause}",
                tid=target_id, **data
            )

        # Actualiza en MongoDB si está disponible
        if _mongo_targets_ready():
            get_db().targets.update_one({'_id': target_id}, {'$set': data})

        return Response({'ok': True})

    # DELETE
    with get_driver().session() as session:
        session.run(
            "MATCH (t:Target {drugbank_target_id: $tid}) DETACH DELETE t",
            tid=target_id
        )
    if _mongo_targets_ready():
        get_db().targets.delete_one({'_id': target_id})

    return Response({'ok': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def target_uniprot_view(request, target_id: str):
    """Devuelve datos de UniProt para un target (desde MongoDB o API)."""
    uniprot_id = ''

    # Intentar obtener uniprot_id + datos embebidos desde MongoDB
    if _mongo_targets_ready():
        doc = get_db().targets.find_one({'_id': target_id}, {'uniprot_id': 1, 'uniprot': 1})
        if not doc:
            return Response({'error': 'Target no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        uniprot_id = doc.get('uniprot_id', '')
        # Si ya está embebido en el documento, devuelve directamente
        if doc.get('uniprot'):
            return Response(doc['uniprot'])
    else:
        # Fallback a Neo4j
        driver = get_driver()
        with driver.session() as session:
            res = session.run(
                "MATCH (t:Target {drugbank_target_id: $id}) "
                "RETURN coalesce(t.uniprot_id,'') AS uniprot_id",
                id=target_id
            )
            record = res.single()
        if not record:
            return Response({'error': 'Target no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        uniprot_id = record['uniprot_id']

    if not uniprot_id:
        return Response({'error': 'Este target no tiene UniProt ID registrado'},
                        status=status.HTTP_404_NOT_FOUND)

    parsed = get_uniprot_entry(uniprot_id)
    if not parsed:
        return Response({'error': f'No se pudo obtener datos de UniProt para {uniprot_id}'},
                        status=status.HTTP_502_BAD_GATEWAY)

    # Actualizar el documento MongoDB con los datos recién obtenidos
    if _mongo_targets_ready():
        try:
            get_db().targets.update_one({'_id': target_id}, {'$set': {'uniprot': parsed}})
        except Exception as exc:
            log.debug("No se pudo actualizar uniprot en targets: %s", exc)

    return Response(parsed)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def drugs_by_target_view(request):
    """GET /api/drugs/targets/by-gene/?q=<name>"""
    query = request.query_params.get('q', '').strip()
    if not query:
        return Response({'error': 'Parámetro q requerido'}, status=status.HTTP_400_BAD_REQUEST)

    driver = get_driver()
    with driver.session() as session:
        res = session.run(
            """
            MATCH (d:Drug)-[r]->(t:Target)
            WHERE toLower(t.name) CONTAINS toLower($query)
               OR toLower(coalesce(t.gene_name,'')) CONTAINS toLower($query)
               OR toLower(coalesce(t.uniprot_id,'')) CONTAINS toLower($query)
            WITH d, collect(DISTINCT {
                target_name: t.name,
                gene_name:   coalesce(t.gene_name,''),
                uniprot_id:  coalesce(t.uniprot_id,''),
                rel_type:    type(r)
            }) AS targets_matched
            RETURN d.drugbank_id AS drugbank_id, d.name AS name, targets_matched
            ORDER BY d.name LIMIT 80
            """,
            query=query
        )
        results = [dict(r) for r in res]

    return Response({'query': query, 'total': len(results), 'results': results})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def target_pathways_view(request, target_id: str):
    """GET /api/drugs/targets/<target_id>/pathways/"""
    # Obtener metadatos del target
    target_meta = None
    if _mongo_targets_ready():
        doc = get_db().targets.find_one(
            {'_id': target_id},
            {'name': 1, 'gene_name': 1, 'uniprot_id': 1, 'organism': 1}
        )
        if doc:
            target_meta = {
                'name':       doc.get('name', ''),
                'gene_name':  doc.get('gene_name', ''),
                'uniprot_id': doc.get('uniprot_id', ''),
                'organism':   doc.get('organism', ''),
            }

    if not target_meta:
        driver = get_driver()
        with driver.session() as session:
            res = session.run(
                """
                MATCH (t:Target {drugbank_target_id: $id})
                RETURN
                  coalesce(t.name,'')       AS name,
                  coalesce(t.gene_name,'')  AS gene_name,
                  coalesce(t.uniprot_id,'') AS uniprot_id,
                  coalesce(t.organism,'')   AS organism
                """,
                id=target_id
            )
            record = res.single()
        if not record:
            return Response({'error': 'Target no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        target_meta = dict(record)

    notes = []

    # ── KEGG ──────────────────────────────────────────────────────────────────
    pathways = None
    if target_meta['uniprot_id']:
        try:
            pathways = pathways_for_targets([{
                'uniprot_id': target_meta['uniprot_id'],
                'name':       target_meta['name'],
                'gene_name':  target_meta['gene_name'],
            }])
        except Exception as exc:
            log.error("KEGG error for target %s: %s", target_id, exc)
            notes.append('No se pudieron obtener las rutas de KEGG.')
    else:
        notes.append('Target sin UniProt ID — no se pueden obtener rutas KEGG.')

    # ── STRING PPI ────────────────────────────────────────────────────────────
    indirect = None
    gene = target_meta['gene_name'] or target_meta['uniprot_id']
    if gene:
        try:
            score    = int(request.query_params.get('score', 400))
            indirect = indirect_neighbors([gene], species=TAXON_HUMAN, required_score=score)
            indirect['network_image_url'] = network_image_url(
                [gene], species=TAXON_HUMAN, required_score=score
            )
        except Exception as exc:
            log.error("STRING error for target %s: %s", target_id, exc)
            notes.append('No se pudo obtener la red PPI de STRING.')

    return Response({
        'target':   target_meta,
        'pathways': pathways,
        'indirect': indirect,
        'notes':    notes,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def kegg_gene_pathways_view(request):
    """GET /api/drugs/targets/kegg-gene/?gene=TP53"""
    gene = request.query_params.get('gene', '').strip()
    if not gene:
        return Response({'error': 'Parámetro gene requerido'}, status=status.HTTP_400_BAD_REQUEST)

    from config.services.kegg_service import kegg_gene_to_pathways, pathway_names, gene_symbol_to_kegg_id
    try:
        # KEGG link/pathway requiere el ID numérico (hsa:240), no el símbolo (hsa:ALOX5).
        # Convertir primero con list/{organism}:{symbol}.
        kegg_id = gene_symbol_to_kegg_id(gene) or f"hsa:{gene}"
        pw_ids   = kegg_gene_to_pathways(kegg_id)
        names    = pathway_names(pw_ids)
        pathways = [{'pathway_id': pid, 'name': names.get(pid, pid)} for pid in pw_ids]
    except Exception as exc:
        log.error("KEGG gene pathways error for %s: %s", gene, exc)
        return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({'gene': gene, 'kegg_id': kegg_id, 'pathways': pathways})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def target_graph_view(request, target_id: str):
    """GET /api/drugs/targets/<target_id>/graph/
    Devuelve nodos y aristas en formato Cytoscape para la diana y sus fármacos.
    """
    doc = None
    if _mongo_targets_ready():
        doc = get_db().targets.find_one(
            {'_id': target_id},
            {'name': 1, 'drug_refs': 1},
        )

    if doc:
        drug_refs = [d for d in doc.get('drug_refs', []) if d.get('drugbank_id')]
        target_name = doc.get('name', target_id)
    else:
        # Fallback a Neo4j
        driver = get_driver()
        with driver.session() as session:
            res = session.run(
                """
                MATCH (t:Target {drugbank_target_id: $id})
                OPTIONAL MATCH (d:Drug)-[r]->(t)
                RETURN t.name AS target_name,
                       d.drugbank_id AS drugbank_id,
                       d.name AS drug_name,
                       type(r) AS rel_type
                """,
                id=target_id
            )
            rows = res.data()
        if not rows:
            return Response({'error': 'Target no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        target_name = rows[0].get('target_name') or target_id
        drug_refs = [
            {'drugbank_id': r['drugbank_id'], 'drug_name': r['drug_name'], 'rel_type': r['rel_type']}
            for r in rows if r.get('drugbank_id')
        ]

    nodes = [{'data': {'id': target_id, 'label': target_name, 'kind': 'target'}}]
    edges = []
    for d in drug_refs:
        did = d['drugbank_id']
        nodes.append({'data': {'id': did, 'label': d.get('drug_name') or did, 'kind': 'drug'}})
        edges.append({'data': {'source': did, 'target': target_id, 'label': d.get('rel_type', '')}})

    return Response({'nodes': nodes, 'edges': edges})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def target_compare_view(request):
    """GET /api/drugs/targets/compare/?a=<id>&b=<id>
    Compara dos dianas: fármacos comunes, exclusivos y Jaccard.
    """
    a_id = request.query_params.get('a', '').strip()
    b_id = request.query_params.get('b', '').strip()
    if not a_id or not b_id:
        return Response({'error': 'Parámetros a y b requeridos'}, status=status.HTTP_400_BAD_REQUEST)

    def _drugs_for(target_id: str) -> list[dict] | None:
        """None = diana no encontrada; [] = encontrada sin fármacos."""
        if _mongo_targets_ready():
            doc = get_db().targets.find_one(
                {'_id': target_id},
                {'drug_refs': 1},
            )
            if doc is not None:
                return [d for d in doc.get('drug_refs', []) if d.get('drugbank_id')]
        driver = get_driver()
        with driver.session() as session:
            rows = list(session.run(
                "MATCH (t:Target {drugbank_target_id: $id}) "
                "OPTIONAL MATCH (d:Drug)-[r]->(t) "
                "RETURN d.drugbank_id AS drugbank_id, d.name AS drug_name, type(r) AS rel_type",
                id=target_id
            ))
            if not rows:
                return None
            return [dict(r) for r in rows if r['drugbank_id']]

    drugs_a = _drugs_for(a_id)
    drugs_b = _drugs_for(b_id)

    if drugs_a is None:
        return Response({'error': f'Diana {a_id} no encontrada'}, status=status.HTTP_404_NOT_FOUND)
    if drugs_b is None:
        return Response({'error': f'Diana {b_id} no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    set_a = {d['drugbank_id'] for d in drugs_a}
    set_b = {d['drugbank_id'] for d in drugs_b}
    common_ids = set_a & set_b
    union_ids  = set_a | set_b

    map_a = {d['drugbank_id']: d for d in drugs_a}
    map_b = {d['drugbank_id']: d for d in drugs_b}

    jaccard = len(common_ids) / len(union_ids) if union_ids else 0.0

    return Response({
        'common_drugs':  [map_a.get(did) or map_b[did] for did in sorted(common_ids)],
        'only_a_drugs':  [map_a[did] for did in sorted(set_a - set_b)],
        'only_b_drugs':  [map_b[did] for did in sorted(set_b - set_a)],
        'stats': {
            'count_a':           len(set_a),
            'count_b':           len(set_b),
            'count_common':      len(common_ids),
            'jaccard_similarity': round(jaccard, 4),
        },
    })
