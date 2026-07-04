"""
admet.py — Predicción ADMET/toxicidad supervisada (Tier 4.3).

POST /api/tools/admet/
    body: { smiles } | { drug_id }
    → predicciones ADMET (BBBP, ESOL, Tox21…) con la métrica de test de cada modelo.

Requiere scikit-learn + los modelos entrenados (scripts/train_admet_models.py).
Degrada con 503 si faltan deps o modelos.
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.services import admet_service

log = logging.getLogger(__name__)

MAX_SMILES_LENGTH = 500


def _resolve_smiles(request) -> str:
    smiles = (request.data.get("smiles") or "").strip()
    if smiles:
        return smiles
    drug_id = (request.data.get("drug_id") or "").strip().upper()
    if drug_id:
        try:
            from config.services.mongo import get_db
            from config.services.chemberta_index import _smiles_for
            return _smiles_for(get_db(), drug_id)
        except Exception as exc:
            log.debug("_resolve_smiles error: %s", exc)
    return ""


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admet_view(request):
    if not admet_service.ADMET_OK:
        return Response(
            {"error": "ADMET no disponible (instala scikit-learn + joblib).", "available": False},
            status=503,
        )

    smiles = _resolve_smiles(request)
    if not smiles or len(smiles) > MAX_SMILES_LENGTH:
        return Response({"error": "Se requiere 'smiles' (o 'drug_id' resoluble), ≤ 500 caracteres."},
                        status=400)

    try:
        result = admet_service.predict(smiles)
    except Exception as exc:
        log.error("admet_view error: %s", exc)
        return Response({"error": "Error prediciendo ADMET."}, status=500)

    if not result.get("available"):
        return Response(result, status=503)
    return Response(result)
