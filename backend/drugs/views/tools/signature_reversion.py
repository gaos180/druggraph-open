"""
signature_reversion.py — Reversión de firma transcriptómica (LINCS L1000) — Tier 3.1.

POST /api/tools/signature-reversion/
    body: { up_genes: [str], dn_genes: [str], reverse?: bool }
    → fármacos que revierten (o imitan) la firma dada, con score de conectividad.
Se conecta de forma natural con la herramienta DEG (genes al alza/baja significativos).
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.services.lincs_service import signature_reversion

log = logging.getLogger(__name__)

MAX_GENES = 200


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def signature_reversion_view(request):
    data = request.data
    up = [str(g).strip() for g in (data.get("up_genes") or []) if str(g).strip()][:MAX_GENES]
    dn = [str(g).strip() for g in (data.get("dn_genes") or []) if str(g).strip()][:MAX_GENES]
    reverse = bool(data.get("reverse", True))

    if not up and not dn:
        return Response({"error": "Se requieren 'up_genes' y/o 'dn_genes'."}, status=400)

    try:
        result = signature_reversion(up, dn, reverse=reverse)
    except Exception as exc:
        log.error("signature_reversion_view error: %s", exc)
        return Response({"error": "Error consultando LINCS."}, status=502)

    if not result.get("available"):
        return Response(result, status=502 if result.get("reason", "").startswith("Error") else 200)
    return Response(result)
