import re

from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from config.services.mongo import get_db

# DrugGraph Open usa IDs abiertos (por defecto 'DC<struct_id>' de DrugCentral). El
# validador se construye desde OPEN_ID_PREFIX y admite dígitos de longitud variable.
# Se conservan los prefijos legacy (DB/BTD/BIOD) por si se cargan cross-refs de DrugBank.
_OPEN_PREFIX = re.escape(getattr(settings, 'OPEN_ID_PREFIX', 'DC'))
_DRUGBANK_ID_RE = re.compile(rf'^({_OPEN_PREFIX}|DB|BTD|BIOD)\d+$')


def _find_drug(db, drug_id: str):
    """Busca un fármaco por drugbank-id (string simple o campo anidado con .value)."""
    doc = db.drugs.find_one(
        {'drugbank-id': drug_id},
        {'name': 1, 'drug-interactions': 1}
    )
    if not doc:
        doc = db.drugs.find_one(
            {'drugbank-id.value': drug_id},
            {'name': 1, 'drug-interactions': 1}
        )
    return doc


def _serialize_interactions(raw: list) -> list:
    return [
        {
            'drugbank_id': item.get('drugbank-id', ''),
            'name':        item.get('name', ''),
            'description': item.get('description'),
        }
        for item in raw
        if item.get('drugbank-id') or item.get('name')
    ]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ddi_check_view(request):
    """
    GET /api/drugs/ddi/?drug_a=DB00945
      → Devuelve todas las DDIs del fármaco A desde MongoDB.

    GET /api/drugs/ddi/?drug_a=DB00945&drug_b=DB00788
      → Verifica si existe interacción entre A y B.
    """
    drug_a_id = request.GET.get('drug_a', '').strip().upper()
    drug_b_id = request.GET.get('drug_b', '').strip().upper()

    if not drug_a_id:
        return JsonResponse({'error': 'El parámetro drug_a es obligatorio'}, status=400)
    _example = f'{settings.OPEN_ID_PREFIX}1234'
    if not _DRUGBANK_ID_RE.match(drug_a_id):
        return JsonResponse({'error': f'Formato de ID inválido: {drug_a_id}. Esperado: {_example}'}, status=400)
    if drug_b_id and not _DRUGBANK_ID_RE.match(drug_b_id):
        return JsonResponse({'error': f'Formato de ID inválido: {drug_b_id}. Esperado: {_example}'}, status=400)

    db = get_db()
    doc_a = _find_drug(db, drug_a_id)
    if not doc_a:
        return JsonResponse(
            {'error': f'Fármaco {drug_a_id} no encontrado en la base de datos'},
            status=404
        )

    drug_a_name  = doc_a.get('name', drug_a_id)
    raw_list     = doc_a.get('drug-interactions', []) or []
    interactions = _serialize_interactions(raw_list)

    # ── Modo PAR: verificar interacción A ↔ B ────────────────────────────────
    if drug_b_id:
        doc_b = _find_drug(db, drug_b_id)
        if not doc_b:
            return JsonResponse(
                {'error': f'Fármaco {drug_b_id} no encontrado en la base de datos'},
                status=404
            )
        drug_b_name = doc_b.get('name', drug_b_id)

        found = next(
            (i for i in interactions if i['drugbank_id'] == drug_b_id),
            None
        )

        return JsonResponse({
            'mode':        'pair',
            'drug_a':      {'drugbank_id': drug_a_id, 'name': drug_a_name},
            'drug_b':      {'drugbank_id': drug_b_id, 'name': drug_b_name},
            'interacts':   found is not None,
            'description': found['description'] if found else None,
        })

    # ── Modo SINGLE: todas las DDIs del fármaco A ─────────────────────────────
    return JsonResponse({
        'mode':              'single',
        'drug':              {'drugbank_id': drug_a_id, 'name': drug_a_name},
        'interaction_count': len(interactions),
        'interactions':      interactions,
    })
