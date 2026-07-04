import re
import logging
from bson import ObjectId
from config.services.mongo import get_db

# ---------------------------------------------------------------------------
# Proyección para LISTADO — solo campos planos y livianos
# Se excluyen explícitamente todos los arrays anidados pesados
# ---------------------------------------------------------------------------
LIST_PROJECTION = {
    '_id': 1,
    'name': 1,
    'type': 1,
    'groups': 1,           # array simple de strings como ["approved", "investigational"]
    'description': 1,
    'drugbank-id': 1,
    'average-mass': 1,
    'unii': 1,
}

# Campos excluidos del detalle (comentados los que sí se usan en la UI modular)
DETAIL_EXCLUDE = {
    # 'general-references': 0,        <- Habilitados para tus componentes
    # 'snp-adverse-drug-reactions': 0,  <- Habilitados para tus componentes
    # 'snp-effects': 0,                 <- Habilitados para tus componentes
    # 'products': 0,                    <- Habilitados para tus componentes
    # 'prices': 0,                      <- Habilitados para tus componentes
    'patents': 0,
    'mixtures': 0,
    'packagers': 0,
    'manufacturers': 0,
}

# Topes de seguridad
MAX_RESULTS_PER_PAGE = 20
MAX_SEARCH_LENGTH = 80    # Evita regex enormes
CURSOR_BATCH_SIZE = 25    # N+1 para detectar página siguiente sin count_documents
CURSOR_TIMEOUT_MS = 8000  # 8 segundos máximo por query

def _serialize(doc: dict) -> dict:
    if doc and '_id' in doc:
        doc['_id'] = str(doc['_id'])
    return doc

def get_smiles(drug: dict) -> str | None:
    """Extrae SMILES de calculated-properties (solo para vista de detalle)."""
    props = drug.get('calculated-properties') or []
    for p in props:
        if isinstance(p, dict) and p.get('kind') == 'SMILES':
            return p.get('value')
    return None

def _build_search_query(search: str, drug_type: str, group: str) -> dict:
    """
    Construye la query de MongoDB inyectando la lógica de búsqueda inteligente:
    - Detecta automáticamente estructuras SMILES.
    - Busca por nombre, IDs y sinónimos internacionales de forma insensible a mayúsculas.
    """
    query: dict = {}
    
    if search:
        s_clean = search[:MAX_SEARCH_LENGTH].strip()
        
        # 1. ¿Es una estructura SMILES? 
        # Detecta patrones moleculares comunes o cadenas de caracteres químicos largos
        if any(char in s_clean for char in ['=', '(', ')', '[', ']', '#', '@', '\\', '/']) or len(s_clean) > 15:
            query['calculated-properties'] = {
                '$elemMatch': {
                    'kind': 'SMILES',
                    'value': {'$regex': re.escape(s_clean), '$options': 'i'}
                }
            }
        else:
            # 2. Búsqueda inteligente por Texto/Sinónimos (Tolerante a fallas ortográficas y parciales)
            escaped_term = re.escape(s_clean)
            regex_condition = {'$regex': escaped_term, '$options': 'i'}
            
            query['$or'] = [
                {'name': regex_condition},
                {'synonyms': regex_condition},  # Soporta buscar "Paracetamol" y mapear al documento
                {'synonyms.value': regex_condition}, # Por si vienen estructurados como objetos {value, language}
                {'drugbank-id': {'$regex': f'^{escaped_term}', '$options': 'i'}},
                {'cas-number': regex_condition}
            ]
        
    if drug_type:
        query['type'] = drug_type
    if group:
        query['groups'] = group

    return query


_SMILES_CHARS = ['=', '(', ')', '[', ']', '#', '@', '\\', '/']

def _is_word_search(s: str) -> bool:
    """
    True si el término conviene resolverlo con el índice de texto ($text) en vez
    del scan por regex: sin caracteres de SMILES, longitud razonable y alfabético.
    Las búsquedas por prefijo parcial corto siguen por regex (type-ahead).
    """
    if not s or len(s) < 3 or len(s) > 15:
        return False
    if any(c in s for c in _SMILES_CHARS):
        return False
    return any(c.isalpha() for c in s)

def list_drugs(
    search: str = '',
    drug_type: str = '',
    group: str = '',
    page: int = 1,
    per_page: int = MAX_RESULTS_PER_PAGE,
) -> dict:
    """
    Paginación sin count_documents optimizada con estrategia N+1.
    """
    search = (search or '').strip()
    per_page = min(per_page, MAX_RESULTS_PER_PAGE)
    page = max(1, page)

    db = get_db()
    query = _build_search_query(search, drug_type, group)

    # Fast-path: para búsquedas por palabra completa usa el índice de texto
    # ($text → IXSCAN, ms) en vez del scan por regex (~650 ms sobre 16k docs).
    # Si el índice no existe o no hay coincidencia exacta de palabra, conserva la
    # regex (que cubre prefijos parciales y sinónimos para el type-ahead).
    if search and _is_word_search(search) and '$or' in query:
        try:
            if db.drugs.find_one({'$text': {'$search': search}}, {'_id': 1}):
                query.pop('$or', None)
                query['$text'] = {'$search': search}
        except Exception as exc:
            logging.getLogger(__name__).debug('text-index probe falló, uso regex: %s', exc)

    skip = (page - 1) * per_page
    fetch = per_page + 1  # N+1

    try:
        cursor = (
            db.drugs
            .find(query, LIST_PROJECTION)
            .skip(skip)
            .limit(fetch)
            .batch_size(CURSOR_BATCH_SIZE)
            .max_time_ms(CURSOR_TIMEOUT_MS)
            .allow_disk_use(False)   
        )

        docs = []
        for doc in cursor:
            docs.append(_serialize(doc))
            if len(docs) >= fetch:
                break
                
    except Exception as exc:
        logging.getLogger(__name__).error('list_drugs cursor error: %s', exc)
        return _empty_page(page, per_page)

    has_next = len(docs) > per_page
    results = docs[:per_page]          

    return {
        'page': page,
        'per_page': per_page,
        'has_next': has_next,
        'has_prev': page > 1,
        'results': results,
    }

def get_drug(drug_id: str) -> dict | None:
    """Devuelve un fármaco completo por _id de Mongo o por drugbank-id."""
    db = get_db()
    try:
        # Intenta buscar por ObjectId primero
        try:
            query_id = ObjectId(drug_id)
            doc = db.drugs.find_one({'_id': query_id}, DETAIL_EXCLUDE)
        except Exception:
            doc = None
            
        # Si no es un ObjectId válido o no se encontró, busca por drugbank-id
        if not doc:
            doc = db.drugs.find_one({'drugbank-id': drug_id}, DETAIL_EXCLUDE)
            
        if not doc:
            # Búsqueda secundaria por si viene dentro de la lista de objetos de IDs de DrugBank
            doc = db.drugs.find_one({'drugbank-id.value': drug_id}, DETAIL_EXCLUDE)

        if not doc:
            return None
            
        doc = _serialize(doc)
        doc['smiles'] = get_smiles(doc)
        return doc
    except Exception as exc:
        logging.getLogger(__name__).error('get_drug error: %s', exc)
        return None

def get_drug_types() -> list[str]:
    return ["small molecule", "biotech"]

def get_drug_groups() -> list[str]:
    return ["approved", "investigational", "experimental", "withdrawn", "nutraceutical", "illicit", "vet_approved"]

def _empty_page(page: int, per_page: int) -> dict:
    return {
        'page': page,
        'per_page': per_page,
        'has_next': False,
        'has_prev': page > 1,
        'results': [],
    }