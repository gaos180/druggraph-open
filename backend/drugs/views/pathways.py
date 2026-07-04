"""
pathways.py — Endpoint Django que combina efecto directo (Neo4j),
efecto indirecto (STRING PPI) y rutas biológicas (KEGG).

Registrar en drugs/urls.py:

    from .pathways import drug_pathways_view
    path('drugs/<str:drug_id>/pathways/', drug_pathways_view, name='drug-pathways'),

Query params:
    include : "string,kegg"  (cuáles análisis correr; default ambos)
    species : NCBI taxon id para STRING/KEGG (default 9606 humano)
    score   : required_score STRING 0–1000 (default 400)
"""

import logging
from concurrent.futures import ThreadPoolExecutor

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from neo4j import exceptions as neo4j_exc

from config.services.neo4j_service import _session
from config.services.string_service import indirect_neighbors, network_image_url, TAXON_HUMAN
from config.services.kegg_service import pathways_for_targets

log = logging.getLogger(__name__)

MAX_TARGETS_FOR_EXTERNAL = 25   # tope de targets a enviar a STRING/KEGG (latencia)


def _fetch_drug_with_targets(drugbank_id: str) -> tuple[dict | None, list[dict]]:
    """
    Obtiene el fármaco y sus targets directos (con uniprot/gene) desde Neo4j.
    Retorna (drug_info, targets) o (None, []) si no existe.
    """
    # El símbolo del gen vive directamente en el nodo :Target (t.gene_name); no
    # existen nodos :Polypeptide en el grafo, así que se lee la propiedad directa
    # en vez de un OPTIONAL MATCH que nunca casaba (dejaba gene_name siempre vacío
    # y degradaba el mapeo a STRING/KEGG a UniProt).
    cypher = """
        MATCH (d:Drug {drugbank_id: $drug_id})
        OPTIONAL MATCH (d)-[r]->(t:Target)
        WITH d, t, r
        RETURN d.name AS drug_name,
               d.drugbank_id AS drugbank_id,
               t.drugbank_target_id AS target_id,
               t.uniprot_id AS target_uniprot,
               t.name AS target_name,
               t.organism AS organism,
               coalesce(t.gene_name, '') AS gene_name,
               t.uniprot_id AS poly_uniprot,
               collect(DISTINCT type(r)) AS rel_types
    """
    drug_info = None
    targets = []
    seen = set()

    with _session() as session:
        rows = session.run(cypher, drug_id=drugbank_id).data()

    for row in rows:
        if drug_info is None:
            drug_info = {
                "drugbank_id": row["drugbank_id"],
                "name":        row["drug_name"],
            }
        tid = row.get("target_id")
        if not tid or tid in seen:
            continue
        seen.add(tid)
        targets.append({
            "drugbank_target_id": tid,
            "uniprot_id": row.get("target_uniprot") or row.get("poly_uniprot") or "",
            "name":       row.get("target_name") or "",
            "gene_name":  row.get("gene_name") or "",
            "organism":   row.get("organism") or "",
            "rel_types":  row.get("rel_types") or [],
        })

    return drug_info, targets


@require_GET
def drug_pathways_view(request, drug_id: str):
    """
    GET /api/drugs/<drug_id>/pathways/

    Devuelve:
        {
            "drug": { drugbank_id, name },
            "direct_targets": [ { drugbank_target_id, uniprot_id, name, gene_name, organism, rel_types } ],
            "indirect": {                 # STRING (si include incluye 'string')
                "direct_genes": [str],
                "neighbors": [ {partner_protein, max_score, connected_to, connection_count} ],
                "edges": [ {source, target, score} ],
                "network_image_url": str
            } | null,
            "pathways": {                 # KEGG (si include incluye 'kegg')
                "pathways": [ {pathway_id, name, target_count, targets, kegg_genes} ],
                "unmapped_targets": [str],
                "pathway_count": int
            } | null,
            "notes": [str]                # avisos (ej. targets truncados)
        }
    """
    drug_id = drug_id.strip()
    include = (request.GET.get("include") or "string,kegg").lower()
    do_string = "string" in include
    do_kegg   = "kegg" in include

    try:
        species = int(request.GET.get("species", TAXON_HUMAN))
    except (TypeError, ValueError):
        species = TAXON_HUMAN
    try:
        score = int(request.GET.get("score", 400))
    except (TypeError, ValueError):
        score = 400

    try:
        drug_info, targets = _fetch_drug_with_targets(drug_id)
    except neo4j_exc.ServiceUnavailable:
        return JsonResponse({"error": "Neo4j no disponible."}, status=503)
    except Exception as exc:
        log.error("drug_pathways_view neo4j error: %s", exc)
        return JsonResponse({"error": "Error consultando el grafo."}, status=500)

    if not drug_info:
        return JsonResponse({"error": f"Fármaco '{drug_id}' no encontrado."}, status=404)

    notes = []

    # Limitar targets enviados a APIs externas (latencia/cortesía)
    targets_for_external = targets[:MAX_TARGETS_FOR_EXTERNAL]
    if len(targets) > MAX_TARGETS_FOR_EXTERNAL:
        notes.append(
            f"Se analizaron los primeros {MAX_TARGETS_FOR_EXTERNAL} de {len(targets)} targets "
            "para los análisis externos."
        )

    # Genes para STRING: preferir gene_name, caer a uniprot
    gene_symbols = [
        t["gene_name"] or t["uniprot_id"]
        for t in targets_for_external
        if (t["gene_name"] or t["uniprot_id"])
    ]

    # STRING y KEGG son servicios externos independientes (rate-limiters
    # separados), así que se lanzan en paralelo para solapar su latencia de red
    # en vez de sumarla secuencialmente.
    def _run_string():
        if not (do_string and gene_symbols):
            return None
        res = indirect_neighbors(gene_symbols, species=species, required_score=score)
        res["network_image_url"] = network_image_url(
            gene_symbols, species=species, required_score=score,
        )
        return res

    def _run_kegg():
        if not do_kegg:
            return None
        return pathways_for_targets(targets_for_external)

    indirect = None
    pathways = None
    with ThreadPoolExecutor(max_workers=2) as pool:
        string_future = pool.submit(_run_string)
        kegg_future = pool.submit(_run_kegg)

        try:
            indirect = string_future.result()
        except Exception as exc:
            log.error("STRING error: %s", exc)
            notes.append("No se pudo obtener la red de interacción de STRING.")

        try:
            pathways = kegg_future.result()
        except Exception as exc:
            log.error("KEGG error: %s", exc)
            notes.append("No se pudieron obtener las rutas de KEGG.")

    return JsonResponse(
        {
            "drug":           drug_info,
            "direct_targets": targets,
            "indirect":       indirect,
            "pathways":       pathways,
            "notes":          notes,
        },
        json_dumps_params={"ensure_ascii": False},
    )
