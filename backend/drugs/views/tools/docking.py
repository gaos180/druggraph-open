"""
docking.py — Cribado estructural por docking con AutoDock Vina (Tier 5.3).

GET  /api/tools/docking/targets/   → receptores preparados disponibles.
POST /api/tools/docking/           → body { smiles | drug_id, target, exhaustiveness? }
                                     acopla el ligando al receptor → afinidad (kcal/mol) + poses.

Requiere vina + meeko + openbabel + un receptor preparado (scripts/prepare_receptor.py).
Degrada con 503 si faltan deps o el receptor.
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.services import docking_service

log = logging.getLogger(__name__)

MAX_SMILES = 500


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def docking_targets_view(request):
    if not docking_service.DOCKING_OK:
        return Response({"available": False, "targets": [],
                         "error": "Docking no disponible (instala vina + meeko + openbabel)."}, status=503)
    return Response({"available": True, "targets": docking_service.list_targets()})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def docking_screen_view(request, target: str):
    """Resultados del cribado batch de una diana (ranking por afinidad), si se corrió."""
    if not docking_service.DOCKING_OK:
        return Response({"available": False, "results": []}, status=503)
    try:
        limit = int(request.GET.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    results = docking_service.screen_results(target.strip(), limit=limit)
    return Response({"available": True, "target": target, "results": results})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def docking_view(request):
    if not docking_service.DOCKING_OK:
        return Response({"available": False,
                         "error": "Docking no disponible (instala vina + meeko + openbabel)."}, status=503)

    target = (request.data.get("target") or "").strip()
    if not target:
        return Response({"error": "Falta 'target' (receptor preparado)."}, status=400)
    try:
        exhaustiveness = max(1, min(int(request.data.get("exhaustiveness", 8)), 32))
    except (TypeError, ValueError):
        exhaustiveness = 8

    drug_id = (request.data.get("drug_id") or "").strip()
    smiles = (request.data.get("smiles") or "").strip()
    try:
        if drug_id:
            result = docking_service.dock_for_drug(drug_id, target, exhaustiveness=exhaustiveness)
        elif smiles and len(smiles) <= MAX_SMILES:
            result = docking_service.dock(smiles, target, exhaustiveness=exhaustiveness)
        else:
            return Response({"error": "Se requiere 'smiles' o 'drug_id'."}, status=400)
    except Exception as exc:
        log.error("docking_view error: %s", exc)
        return Response({"error": "Error en el docking."}, status=500)

    if not result.get("available"):
        return Response(result, status=503)
    return Response(result)
