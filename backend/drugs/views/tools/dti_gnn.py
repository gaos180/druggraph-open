"""
dti_gnn.py — Predicción de interacción fármaco-diana con GNN (Tier 4.2).

GET /api/tools/dti-gnn/<drug_id>/
    → dianas predichas (no documentadas) por la GNN entrenada, con probabilidad y la
      métrica AUCPR/AP del modelo.

Requiere el modelo entrenado (scripts/train_dti_gnn.py) + GDS. Degrada con 503 si el modelo
no está entrenado o GDS no está disponible.
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.services import dti_gnn_service

log = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dti_gnn_view(request, drug_id):
    try:
        result = dti_gnn_service.predict_for_drug(drug_id.upper())
    except dti_gnn_service.DTIUnavailable as exc:
        return Response({"error": str(exc), "available": False}, status=503)
    except Exception as exc:
        log.error("dti_gnn_view error: %s", exc)
        return Response({"error": "Error consultando la GNN DTI."}, status=500)

    # Sin predicciones y sin modelo entrenado → 503 (aún no se corrió el entrenamiento).
    if not result.get("model"):
        return Response(
            {"error": "Modelo DTI no entrenado. Ejecuta scripts/train_dti_gnn.py.",
             "available": False},
            status=503,
        )
    return Response(result)
