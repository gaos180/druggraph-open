"""
sandbox.py — Endpoints Django para el "químico sandbox".

Registrar en drugs/urls.py:

    from .sandbox import (
        sandbox_analyze_view,
        sandbox_target_search_view,
        sandbox_cleanup_view,
    )

    path('sandbox/analyze/',       sandbox_analyze_view,       name='sandbox-analyze'),
    path('sandbox/targets/',       sandbox_target_search_view, name='sandbox-targets'),
    path('sandbox/<str:sandbox_id>/', sandbox_cleanup_view,    name='sandbox-cleanup'),
"""

import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from neo4j import exceptions as neo4j_exc
from rest_framework.decorators import api_view

from config.services.sandbox_service import (
    analyze_sandbox_compound,
    delete_sandbox_drug,
    RDKIT_OK,
    MAX_CANDIDATE_TARGETS,
)
from config.services.neo4j_service import _session
from config.services.swiss_service import (
    parse_swiss_csv,
    predict_targets,
    ORGANISMS,
)
from config.services.string_service import indirect_neighbors, functional_annotations
from config.services.kegg_service import pathways_for_targets
from config.services.ctd_service import gene_interactions as ctd_gene_interactions
from config.services.propagation_service import propagate, propagate_signed, PropagationUnavailable

log = logging.getLogger(__name__)

