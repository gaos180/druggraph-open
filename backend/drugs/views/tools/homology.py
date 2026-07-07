"""
homology.py — Homología de dianas entre especies (Tier 6, uso veterinario).

GET  /api/tools/homology/species/   → especies disponibles (perro, gato, caballo, vaca…).
POST /api/tools/homology/           → body { drug_id | genes:[...], species:[organism_id,...] }
    → % de identidad de cada diana en las especies elegidas + veredicto (¿el fármaco funcionaría?).

Requiere biopython. Degrada con 503 si falta.
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.services import homology_service

log = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def homology_species_view(request):
    if not homology_service.BIO_OK:
        return Response({"available": False, "species": [], "error": "biopython no disponible."}, status=503)
    return Response({"available": True, "species": homology_service.SPECIES})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def homology_view(request):
    if not homology_service.BIO_OK:
        return Response({"available": False, "error": "biopython no disponible (Tier homología)."}, status=503)

    species = request.data.get("species") or []
    try:
        species_ids = [int(x) for x in species][:11]
    except (TypeError, ValueError):
        species_ids = []

    drug_id = (request.data.get("drug_id") or "").strip()
    genes = request.data.get("genes") or []
    try:
        if drug_id:
            result = homology_service.homology_for_drug(drug_id, species_ids)
        elif isinstance(genes, list) and genes:
            result = homology_service.conservation([str(g) for g in genes][:8], species_ids)
        else:
            return Response({"error": "Se requiere 'drug_id' o 'genes' (lista)."}, status=400)
    except Exception as exc:
        log.error("homology_view error: %s", exc)
        return Response({"error": "Error en el análisis de homología."}, status=500)

    return Response(result, status=200 if result.get("available") else 503)
