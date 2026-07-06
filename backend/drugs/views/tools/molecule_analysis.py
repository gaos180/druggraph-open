"""
molecule_analysis.py — Análisis molecular integral (panel tipo sandbox).

POST /api/tools/molecule-analysis/
    body: { smiles | drug_id }
    → propiedades + vecinos + espacio químico + pharmacóforo + ADMET + toxicidad + dianas
      predichas + repurposing, en una sola respuesta (cada sección degrada por separado).

El docking es aparte (extra opcional, POST /api/tools/docking/).
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.services import molecule_analysis_service

log = logging.getLogger(__name__)
MAX_LEN = 600


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def molecule_analysis_view(request):
    query = (request.data.get("smiles") or request.data.get("drug_id") or "").strip()
    if not query or len(query) > MAX_LEN:
        return Response({"error": "Se requiere 'smiles' o 'drug_id' (≤ 600 caracteres)."}, status=400)
    try:
        result = molecule_analysis_service.build(query)
    except Exception as exc:
        log.error("molecule_analysis_view error: %s", exc)
        return Response({"error": "Error en el análisis molecular."}, status=500)
    if not result.get("available"):
        return Response(result, status=400)
    return Response(result)
