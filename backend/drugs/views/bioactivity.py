"""
bioactivity.py — Bioactividad experimental (ChEMBL + PubChem BioAssay).

Convierte la similitud *predicha* en comportamiento *medido*: potencia y mecanismo
de acción curados (ChEMBL) + resumen de bioensayos activo/inactivo (PubChem).

    GET  /api/drugs/<drug_id>/bioactivity/   — para un fármaco de la base (resuelve su SMILES)
    POST /api/drugs/sandbox/bioactivity/     — para un compuesto sandbox (body {smiles})
"""

import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from config.services.mongo import get_db
from config.services import chembl_service, pubchem_service

log = logging.getLogger(__name__)

MAX_SMILES_LENGTH = 500


def _find_drug(db, drug_id: str):
    doc = db.drugs.find_one({"drugbank-id": drug_id},
                            {"name": 1, "calculated-properties": 1, "experimental-properties": 1})
    if not doc:
        doc = db.drugs.find_one({"drugbank-id.value": drug_id},
                                {"name": 1, "calculated-properties": 1, "experimental-properties": 1})
    return doc


def _smiles_from_doc(doc: dict) -> str:
    """Extrae el SMILES de calculated-/experimental-properties (kind == 'SMILES')."""
    for field in ("calculated-properties", "experimental-properties"):
        props = doc.get(field) or []
        if isinstance(props, list):
            for p in props:
                if isinstance(p, dict) and str(p.get("kind", "")).upper() == "SMILES":
                    val = (p.get("value") or "").strip()
                    if val:
                        return val
    return ""


def _build_profile(smiles: str, notes: list) -> dict:
    """Combina ChEMBL (potencia+MoA) y PubChem (bioensayos) desde un SMILES."""
    chembl = chembl_service.full_profile(smiles)
    if not chembl.get("available"):
        notes.append("Sin coincidencia en ChEMBL para esta estructura.")

    pubchem = {"available": False, "cid": None, "total": 0, "active": 0, "inactive": 0, "assays": []}
    cid = pubchem_service.cid_from_smiles(smiles)
    if cid:
        summary = pubchem_service.bioassay_summary(cid)
        pubchem = {"available": True, **summary}
    else:
        notes.append("Sin coincidencia en PubChem para esta estructura.")

    return {"smiles": smiles, "chembl": chembl, "pubchem": pubchem, "notes": notes}


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def drug_bioactivity_view(request, drug_id: str):
    """GET /api/drugs/<drug_id>/bioactivity/ — bioactividad de un fármaco de la base."""
    drug_id = drug_id.strip().upper()
    db = get_db()
    doc = _find_drug(db, drug_id)
    if not doc:
        return Response({"error": f"Fármaco {drug_id} no encontrado."},
                        status=status.HTTP_404_NOT_FOUND)

    smiles = _smiles_from_doc(doc)
    if not smiles:
        return Response({
            "drug": {"drugbank_id": drug_id, "name": doc.get("name", drug_id)},
            "available": False,
            "notes": ["Este fármaco no tiene SMILES (p.ej. biotecnológico); no hay bioactividad estructural."],
        })

    notes: list = []
    profile = _build_profile(smiles, notes)
    return Response({
        "drug": {"drugbank_id": drug_id, "name": doc.get("name", drug_id)},
        "available": True,
        **profile,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sandbox_bioactivity_view(request):
    """POST /api/drugs/sandbox/bioactivity/ — bioactividad de un compuesto (body {smiles})."""
    smiles = (request.data.get("smiles") or "").strip()
    if not smiles:
        return Response({"error": "El campo 'smiles' es obligatorio."}, status=400)
    if len(smiles) > MAX_SMILES_LENGTH:
        return Response({"error": f"SMILES demasiado largo (máx. {MAX_SMILES_LENGTH})."}, status=400)

    notes: list = []
    profile = _build_profile(smiles, notes)
    return Response({"available": True, **profile})
