"""
dossier.py — Informe integral de una molécula generado con IA (Gemini, estructura fija).

POST /api/tools/dossier/
    body: { smiles | drug_id, style? }
    → informe Markdown en secciones fijas (identidad, similitud, dianas+especies, cascada, rutas,
      enfermedades que afecta/podría tratar, fármacos relacionados) + los datos usados.

Requiere GEMINI_API_KEY. Degrada con 503 si Gemini/datos no están.
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.services import dossier_service

log = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def dossier_view(request):
    query = (request.data.get("smiles") or request.data.get("drug_id") or "").strip()
    style = (request.data.get("style") or "scientific").strip()
    if not query or len(query) > 600:
        return Response({"error": "Se requiere 'smiles' o 'drug_id' (≤ 600 caracteres)."}, status=400)
    try:
        result = dossier_service.build(query, style=style)
    except Exception as exc:
        log.error("dossier_view error: %s", exc)
        return Response({"error": "Error generando el informe."}, status=500)
    return Response(result, status=200 if result.get("available") else 503)
