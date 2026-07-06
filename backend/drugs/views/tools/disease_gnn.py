"""
disease_gnn.py — Repurposing fármaco→enfermedad por GNN sobre el KG (Tier 4.7, BiomedGPS).

GET /api/tools/disease-gnn/<drug_id>/?top_n=20
    → enfermedades a las que el fármaco PODRÍA reposicionarse según la GNN de enlaces del
      knowledge graph (Drug↔Target↔Disease), con probabilidad + métricas del modelo.

Solo LEE las aristas :PREDICTED_DISEASE precomputadas por scripts/train_disease_gnn.py.
Degrada con 503 si el modelo no se ha entrenado / GDS o la capa de enfermedad faltan.
"""
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from neo4j import exceptions as neo4j_exc

from config.services import disease_gnn_service

log = logging.getLogger(__name__)


@require_GET
def disease_gnn_view(request, drug_id: str):
    drug_id = (drug_id or "").strip()
    try:
        top_n = int(request.GET.get("top_n", 20))
    except (TypeError, ValueError):
        top_n = 20

    try:
        result = disease_gnn_service.predict_for_drug(drug_id, top_n=top_n)
    except disease_gnn_service.DiseaseGNNUnavailable as exc:
        return JsonResponse({"available": False, "error": str(exc)}, status=503)
    except neo4j_exc.ServiceUnavailable:
        return JsonResponse({"available": False, "error": "Neo4j no disponible."}, status=503)
    except Exception as exc:
        log.error("disease_gnn_view error: %s", exc)
        return JsonResponse({"error": "Error prediciendo enfermedades."}, status=500)

    # Sin modelo entrenado no hay predicciones: señalar 503 para consistencia con Tier 4.
    if not result.get("model"):
        return JsonResponse(
            {"available": False,
             "error": "Modelo fármaco→enfermedad no entrenado (scripts/train_disease_gnn.py)."},
            status=503,
        )
    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})