MAX_SMILES_LENGTH = 500


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/sandbox/analyze/
# ══════════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
def sandbox_analyze_view(request):
    """
    Analiza un compuesto sandbox: valida el SMILES, crea un nodo temporal
    (:SandboxDrug) en Neo4j, calcula similitud estructural y de comportamiento
    contra fármacos reales, y elimina el nodo temporal al finalizar.

    Body JSON:
        {
            "smiles":     str,            // requerido
            "name":       str,            // opcional, default "Compuesto sandbox"
            "target_ids": [str],          // opcional, drugbank_target_id candidatos
            "session_id": str,            // opcional — reutilizar sesión existente
            "persist":    bool            // opcional, default false.
                                           // Si true, NO borra el nodo al finalizar
                                           // (queda sujeto al TTL de 30 min)
        }

    Respuesta 200:
        {
            "sandbox": {
                "session_id", "sandbox_id", "name", "smiles",
                "properties": { molecular_weight, logp, tpsa, ... },
                "linked_targets": [str],
                "expires_at": float
            },
            "structural_similarity": [ {drugbank_id, name, score} ],
            "behavioral_similarity": [ {drugbank_id, name, score, shared_targets?} ],
            "combined": [ {drugbank_id, name, structural_score, behavioral_score, combined_score} ],
            "method_used": "gds" | "jaccard" | "structural_only" | "none"
        }

    Errores:
        400 — SMILES ausente/inválido, demasiado largo, demasiados targets.
        503 — RDKit no instalado o Neo4j no disponible.
    """
    if not RDKIT_OK:
        return JsonResponse(
            {"error": "RDKit no está instalado en el servidor. "
                      "Instala con: pip install rdkit"},
            status=503,
        )

    body = request.data
    smiles = (body.get("smiles") or "").strip()
    if not smiles:
        return JsonResponse({"error": "El campo 'smiles' es obligatorio."}, status=400)
    if len(smiles) > MAX_SMILES_LENGTH:
        return JsonResponse(
            {"error": f"SMILES demasiado largo (máx. {MAX_SMILES_LENGTH} caracteres)."},
            status=400,
        )

    name = (body.get("name") or "Compuesto sandbox").strip()[:200]

    target_ids = body.get("target_ids") or []
    if not isinstance(target_ids, list):
        return JsonResponse({"error": "'target_ids' debe ser una lista."}, status=400)
    target_ids = [str(t).strip() for t in target_ids if str(t).strip()][:MAX_CANDIDATE_TARGETS]

    session_id = body.get("session_id")
    if session_id is not None:
        session_id = str(session_id).strip()[:64] or None

    persist = bool(body.get("persist", False))

    try:
        result = analyze_sandbox_compound(
            smiles=smiles,
            name=name,
            target_ids=target_ids,
            session_id=session_id,
            cleanup=not persist,
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except neo4j_exc.ServiceUnavailable:
        return JsonResponse(
            {"error": "El servicio de grafo no está disponible en este momento."},
            status=503,
        )
    except Exception as exc:
        log.error("sandbox_analyze_view error: %s", exc)
        return JsonResponse(
            {"error": "Error interno al analizar el compuesto."}, status=500
        )

    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/sandbox/targets/?search=...
# ══════════════════════════════════════════════════════════════════════════════

MAX_TARGET_SEARCH_RESULTS = 25


@api_view(['GET'])
def sandbox_target_search_view(request):
    """
    Autocompletado de targets reales para que el usuario seleccione
    "targets candidatos" al crear su compuesto sandbox.

    Query params:
        search : str — texto parcial (nombre de proteína, gen, UniProt ID
                        o drugbank_target_id). Mínimo 2 caracteres.

    Respuesta 200:
        {
            "results": [
                {
                    "drugbank_target_id": str,
                    "uniprot_id":         str,
                    "name":               str,
                    "organism":           str
                }
            ]
        }
    """
    search = request.GET.get("search", "").strip()
    if len(search) < 2:
        return JsonResponse({"results": []})

    cypher = """
        MATCH (t:Target)
        WHERE toLower(t.name) CONTAINS toLower($search)
           OR toLower(t.drugbank_target_id) CONTAINS toLower($search)
           OR toLower(coalesce(t.uniprot_id, '')) CONTAINS toLower($search)
           OR toLower(coalesce(t.gene_name, ''))  CONTAINS toLower($search)
        RETURN t.drugbank_target_id AS drugbank_target_id,
               t.uniprot_id         AS uniprot_id,
               t.gene_name          AS gene_name,
               t.name               AS name,
               t.organism           AS organism
        ORDER BY t.name
        LIMIT $limit
    """

    try:
        with _session() as session:
            results = session.run(
                cypher, search=search, limit=MAX_TARGET_SEARCH_RESULTS
            ).data()
    except neo4j_exc.ServiceUnavailable:
        return JsonResponse(
            {"error": "El servicio de grafo no está disponible en este momento."},
            status=503,
        )
    except Exception as exc:
        log.error("sandbox_target_search_view error: %s", exc)
        return JsonResponse({"error": "Error interno buscando targets."}, status=500)

    # Normalizar nulls
    for r in results:
        r["uniprot_id"] = r.get("uniprot_id") or ""
        r["organism"]   = r.get("organism") or ""

    return JsonResponse({"results": results}, json_dumps_params={"ensure_ascii": False})


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /api/sandbox/<sandbox_id>/
# ══════════════════════════════════════════════════════════════════════════════

@api_view(['DELETE'])
def sandbox_cleanup_view(request, sandbox_id: str):
    """
    Elimina manualmente un nodo :SandboxDrug por su sandbox_id.
    Útil si el frontend usó persist=true y quiere limpiar antes del TTL.

    Respuesta 200:
        { "deleted": int }
    """
    sandbox_id = sandbox_id.strip()
    if not sandbox_id:
        return JsonResponse({"error": "sandbox_id requerido."}, status=400)

    try:
        deleted = delete_sandbox_drug(sandbox_id=sandbox_id)
    except Exception as exc:
        log.error("sandbox_cleanup_view error: %s", exc)
        return JsonResponse({"error": "Error eliminando el sandbox."}, status=500)

    return JsonResponse({"deleted": deleted})


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/drugs/sandbox/pathways/
# ══════════════════════════════════════════════════════════════════════════════

def _resolve_targets(target_ids: list[str], drug_ids: list[str]) -> list[dict]:
    """Convierte listas de drugbank_target_id y drugbank_id a dicts con gene_name/uniprot."""
    result: list[dict] = []
    seen: set[str] = set()

    if target_ids:
        cypher = """
            MATCH (t:Target)
            WHERE t.drugbank_target_id IN $tids
            RETURN t.drugbank_target_id AS drugbank_target_id,
                   t.uniprot_id AS uniprot_id,
                   t.gene_name  AS gene_name,
                   t.name       AS name,
                   t.organism   AS organism
        """
        with _session() as session:
            for row in session.run(cypher, tids=target_ids).data():
                tid = row["drugbank_target_id"]
                if tid and tid not in seen:
                    seen.add(tid)
                    result.append({
                        "drugbank_target_id": tid,
                        "uniprot_id": row.get("uniprot_id") or "",
                        "gene_name":  row.get("gene_name") or "",
                        "name":       row.get("name") or "",
                        "organism":   row.get("organism") or "",
                    })

    if drug_ids:
        cypher = """
            MATCH (d:Drug)-[]->(t:Target)
            WHERE d.drugbank_id IN $dids
              AND (t.organism = 'Humans' OR t.organism CONTAINS 'Homo sapiens')
            RETURN DISTINCT
                   t.drugbank_target_id AS drugbank_target_id,
                   t.uniprot_id AS uniprot_id,
                   t.gene_name  AS gene_name,
                   t.name       AS name,
                   t.organism   AS organism
            ORDER BY t.name
        """
        with _session() as session:
            for row in session.run(cypher, dids=drug_ids).data():
                tid = row["drugbank_target_id"]
                if tid and tid not in seen:
                    seen.add(tid)
                    result.append({
                        "drugbank_target_id": tid,
                        "uniprot_id": row.get("uniprot_id") or "",
                        "gene_name":  row.get("gene_name") or "",
                        "name":       row.get("name") or "",
                        "organism":   row.get("organism") or "",
                    })

    return result


MAX_TARGETS_PATHWAY = 30
MAX_DRUG_IDS_PATHWAY = 10


@api_view(['POST'])
def sandbox_pathways_view(request):
    """
    POST /api/drugs/sandbox/pathways/

    Calcula rutas metabólicas (KEGG), anotaciones GO y red PPI (STRING)
    para un conjunto de targets del sandbox y/o fármacos similares.

    Body JSON:
        {
            "target_ids": [str],  // drugbank_target_id candidatos (opcional)
            "drug_ids":   [str],  // drugbank_id de fármacos similares (opcional)
        }

    Al menos uno de los dos debe estar presente.
    """
    body = request.data
    target_ids = [str(t).strip() for t in (body.get("target_ids") or []) if str(t).strip()]
    drug_ids   = [str(d).strip() for d in (body.get("drug_ids") or []) if str(d).strip()][:MAX_DRUG_IDS_PATHWAY]

    if not target_ids and not drug_ids:
        return JsonResponse({"error": "Se requiere al menos un target_id o drug_id."}, status=400)

    notes: list[str] = []

    try:
        targets = _resolve_targets(target_ids, drug_ids)
    except neo4j_exc.ServiceUnavailable:
        return JsonResponse({"error": "Neo4j no disponible."}, status=503)
    except Exception as exc:
        log.error("sandbox_pathways_view neo4j error: %s", exc)
        return JsonResponse({"error": "Error consultando el grafo."}, status=500)

    if not targets:
        return JsonResponse({
            "targets_used": [], "kegg": None, "string_ppi": None,
            "go_process": [], "go_function": [], "go_component": [],
            "string_kegg": [], "reactome": [], "wikipathways": [], "ctd": None,
            "notes": ["No se encontraron targets asociados."],
        }, json_dumps_params={"ensure_ascii": False})

    if len(targets) > MAX_TARGETS_PATHWAY:
        notes.append(f"Análisis limitado a los primeros {MAX_TARGETS_PATHWAY} de {len(targets)} targets.")
        targets = targets[:MAX_TARGETS_PATHWAY]

    gene_symbols = [
        t["gene_name"] or t["uniprot_id"]
        for t in targets
        if t["gene_name"] or t["uniprot_id"]
    ]

    # ── STRING PPI ────────────────────────────────────────────────────────────
    string_ppi = None
    func_ann: dict = {}
    if gene_symbols:
        try:
            string_ppi = indirect_neighbors(gene_symbols)
        except Exception as exc:
            log.error("STRING PPI error: %s", exc)
            notes.append("No se pudo obtener la red PPI de STRING.")

        try:
            func_ann = functional_annotations(gene_symbols)
        except Exception as exc:
            log.error("STRING functional_annotation error: %s", exc)
            notes.append("No se pudieron obtener anotaciones funcionales (GO/KEGG) de STRING.")

    # ── KEGG pathways ─────────────────────────────────────────────────────────
    kegg_data = None
    try:
        kegg_data = pathways_for_targets(targets)
    except Exception as exc:
        log.error("KEGG pathways error: %s", exc)
        notes.append("No se pudieron obtener las rutas de KEGG.")

    # ── CTD chemical-gene interactions (MongoDB, rápido) ───────────────────────
    ctd_data = None
    try:
        ctd_data = ctd_gene_interactions(gene_symbols)
        if ctd_data and not ctd_data.get("available"):
            notes.append("Datos de CTD no cargados (ejecuta load_ctd_interactions.py).")
    except Exception as exc:
        log.error("CTD interactions error: %s", exc)
        notes.append("No se pudieron obtener las interacciones químico-gen de CTD.")

    return JsonResponse({
        "targets_used":  targets,
        "kegg":          kegg_data,
        "string_ppi":    string_ppi,
        "go_process":    func_ann.get("go_process", []),
        "go_function":   func_ann.get("go_function", []),
        "go_component":  func_ann.get("go_component", []),
        "string_kegg":   func_ann.get("kegg", []),
        "reactome":      func_ann.get("reactome", []),
        "wikipathways":  func_ann.get("wikipathways", []),
        "ctd":           ctd_data,
        "notes":         notes,
    }, json_dumps_params={"ensure_ascii": False})


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/drugs/sandbox/propagation/
# ══════════════════════════════════════════════════════════════════════════════

MAX_PROPAGATION_SEEDS = 60


@api_view(['POST'])
def sandbox_propagation_view(request):
    """
    POST /api/drugs/sandbox/propagation/

    Propaga el efecto del compuesto por la red PPI de STRING (local) con
    Personalized PageRank y devuelve los genes más alcanzados (efecto en cadena).

    Body JSON:
        genes / target_ids / drug_ids  — semillas (una de las tres formas)
        mode      : "diffusion" (STRING, magnitud) | "directed" (KEGG, con signo)
        seed_sign : -1 (el fármaco inhibe sus dianas, default) | +1   [solo directed]
        max_hops  : profundidad de la cascada [solo directed, default 3]
        top_n     : nº de genes downstream (default 40)

    Respuesta: ver propagation_service.propagate() / propagate_signed().
    """
    body = request.data
    genes = [str(g).strip() for g in (body.get("genes") or []) if str(g).strip()]

    if not genes:
        target_ids = [str(t).strip() for t in (body.get("target_ids") or []) if str(t).strip()]
        drug_ids   = [str(d).strip() for d in (body.get("drug_ids") or []) if str(d).strip()][:MAX_DRUG_IDS_PATHWAY]
        if target_ids or drug_ids:
            try:
                targets = _resolve_targets(target_ids, drug_ids)
            except neo4j_exc.ServiceUnavailable:
                return JsonResponse({"error": "Neo4j no disponible."}, status=503)
            genes = [t["gene_name"] for t in targets if t.get("gene_name")]

    genes = list(dict.fromkeys(genes))[:MAX_PROPAGATION_SEEDS]
    if not genes:
        return JsonResponse({"error": "Se requiere 'genes', 'target_ids' o 'drug_ids'."}, status=400)

    mode = (body.get("mode") or "diffusion").strip()
    top_n = int(body.get("top_n", 40))

    try:
        if mode == "directed":
            result = propagate_signed(
                genes,
                seed_sign=int(body.get("seed_sign", -1)),
                max_hops=int(body.get("max_hops", 3)),
                top_n=top_n,
            )
        else:
            result = propagate(genes, top_n=top_n)
    except PropagationUnavailable as exc:
        return JsonResponse({"error": str(exc), "available": False}, status=503)
    except Exception as exc:
        log.error("sandbox_propagation_view error: %s", exc)
        return JsonResponse({"error": "Error en la propagación."}, status=500)

    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})


