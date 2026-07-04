"""
reports.py — Endpoints de la reportería IA (Gemini) de DrugGraph.

Genera informes en lenguaje natural a partir de cualquier análisis de la plataforma
(sandbox, reposicionamiento, toxicidad, DEG, DDI) y los guarda por usuario en Mongo.

    POST   /api/reports/generate/     — genera y persiste un informe
    GET    /api/reports/              — historial del usuario (ligero)
    GET    /api/reports/<report_id>/  — detalle (markdown completo)
    DELETE /api/reports/<report_id>/  — borrar del historial
"""

import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from config.services import gemini_service, report_service

log = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def report_generate_view(request):
    """
    POST /api/reports/generate/

    Body JSON:
        kind    : "sandbox" | "repurposing" | "toxicity" | "deg" | "ddi"   (requerido)
        payload : objeto con el resultado del análisis correspondiente       (requerido)
        style   : "scientific" | "executive"   (default "scientific")
        model   : "gemini-2.5-flash" | "gemini-2.5-pro"  (default flash)

    Respuesta 200: { report_id, kind, style, model, title, report_markdown, created_at }
    503 si Gemini no está configurado; 502 si la API falla; 400 si datos inválidos.
    """
    data = request.data
    kind = (data.get("kind") or "").strip()
    style = (data.get("style") or "scientific").strip()
    model = (data.get("model") or "").strip() or None
    payload = data.get("payload")

    try:
        result = report_service.build_report(
            kind,
            payload,
            style=style,
            model=model,
            user_id=str(request.user.id),
        )
    except report_service.ReportError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except gemini_service.GeminiUnavailable as exc:
        return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except gemini_service.GeminiError as exc:
        log.error("Gemini falló al generar informe: %s", exc)
        return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    except Exception as exc:
        log.error("report_generate_view error: %s", exc)
        return Response(
            {"error": "Error interno generando el informe."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(result)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def report_list_view(request):
    """GET /api/reports/ — historial del usuario (sin el cuerpo markdown)."""
    try:
        reports = report_service.list_reports(str(request.user.id))
    except Exception as exc:
        log.error("report_list_view error: %s", exc)
        return Response({"error": "Error consultando el historial."}, status=500)
    return Response({"reports": reports})


@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def report_detail_view(request, report_id: str):
    """
    GET    /api/reports/<report_id>/ — detalle con markdown completo.
    DELETE /api/reports/<report_id>/ — borra el informe del historial.
    """
    user_id = str(request.user.id)

    if request.method == "DELETE":
        try:
            deleted = report_service.delete_report(user_id, report_id)
        except Exception as exc:
            log.error("report_detail_view delete error: %s", exc)
            return Response({"error": "Error eliminando el informe."}, status=500)
        if not deleted:
            return Response({"error": "Informe no encontrado."}, status=404)
        return Response({"deleted": deleted})

    try:
        report = report_service.get_report(user_id, report_id)
    except Exception as exc:
        log.error("report_detail_view get error: %s", exc)
        return Response({"error": "Error consultando el informe."}, status=500)
    if not report:
        return Response({"error": "Informe no encontrado."}, status=404)
    return Response(report)
