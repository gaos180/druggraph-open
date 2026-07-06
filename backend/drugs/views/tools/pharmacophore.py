"""
pharmacophore.py — Modelado de pharmacóforos 3D ligand-based (Tier 5.1).

POST /api/tools/pharmacophore/
    body: { smiles } (uno o varios separados por '|')  |  { drug_id }  |  { min_fraction }
    → un SMILES: rasgos 3D + distancias; varios: perfil de consenso; + referencias.

Implementación propia con RDKit (open). Degrada con 503 si RDKit falta o el SMILES es inválido.
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.services import pharmacophore_service

log = logging.getLogger(__name__)

MAX_LEN = 5000
MAX_MOLS = 25


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def pharmacophore_view(request):
    if not pharmacophore_service.RDKIT_OK:
        return Response({"available": False, "error": "RDKit no disponible."}, status=503)

    drug_id = (request.data.get("drug_id") or "").strip()
    raw = (request.data.get("smiles") or "").strip()
    try:
        min_fraction = float(request.data.get("min_fraction", 0.5))
    except (TypeError, ValueError):
        min_fraction = 0.5

    try:
        if drug_id:
            result = pharmacophore_service.pharmacophore_for_drug(drug_id)
        elif raw and len(raw) <= MAX_LEN:
            smiles_list = [s.strip() for s in raw.split("|") if s.strip()][:MAX_MOLS]
            result = pharmacophore_service.build(smiles_list, min_fraction=min_fraction)
        else:
            return Response({"error": "Se requiere 'smiles' (uno o varios con '|') o 'drug_id'."},
                            status=400)
    except Exception as exc:
        log.error("pharmacophore_view error: %s", exc)
        return Response({"error": "Error construyendo el pharmacóforo."}, status=500)

    if not result.get("available"):
        return Response(result, status=503 if "RDKit" in result.get("reason", "") else 400)
    return Response(result)