# ══════════════════════════════════════════════════════════════════════════════
# GET  /api/drugs/sandbox/swiss-targets/?smiles=...&organism=Homo+sapiens
# POST /api/drugs/sandbox/swiss-targets/   (multipart, campo "file" = CSV)
# ══════════════════════════════════════════════════════════════════════════════

MAX_SWISS_RESULTS = 100

@api_view(['GET', 'POST'])
def sandbox_swiss_targets_view(request):
    """
    Importa predicciones de SwissTargetPrediction y las cruza con los
    Target nodes de Neo4j para devolver `drugbank_target_id`.

    Modo GET — llama a la API de SwissTargetPrediction en tiempo real:
        GET ?smiles=<SMILES>&organism=Homo+sapiens

    Modo POST — parsea un CSV exportado desde swisstargetprediction.ch:
        POST multipart/form-data  con campo "file" = archivo .csv

    Respuesta 200:
        {
          "total":    int,
          "matched":  int,      # con drugbank_target_id en DrugGraph
          "organisms": [...],   # lista de organismos disponibles
          "results": [
            {
              "uniprot_id":         str,
              "gene_name":          str,
              "target_name":        str,
              "probability":        float,
              "target_class":       str,
              "chembl_id":          str,
              "known_actives":      int,
              "drugbank_target_id": str | null,
              "db_name":            str | null,
              "db_organism":        str | null,
              "in_druggraph":       bool,
            }
          ]
        }
    """
    # ── Obtener predicciones ─────────────────────────────────────────────────
    if request.method == 'GET':
        smiles = request.GET.get('smiles', '').strip()
        if not smiles:
            return JsonResponse({"error": "Parámetro 'smiles' obligatorio."}, status=400)
        if len(smiles) > MAX_SMILES_LENGTH:
            return JsonResponse({"error": f"SMILES demasiado largo (máx. {MAX_SMILES_LENGTH})."}, status=400)

        organism = request.GET.get('organism', 'Homo sapiens')
        if organism not in ORGANISMS:
            organism = 'Homo sapiens'

        try:
            swiss = predict_targets(smiles, organism)
        except RuntimeError as exc:
            msg = str(exc)
            if msg.startswith("API_UNAVAILABLE"):
                return JsonResponse({
                    "error": "api_unavailable",
                    "detail": "SwissTargetPrediction no ofrece API REST. Usa la importación CSV.",
                    "swiss_url": f"https://www.swisstargetprediction.ch/predict.php",
                }, status=503)
            return JsonResponse({"error": msg}, status=502)
        except Exception as exc:
            log.error("sandbox_swiss_targets_view API error: %s", exc)
            return JsonResponse({"error": "Error llamando a SwissTargetPrediction."}, status=500)

    else:  # POST — CSV upload
        uploaded = request.FILES.get('file')
        if not uploaded:
            return JsonResponse({"error": "Se esperaba un archivo CSV en el campo 'file'."}, status=400)
        if not uploaded.name.lower().endswith('.csv'):
            return JsonResponse({"error": "Solo se aceptan archivos .csv de SwissTargetPrediction."}, status=400)

        try:
            content = uploaded.read().decode('utf-8-sig')  # elimina BOM si existe
        except UnicodeDecodeError:
            return JsonResponse({"error": "El archivo no está en UTF-8."}, status=400)

        try:
            swiss = parse_swiss_csv(content)
        except Exception as exc:
            log.error("sandbox_swiss_targets_view CSV parse error: %s", exc)
            return JsonResponse({"error": f"Error parseando el CSV: {exc}"}, status=400)

    swiss = swiss[:MAX_SWISS_RESULTS]

    # ── Cruzar con Neo4j ─────────────────────────────────────────────────────
    uniprot_ids = [t["uniprot_id"] for t in swiss if t["uniprot_id"]]
    gene_names  = [t["gene_name"]  for t in swiss if t["gene_name"]]

    neo4j_by_uid: dict[str, dict] = {}
    neo4j_by_gene: dict[str, dict] = {}

    if uniprot_ids or gene_names:
        cypher = """
            MATCH (t:Target)
            WHERE t.uniprot_id IN $uids OR t.gene_name IN $genes
            RETURN t.drugbank_target_id AS drugbank_target_id,
                   t.uniprot_id         AS uniprot_id,
                   t.gene_name          AS gene_name,
                   t.name               AS name,
                   t.organism           AS organism
        """
        try:
            with _session() as session:
                rows = session.run(cypher, uids=uniprot_ids, genes=gene_names).data()
            for row in rows:
                if row.get("uniprot_id"):
                    neo4j_by_uid[row["uniprot_id"]] = row
                if row.get("gene_name"):
                    neo4j_by_gene[row["gene_name"]] = row
        except Exception as exc:
            log.warning("sandbox_swiss_targets_view Neo4j lookup failed: %s", exc)

    # ── Enriquecer y devolver ────────────────────────────────────────────────
    enriched = []
    for t in swiss:
        neo4j = neo4j_by_uid.get(t["uniprot_id"]) or neo4j_by_gene.get(t["gene_name"])
        enriched.append({
            **t,
            "drugbank_target_id": neo4j["drugbank_target_id"] if neo4j else None,
            "db_name":            neo4j["name"]               if neo4j else None,
            "db_organism":        neo4j["organism"]           if neo4j else None,
            "in_druggraph":       neo4j is not None,
        })

    matched = sum(1 for r in enriched if r["in_druggraph"])

    return JsonResponse(
        {
            "total":     len(enriched),
            "matched":   matched,
            "organisms": ORGANISMS,
            "results":   enriched,
        },
        json_dumps_params={"ensure_ascii": False},
    )
