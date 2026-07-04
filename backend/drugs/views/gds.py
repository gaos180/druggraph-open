"""
gds.py — Endpoints Django para análisis de red con GDS.

Registrar en drugs/urls.py:

    from .gds import (
        gds_centrality_view,
        gds_communities_view,
        gds_link_prediction_view,
        gds_link_prediction_global_view,
    )

    path('gds/centrality/',        gds_centrality_view,             name='gds-centrality'),
    path('gds/communities/',       gds_communities_view,            name='gds-communities'),
    path('gds/predict/<str:drug_id>/', gds_link_prediction_view,    name='gds-predict'),
    path('gds/predict-global/',    gds_link_prediction_global_view, name='gds-predict-global'),

Todos los endpoints devuelven 503 si el plugin GDS no está instalado.
"""

import logging

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from neo4j import exceptions as neo4j_exc

from config.services.gds_service import (
    centrality,
    communities,
    predict_links_for_drug,
    predict_links_gds,
    GDSUnavailable,
    DEFAULT_TOP_N,
)

log = logging.getLogger(__name__)


def _int_param(request, name, default):
    try:
        return int(request.GET.get(name, default))
    except (TypeError, ValueError):
        return default


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/gds/centrality/?node=Target&metric=pagerank&top_n=50
# ══════════════════════════════════════════════════════════════════════════════

@require_GET
def gds_centrality_view(request):
    """
    Ranking de centralidad sobre :Target o :Drug.

    Query params:
        node   : "Target" | "Drug"  (default "Target")
        metric : "pagerank" | "degree"  (default "pagerank")
        top_n  : int  (default 50, máx 200)

    Casos de uso:
        - node=Target&metric=degree   → dianas más promiscuas (posibles off-targets)
        - node=Drug&metric=degree     → fármacos multi-diana
        - node=Target&metric=pagerank → dianas centrales en la red de interacción
    """
    node   = request.GET.get("node", "Target")
    metric = request.GET.get("metric", "pagerank")
    top_n  = _int_param(request, "top_n", DEFAULT_TOP_N)

    try:
        result = centrality(node_label=node, metric=metric, top_n=top_n)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except GDSUnavailable as exc:
        return JsonResponse({"error": str(exc)}, status=503)
    except neo4j_exc.ServiceUnavailable:
        return JsonResponse({"error": "Neo4j no disponible."}, status=503)
    except Exception as exc:
        log.error("gds_centrality_view error: %s", exc)
        return JsonResponse({"error": "Error interno en el análisis de centralidad."}, status=500)

    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/gds/communities/?max=100&min_size=2&members=20
# ══════════════════════════════════════════════════════════════════════════════

@require_GET
def gds_communities_view(request):
    """
    Detección de comunidades (Louvain) en el grafo bipartito Drug↔Target.

    Query params:
        max      : máx. de comunidades a devolver (default 100)
        min_size : tamaño mínimo de comunidad (default 2)
        members  : máx. de miembros listados por comunidad (default 20)
    """
    max_comm = _int_param(request, "max", 100)
    min_size = _int_param(request, "min_size", 2)
    members  = _int_param(request, "members", 20)

    try:
        result = communities(
            max_communities=max_comm,
            min_size=min_size,
            members_per_community=members,
        )
    except GDSUnavailable as exc:
        return JsonResponse({"error": str(exc)}, status=503)
    except neo4j_exc.ServiceUnavailable:
        return JsonResponse({"error": "Neo4j no disponible."}, status=503)
    except Exception as exc:
        log.error("gds_communities_view error: %s", exc)
        return JsonResponse({"error": "Error interno en la detección de comunidades."}, status=500)

    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/gds/predict/<drug_id>/?top_n=50&method=adamic_adar
# ══════════════════════════════════════════════════════════════════════════════

@require_GET
def gds_link_prediction_view(request, drug_id: str):
    """
    Predicción de enlaces para un fármaco específico: targets a los que
    PODRÍA unirse según la topología de la red, pero que no están documentados.

    Query params:
        top_n  : int (default 50, máx 100)
        method : "adamic_adar" | "common_neighbors" (default "adamic_adar")

    No requiere el plugin GDS (usa fórmula topológica en Cypher puro).
    """
    drug_id = drug_id.strip()
    top_n   = _int_param(request, "top_n", DEFAULT_TOP_N)
    method  = request.GET.get("method", "adamic_adar")

    try:
        result = predict_links_for_drug(drug_id, top_n=top_n, method=method)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except neo4j_exc.ServiceUnavailable:
        return JsonResponse({"error": "Neo4j no disponible."}, status=503)
    except Exception as exc:
        log.error("gds_link_prediction_view error: %s", exc)
        return JsonResponse({"error": "Error interno en la predicción de enlaces."}, status=500)

    if not result:
        return JsonResponse({"error": f"Fármaco '{drug_id}' no encontrado."}, status=404)

    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/gds/predict-global/?top_n=50
# ══════════════════════════════════════════════════════════════════════════════

@require_GET
def gds_link_prediction_global_view(request):
    """
    Predicción de enlaces a escala global con GDS (gds.alpha.linkprediction).
    Devuelve los pares (fármaco, target) no conectados con mayor score.

    Requiere el plugin GDS instalado (503 si no).

    Query params:
        top_n : int (default 50, máx 100)
    """
    top_n = _int_param(request, "top_n", DEFAULT_TOP_N)

    try:
        result = predict_links_gds(top_n=top_n)
    except GDSUnavailable as exc:
        return JsonResponse({"error": str(exc)}, status=503)
    except neo4j_exc.ServiceUnavailable:
        return JsonResponse({"error": "Neo4j no disponible."}, status=503)
    except Exception as exc:
        log.error("gds_link_prediction_global_view error: %s", exc)
        return JsonResponse({"error": "Error interno en la predicción global."}, status=500)

    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})
