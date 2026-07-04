import logging

from django.http import JsonResponse
from bson import ObjectId
from rest_framework.decorators import api_view
from ..services import list_drugs, get_drug, get_drug_types, get_drug_groups
from config.services.mongo import get_db
from ._helpers import _is_admin

log = logging.getLogger(__name__)


def _resolve_drug_doc(drug_id: str):
    """Resuelve un drug_id (ObjectId o DrugBank ID) al documento mínimo de MongoDB."""
    db = get_db()
    try:
        doc = db.drugs.find_one({'_id': ObjectId(drug_id)}, {'_id': 1, 'name': 1, 'drugbank-id': 1})
    except Exception:
        doc = None
    if not doc:
        doc = db.drugs.find_one({'drugbank-id': drug_id}, {'_id': 1, 'name': 1, 'drugbank-id': 1})
    if not doc:
        doc = db.drugs.find_one({'drugbank-id.value': drug_id}, {'_id': 1, 'name': 1, 'drugbank-id': 1})
    return doc


@api_view(['GET'])
def drug_filters_view(request):
    try:
        types = get_drug_types()
        groups = get_drug_groups()
        return JsonResponse({'types': types, 'groups': groups})
    except Exception as e:
        log.error('drug_filters_view error: %s', e, exc_info=True)
        return JsonResponse({'error': 'Error al obtener filtros'}, status=500)


@api_view(['GET', 'POST'])
def list_drugs_view(request):
    if request.method == 'GET':
        try:
            search_param    = request.GET.get('search', '')
            drug_type_param = request.GET.get('drug_type', '')
            group_param     = request.GET.get('group', '')
            page_param      = int(request.GET.get('page', 1))
            response_data = list_drugs(
                search=search_param,
                drug_type=drug_type_param,
                group=group_param,
                page=page_param,
            )
            return JsonResponse(response_data)
        except Exception as e:
            log.error('list_drugs_view error: %s', e, exc_info=True)
            return JsonResponse({'error': 'Error al listar fármacos'}, status=500)

    # POST — solo admin
    if not _is_admin(request):
        return JsonResponse({'error': 'Solo administradores.'}, status=403)

    data = request.data
    name       = (data.get('name') or '').strip()
    drugbank_id = (data.get('drugbank_id') or '').strip()
    if not name or not drugbank_id:
        return JsonResponse({'error': 'name y drugbank_id son obligatorios.'}, status=400)

    db = get_db()
    if db.drugs.find_one({'drugbank-id': drugbank_id}, {'_id': 1}):
        return JsonResponse({'error': f'Ya existe un fármaco con DrugBank ID {drugbank_id}.'}, status=409)

    doc = {
        'name':        name,
        'type':        data.get('type', 'small molecule'),
        'groups':      data.get('groups', []),
        'description': data.get('description', ''),
        'drugbank-id': drugbank_id,
    }
    result = db.drugs.insert_one(doc)

    try:
        from config.services.neo4j_service import get_driver
        with get_driver().session() as session:
            session.run(
                "MERGE (d:Drug {drugbank_id: $dbid}) "
                "SET d.name = $name, d.type = $type, d.groups = $groups",
                dbid=drugbank_id, name=name,
                type=doc['type'], groups=doc['groups'],
            )
    except Exception as e:
        log.warning('No se pudo crear nodo Neo4j para %s: %s', drugbank_id, e)

    return JsonResponse({'ok': True, '_id': str(result.inserted_id)}, status=201)


@api_view(['GET', 'PATCH', 'DELETE'])
def drug_detail(request, drug_id):
    if request.method == 'GET':
        try:
            drug = get_drug(drug_id)
            if not drug:
                return JsonResponse({'error': 'Fármaco no encontrado'}, status=404)
            return JsonResponse(drug)
        except Exception as e:
            log.error('drug_detail GET error for %s: %s', drug_id, e, exc_info=True)
            return JsonResponse({'error': 'Error al obtener fármaco'}, status=500)

    # PATCH / DELETE — solo admin
    if not _is_admin(request):
        return JsonResponse({'error': 'Solo administradores.'}, status=403)

    doc = _resolve_drug_doc(drug_id)
    if not doc:
        return JsonResponse({'error': 'Fármaco no encontrado.'}, status=404)

    db = get_db()

    if request.method == 'PATCH':
        allowed = {'name', 'groups', 'type', 'description'}
        data = {k: v for k, v in request.data.items() if k in allowed}
        if not data:
            return JsonResponse({'error': 'Sin campos válidos para actualizar.'}, status=400)
        db.drugs.update_one({'_id': doc['_id']}, {'$set': data})
        return JsonResponse({'ok': True})

    # DELETE
    dbid = doc.get('drugbank-id')
    if isinstance(dbid, list):
        dbid = next((d.get('value') if isinstance(d, dict) else d for d in dbid), None)
    db.drugs.delete_one({'_id': doc['_id']})
    if dbid:
        try:
            from config.services.neo4j_service import get_driver
            with get_driver().session() as session:
                session.run("MATCH (d:Drug {drugbank_id: $dbid}) DETACH DELETE d", dbid=dbid)
        except Exception as e:
            log.warning('No se pudo eliminar nodo Neo4j para %s: %s', dbid, e)
    return JsonResponse({'ok': True})