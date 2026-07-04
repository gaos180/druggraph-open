"""
uniprot_service.py — Cliente UniProt REST API con caché en MongoDB (30 días).

La caché persiste entre reinicios del servidor.  Cuando un accession no está
en la BD (o expiró), se llama a la API de UniProt y se guarda en la colección
`uniprot_cache` de MongoDB.

Correr `populate_uniprot.py` una vez para pre-cargar todos los targets.
"""

import time
import logging
import requests

log = logging.getLogger(__name__)

UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
CACHE_TTL    = 86_400 * 30   # 30 días

# Caché en memoria (L1): evita viajes a MongoDB en requests repetidos
_mem_cache:  dict[str, dict]  = {}
_mem_times:  dict[str, float] = {}
_MEM_TTL = 3600  # 1 h en memoria; luego releer de MongoDB

_SUBLOC_ICONS: dict[str, str] = {
    'nucleus':          '🔵',
    'cytoplasm':        '🟡',
    'mitochondr':       '🟠',
    'membrane':         '🟣',
    'endoplasmic':      '🟤',
    'golgi':            '🔴',
    'lysosome':         '⚪',
    'peroxisome':       '🟢',
    'secreted':         '⬆️',
    'extracellular':    '⬆️',
    'cell surface':     '🔷',
    'plasma membrane':  '🔷',
    'endosome':         '🔸',
    'autophagosome':    '♻️',
    'ribosome':         '🟥',
}


def _subloc_icon(loc_name: str) -> str:
    lower = loc_name.lower()
    for key, icon in _SUBLOC_ICONS.items():
        if key in lower:
            return icon
    return '📍'


# ── Caché MongoDB (L2) ────────────────────────────────────────────────────────

def _mongo_get(accession: str):
    """Devuelve los datos parseados del accession si están en MongoDB y vigentes."""
    try:
        from config.services.mongo import get_db
        db  = get_db()
        doc = db.uniprot_cache.find_one({'_id': accession})
        if doc and (time.time() - doc.get('cached_at', 0)) < CACHE_TTL:
            return doc.get('parsed')
    except Exception as exc:
        log.debug("MongoDB uniprot_cache read error: %s", exc)
    return None


def _mongo_set(accession: str, parsed: dict):
    """Guarda los datos parseados en MongoDB."""
    try:
        from config.services.mongo import get_db
        db = get_db()
        db.uniprot_cache.replace_one(
            {'_id': accession},
            {'_id': accession, 'parsed': parsed, 'cached_at': time.time()},
            upsert=True,
        )
    except Exception as exc:
        log.debug("MongoDB uniprot_cache write error: %s", exc)


# ── Fetch UniProt ─────────────────────────────────────────────────────────────

def _fetch_uniprot(accession: str):
    """Llama a UniProt REST API; devuelve el JSON crudo o None."""
    try:
        r = requests.get(
            f"{UNIPROT_BASE}/{accession}.json",
            timeout=10,
            headers={"Accept": "application/json"},
        )
        if r.status_code == 200:
            return r.json()
        log.warning("UniProt %s: HTTP %s", accession, r.status_code)
    except Exception as exc:
        log.warning("UniProt fetch error for %s: %s", accession, exc)
    return None


# ── Punto de entrada principal ────────────────────────────────────────────────

def get_uniprot_entry(accession: str):
    """
    Devuelve los datos *parseados* de UniProt para el accession dado.

    Orden de consulta:
      1. Caché en memoria (1 h TTL)
      2. MongoDB `uniprot_cache` (30 días TTL)
      3. UniProt REST API → guarda en MongoDB y en memoria
    """
    now = time.time()

    # L1: memoria
    if accession in _mem_cache and now - _mem_times.get(accession, 0) < _MEM_TTL:
        return _mem_cache[accession]

    # L2: MongoDB
    parsed = _mongo_get(accession)
    if parsed:
        _mem_cache[accession]  = parsed
        _mem_times[accession]  = now
        return parsed

    # L3: API
    raw = _fetch_uniprot(accession)
    if not raw:
        return None

    try:
        parsed = parse_protein_details(raw)
    except Exception as exc:
        log.error("parse_protein_details error for %s: %s", accession, exc, exc_info=True)
        return None

    _mem_cache[accession] = parsed
    _mem_times[accession] = now
    _mongo_set(accession, parsed)
    return parsed


# ── Parser ────────────────────────────────────────────────────────────────────

