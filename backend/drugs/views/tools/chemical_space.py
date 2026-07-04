"""
chemical_space.py — Mapa 2D del espacio químico (Tier 4.1).

GET  /api/tools/chemical-space/         → nube de puntos (UMAP+HDBSCAN) + resumen por cluster.
POST /api/tools/chemical-space/locate/  body: { smiles } → ubica una molécula nueva en el mapa.

Requiere umap-learn + hdbscan + la nube construida con scripts/build_chemical_space.py
(y torch+transformers para 'locate'). Degrada con 503 si falta el modelo/nube.
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.services import chemical_space_service

log = logging.getLogger(__name__)

MAX_SMILES_LENGTH = 500


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chemical_space_view(request):
    if not chemical_space_service.SPACE_OK:
        return Response(
            {"error": "Mapa de espacio químico no disponible (instala umap-learn + hdbscan).",
             "available": False},
            status=503,
        )
    try:
        result = chemical_space_service.load_points()
    except Exception as exc:
        log.error("chemical_space_view error: %s", exc)
        return Response({"error": "Error leyendo el mapa de espacio químico."}, status=500)

    if not result.get("available"):
        return Response(
            {"error": "Mapa no construido. Ejecuta scripts/build_chemical_space.py.",
             "available": False},
            status=503,
        )
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chemical_space_locate_view(request):
    if not chemical_space_service.SPACE_OK:
        return Response(
            {"error": "Mapa de espacio químico no disponible (instala umap-learn + hdbscan).",
             "available": False},
            status=503,
        )

    smiles = (request.data.get("smiles") or "").strip()
    if not smiles or len(smiles) > MAX_SMILES_LENGTH:
        return Response({"error": "El campo 'smiles' es obligatorio y ≤ 500 caracteres."}, status=400)

    try:
        result = chemical_space_service.locate(smiles)
    except Exception as exc:
        log.error("chemical_space_locate_view error: %s", exc)
        return Response({"error": "Error ubicando la molécula en el mapa."}, status=500)

    if not result.get("available"):
        return Response(result, status=503)
    return Response(result)
