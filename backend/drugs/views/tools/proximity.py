"""
proximity.py — Proximidad de red entre dos fármacos (network medicine, Tier 1.3).

GET /api/tools/proximity/?drug_a=DB..&drug_b=DB..
    → distancia d_c en el interactoma STRING entre los módulos de dianas de ambos
      fármacos. Menor d_c ⇒ módulos más cercanos ⇒ posible relación funcional.
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.services.proximity_service import closest_proximity, ProximityUnavailable
from ._common import _get_drug_targets, _get_drug_info

log = logging.getLogger(__name__)


def _drug_genes(drug_id: str) -> list[str]:
    return sorted({t["gene_name"].upper() for t in _get_drug_targets(drug_id) if t.get("gene_name")})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def proximity_view(request):
    drug_a = request.GET.get("drug_a", "").strip().upper()
    drug_b = request.GET.get("drug_b", "").strip().upper()
    if not drug_a or not drug_b:
        return Response({"error": "Se requieren 'drug_a' y 'drug_b'."}, status=400)

    genes_a = _drug_genes(drug_a)
    genes_b = _drug_genes(drug_b)
    if not genes_a or not genes_b:
        return Response({"error": "Uno de los fármacos no tiene genes diana en la red."}, status=404)

    try:
        result = closest_proximity(genes_a, genes_b)
    except ProximityUnavailable as exc:
        return Response({"error": str(exc), "available": False}, status=503)
    except Exception as exc:
        log.error("proximity_view error: %s", exc)
        return Response({"error": "Error calculando la proximidad de red."}, status=500)

    return Response({
        "drug_a": _get_drug_info(drug_a),
        "drug_b": _get_drug_info(drug_b),
        "genes_a": genes_a,
        "genes_b": genes_b,
        **result,
    })
