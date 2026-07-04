"""
disease_evidence.py — Evidencia diana→enfermedad (Open Targets) — Tier 2.1.

GET /api/tools/disease-evidence/<drug_id>/
    → enfermedades asociadas al módulo de dianas del fármaco, con score integrado
      de Open Targets. Hipótesis diana→enfermedad para reposicionamiento.
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.services.opentargets_service import diseases_for_genes
from ._common import _get_drug_targets, _get_drug_info

log = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def disease_evidence_view(request, drug_id: str):
    drug_id = drug_id.strip().upper()
    genes = sorted({t["gene_name"].upper() for t in _get_drug_targets(drug_id) if t.get("gene_name")})
    if not genes:
        return Response({"error": "Fármaco sin genes diana en la red."}, status=404)

    try:
        result = diseases_for_genes(genes)
    except Exception as exc:
        log.error("disease_evidence_view error: %s", exc)
        return Response({"error": "Error consultando Open Targets."}, status=502)

    return Response({"drug": _get_drug_info(drug_id), "genes": genes, **result})
