"""
blast.py — Endpoint Django para búsqueda por homología de secuencia.

Registrar en drugs/urls.py:

    from .blast import blast_search_view
    path('blast/search/', blast_search_view, name='blast-search'),

settings.py necesita:
    BLAST_DB_PATH  = "/ruta/absoluta/blast_db/druggraph_targets"
    BLAST_MAP_PATH = "/ruta/absoluta/blast_db/druggraph_targets.map.json"
    BLAST_THREADS  = 2   # opcional, default 2
"""

import logging

from django.http import JsonResponse
from rest_framework.decorators import api_view

from config.services.blast_service import (
    blast_search,
    DEFAULT_MAX_HITS,
    DEFAULT_EVALUE,
    MAX_SEQUENCE_LENGTH,
)

log = logging.getLogger(__name__)


@api_view(['POST'])
def blast_search_view(request):
    """
    POST /api/blast/search/

    Body JSON:
        {
            "sequence":     str,        // requerido — secuencia AA o FASTA
            "max_hits":     int,        // opcional, default 50, máx 200
            "evalue":       float,      // opcional, default 1e-3
            "organism":     str,        // opcional — filtra por organismo exacto
            "min_identity": float       // opcional — % identidad mínima (0–100)
        }

    Respuesta 200:
        {
            "query_length": int,
            "hit_count":    int,
            "hits": [ { target, alignment, drugs } ],
            "organisms": [str]
        }

    Errores:
        400 — secuencia ausente/inválida.
        503 — BLAST+ no instalado, índice no construido, o Neo4j caído.
    """
    body = request.data  # DRF ya parsea el JSON

    sequence = body.get("sequence") or ""
    if not sequence.strip():
        return JsonResponse({"error": "El campo 'sequence' es obligatorio."}, status=400)

    # Parámetros opcionales con saneo de tipos
    try:
        max_hits = int(body.get("max_hits", DEFAULT_MAX_HITS))
    except (TypeError, ValueError):
        max_hits = DEFAULT_MAX_HITS

    try:
        evalue = float(body.get("evalue", DEFAULT_EVALUE))
    except (TypeError, ValueError):
        evalue = DEFAULT_EVALUE

    try:
        min_identity = float(body.get("min_identity", 0.0))
    except (TypeError, ValueError):
        min_identity = 0.0

    organism = (body.get("organism") or "").strip() or None

    try:
        result = blast_search(
            raw_sequence=sequence,
            max_hits=max_hits,
            evalue=evalue,
            organism_filter=organism,
            min_identity=min_identity,
        )
    except ValueError as exc:
        # Secuencia inválida
        return JsonResponse({"error": str(exc)}, status=400)
    except RuntimeError as exc:
        # BLAST no instalado / índice ausente / timeout
        log.error("blast_search_view runtime error: %s", exc)
        return JsonResponse({"error": str(exc)}, status=503)
    except Exception as exc:
        log.error("blast_search_view error: %s", exc)
        return JsonResponse(
            {"error": "Error interno en la búsqueda por secuencia."}, status=500
        )

    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})
