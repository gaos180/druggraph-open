"""
similarity.py — Similitud de consenso multi-fingerprint (Tier 1.2).

Desglosa la similitud estructural entre un compuesto sandbox y un fármaco de la base
en varios fingerprints complementarios (Morgan, MACCS, atom-pair, farmacóforo) más un
consenso. Se calcula bajo demanda (la huella de farmacóforo es costosa) para no
penalizar el análisis principal del sandbox.

    POST /api/drugs/sandbox/similarity-detail/
        body: { smiles: str, drugbank_id?: str, smiles_b?: str }
"""

import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.services.mongo import get_db
from config.services.sandbox_service import named_similarities, RDKIT_OK
from .bioactivity import _find_drug, _smiles_from_doc

log = logging.getLogger(__name__)

MAX_SMILES_LENGTH = 500


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sandbox_similarity_detail_view(request):
    if not RDKIT_OK:
        return Response({"error": "RDKit no está instalado en el servidor."}, status=503)

    body = request.data
    smiles = (body.get("smiles") or "").strip()
    if not smiles or len(smiles) > MAX_SMILES_LENGTH:
        return Response({"error": "El campo 'smiles' es obligatorio y ≤ 500 caracteres."}, status=400)

    smiles_b = (body.get("smiles_b") or "").strip()
    drugbank_id = (body.get("drugbank_id") or "").strip().upper()

    drug_name = None
    if not smiles_b and drugbank_id:
        doc = _find_drug(get_db(), drugbank_id)
        if not doc:
            return Response({"error": f"Fármaco {drugbank_id} no encontrado."}, status=404)
        drug_name = doc.get("name")
        smiles_b = _smiles_from_doc(doc)
        if not smiles_b:
            return Response({
                "available": False,
                "drugbank_id": drugbank_id, "name": drug_name,
                "notes": ["El fármaco no tiene SMILES (p.ej. biotecnológico)."],
            })

    if not smiles_b:
        return Response({"error": "Se requiere 'smiles_b' o 'drugbank_id'."}, status=400)

    result = named_similarities(smiles, smiles_b)
    return Response({
        "drugbank_id": drugbank_id or None,
        "name": drug_name,
        **result,
    })
