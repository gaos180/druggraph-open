"""
chemprop_tox.py — GNN Chemprop (D-MPNN) multi-tarea de toxicidad Tox21 (Tier 4.6).

POST /api/tools/chemprop-tox/
    body: { smiles } | { drug_id }
    → 12 probabilidades de toxicidad Tox21 predichas por un D-MPNN Chemprop (rankeadas),
      con cita del paper y disclaimer in-silico.

Complementa al ADMET por RandomForest (4.3): GNN que aprende la representación molecular vs.
features RDKit fijos. Requiere chemprop + el modelo entrenado (scripts/train_chemprop.py).
Degrada con 503 si faltan el paquete o el modelo.
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.services import chemprop_service

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
def chemprop_tox_view(request):
    if not chemprop_service.model_ready():
        return Response(
            {"error": "GNN Chemprop no disponible (instala chemprop + entrena con "
                      "scripts/train_chemprop.py).", "available": False},
            status=503,
        )

    smiles = _resolve_smiles(request)
    if not smiles or len(smiles) > MAX_SMILES_LENGTH:
        return Response({"error": "Se requiere 'smiles' (o 'drug_id' resoluble), ≤ 500 caracteres."},
                        status=400)

    try:
        result = chemprop_service.predict(smiles)
    except Exception as exc:
        log.error("chemprop_tox_view error: %s", exc)
        return Response({"error": "Error prediciendo toxicidad con Chemprop."}, status=500)

    if not result.get("available"):
        return Response(result, status=503)
    return Response(result)