def parse_protein_details(data: dict) -> dict:
    """Extrae campos relevantes de la respuesta JSON de UniProt."""

    def _text(obj) -> str:
        if isinstance(obj, dict):
            return obj.get('value', '')
        return str(obj) if obj is not None else ''

    result: dict = {
        'accession':             data.get('primaryAccession', ''),
        'protein_name':          '',
        'alternative_names':     [],
        'gene_names':            [],
        'organism':              {},
        'function':              '',
        'activity_regulation':   '',
        'subunit':               '',
        'subcellular_locations': [],
        'ptm':                   '',
        'sequence':              {},
        'keywords':              [],
        'go_terms':              [],
        'pdb_ids':               [],
        'reviewed': data.get('entryType', '') == 'UniProtKB reviewed (Swiss-Prot)',
    }

    # Nombre de la proteína
    pd  = data.get('proteinDescription', {})
    rec = pd.get('recommendedName', {})
    if rec:
        result['protein_name'] = _text(rec.get('fullName', {}))
    else:
        subs = pd.get('submissionNames', [])
        if subs:
            result['protein_name'] = _text(subs[0].get('fullName', {}))

    # Nombres alternativos (nivel proteinDescription, no dentro de recommendedName)
    for alt in pd.get('alternativeNames', []):
        name = _text(alt.get('fullName', {}))
        if name:
            result['alternative_names'].append(name)

    # Genes
    for g in data.get('genes', []):
        name = _text(g.get('geneName', {}))
        if name:
            result['gene_names'].append(name)

    # Organismo
    org = data.get('organism', {})
    result['organism'] = {
        'scientific': org.get('scientificName', ''),
        'taxon_id':   org.get('taxonId', 0),
    }

    # Comments
    for c in data.get('comments', []):
        ctype = c.get('commentType', '')
        texts = c.get('texts', [])

        if ctype == 'FUNCTION' and not result['function']:
            result['function'] = _text(texts[0]) if texts else ''

        elif ctype == 'ACTIVITY REGULATION' and not result['activity_regulation']:
            result['activity_regulation'] = _text(texts[0]) if texts else ''

        elif ctype == 'SUBUNIT' and not result['subunit']:
            result['subunit'] = _text(texts[0]) if texts else ''

        elif ctype == 'PTM' and not result['ptm']:
            result['ptm'] = _text(texts[0]) if texts else ''

        elif ctype == 'SUBCELLULAR LOCATION':
            for sloc in c.get('subcellularLocations', []):
                loc  = sloc.get('location', {})
                topo = sloc.get('topology', {})
                val  = _text(loc)
                sl_id = loc.get('id', '') if isinstance(loc, dict) else ''
                if val:
                    result['subcellular_locations'].append({
                        'value':    val,
                        'topology': _text(topo) if topo else '',
                        'icon':     _subloc_icon(val),
                        'sl_id':    sl_id,
                    })

    # Deduplicar localizaciones
    seen_locs: set = set()
    unique_locs = []
    for loc in result['subcellular_locations']:
        if loc['value'] not in seen_locs:
            seen_locs.add(loc['value'])
            unique_locs.append(loc)
    result['subcellular_locations'] = unique_locs

    # Secuencia
    seq = data.get('sequence', {})
    result['sequence'] = {
        'length':   seq.get('length', 0),
        'mass':     seq.get('molWeight', 0),
        'checksum': seq.get('crc64', ''),
        'first_50': (seq.get('value', '') or '')[:50],
    }

    # Keywords
    result['keywords'] = [
        kw.get('name', '') for kw in data.get('keywords', [])[:20]
        if kw.get('name')
    ]

    # GO terms + PDB IDs
    for xref in data.get('uniProtKBCrossReferences', []):
        db_name = xref.get('database', '')
        if db_name == 'GO':
            props    = {p.get('key', ''): p.get('value', '') for p in xref.get('properties', [])}
            go_term  = props.get('GoTerm', '')
            go_aspect = props.get('GoAspect', '')
            if go_term:
                result['go_terms'].append({
                    'id':     xref.get('id', ''),
                    'term':   go_term.split(':', 1)[-1].strip() if ':' in go_term else go_term,
                    'aspect': go_aspect,
                })
        elif db_name == 'PDB':
            xref_id = xref.get('id', '')
            if xref_id:
                result['pdb_ids'].append(xref_id)

    result['pdb_ids'] = result['pdb_ids'][:10]

    return result
