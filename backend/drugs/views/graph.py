"""
graph.py — Endpoint Django para el grafo de interacciones moleculares.

Registrar en drugs/urls.py:
    from .graph import drug_graph_view
    path('drugs/<str:drug_id>/graph/', drug_graph_view, name='drug-graph'),

O si usas el router de DRF, puedes importar directamente:
    path('api/drugs/<str:drug_id>/graph/', drug_graph_view),
"""

import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from neo4j import exceptions as neo4j_exc

# Ajusta la ruta según dónde coloques neo4j_service.py
from config.services.neo4j_service import get_drug_graph

log = logging.getLogger(__name__)


@require_GET
def drug_graph_view(request, drug_id: str):
    """
    GET /api/drugs/<drug_id>/graph/

    Parámetros:
        drug_id  (path)  — DrugBank ID (DB00001) o MongoDB _id del fármaco.
        name     (query) — Nombre alternativo para buscar en Neo4j si drug_id
                           no es un DB-id válido.

    Respuesta 200:
        {
          "drug":              { drugbank_id, name, type, groups },
          "interactions":      [ { rel_type, known_action, actions, role, target } ],
          "categories":        [ { name, mesh_id } ],
          "drug_interactions": [ { drugbank_id, name, description } ],
          "stats":             { total_interactions, total_categories, total_ddi, rel_type_counts }
        }
    """
    drug_id = drug_id.strip()

    # Determinar si drug_id parece un DrugBank ID (DBxxxxx / BTDxxxxx / BIODxxxxx)
    # vs. un MongoDB ObjectId hexadecimal de 24 caracteres
    is_dbid = (
        drug_id.upper().startswith("DB")   or
        drug_id.upper().startswith("BTD")  or
        drug_id.upper().startswith("BIOD")
    )

    drugbank_id = drug_id if is_dbid else None
    drug_name   = request.GET.get("name", "").strip() or None

    # Si no es un DB-id y no se pasa name, intenta con el id de todos modos
    # (puede ser que el usuario pase el drugbank_id como path param con otro formato)
    if not drugbank_id and not drug_name:
        drugbank_id = drug_id

    try:
        data = get_drug_graph(drugbank_id=drugbank_id, drug_name=drug_name)
    except neo4j_exc.ServiceUnavailable:
        return JsonResponse(
            {"error": "El servicio de grafo no está disponible en este momento."},
            status=503,
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        log.error("drug_graph_view error for %s: %s", drug_id, exc)
        return JsonResponse(
            {"error": "Error interno al consultar el grafo molecular."},
            status=500,
        )

    if not data:
        return JsonResponse(
            {"error": f"Fármaco '{drug_id}' no encontrado en el grafo."},
            status=404,
        )

    return JsonResponse(data, json_dumps_params={"ensure_ascii": False})
