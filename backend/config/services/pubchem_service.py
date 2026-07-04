"""
pubchem_service.py — Cliente de PubChem PUG-REST para bioactividad experimental.

PubChem aporta el COMPORTAMIENTO MEDIDO de un compuesto: en qué bioensayos resultó
activo o inactivo, contra qué diana y con qué actividad. Complementa la similitud
*predicha* (Tanimoto/targets) con evidencia *experimental*.

API base: https://pubchem.ncbi.nlm.nih.gov/rest/pug
Operaciones usadas:
    - compound/smiles/{SMILES}/cids/JSON      → resuelve SMILES a CID(s)
    - compound/cid/{CID}/assaysummary/JSON    → resumen de bioensayos del compuesto

Buenas prácticas PubChem:
    - Máx. ~5 peticiones/segundo (política pública). No requiere API key.

Dependencias: pip install requests
"""

import logging
import threading
import time
from urllib.parse import quote

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

log = logging.getLogger(__name__)

PUBCHEM_API = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

HTTP_TIMEOUT = 30
MIN_CALL_INTERVAL = 0.21        # ~5 req/s
MAX_ASSAY_ROWS = 400            # cota para no traer miles de filas al front

# ── Caché en memoria con TTL ─────────────────────────────────────────────────
_CACHE: dict = {}
_CACHE_TTL = 60 * 60 * 24       # 24 h
_cache_lock = threading.Lock()

_last_call = [0.0]
_rate_lock = threading.Lock()


def _rate_limit():
    with _rate_lock:
        elapsed = time.time() - _last_call[0]
        if elapsed < MIN_CALL_INTERVAL:
            time.sleep(MIN_CALL_INTERVAL - elapsed)
        _last_call[0] = time.time()


def _cache_get(key):
    with _cache_lock:
        entry = _CACHE.get(key)
        if entry and (time.time() - entry[0]) < _CACHE_TTL:
            return entry[1]
        if entry:
            del _CACHE[key]
    return None


def _cache_put(key, value):
    with _cache_lock:
        _CACHE[key] = (time.time(), value)


def _get(url: str):
    _rate_limit()
    return requests.get(url, timeout=HTTP_TIMEOUT, headers={"Accept": "application/json"})


def cid_from_smiles(smiles: str) -> int | None:
    """Resuelve un SMILES al primer CID de PubChem (None si no hay match)."""
    if not REQUESTS_OK or not smiles:
        return None
    key = f"cid:{smiles}"
    cached = _cache_get(key)
    if cached is not None:
        return cached or None

    url = f"{PUBCHEM_API}/compound/smiles/{quote(smiles, safe='')}/cids/JSON"
    try:
        r = _get(url)
        if r.status_code != 200:
            _cache_put(key, 0)
            return None
        cids = r.json().get("IdentifierList", {}).get("CID", []) or []
        cid = int(cids[0]) if cids else None
    except Exception as exc:
        log.warning("PubChem cid_from_smiles error: %s", exc)
        return None

    _cache_put(key, cid or 0)
    return cid


def bioassay_summary(cid: int) -> dict:
    """
    Resumen de bioensayos para un CID.

    Retorna:
        {
          "cid": int,
          "total": int, "active": int, "inactive": int,
          "assays": [ {aid, activity, target_gene_id, target_accession,
                       activity_value_um, activity_name, assay_name, assay_type} ]
        }
    """
    if not REQUESTS_OK or not cid:
        return {"cid": cid, "total": 0, "active": 0, "inactive": 0, "assays": []}

    key = f"assay:{cid}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    url = f"{PUBCHEM_API}/compound/cid/{cid}/assaysummary/JSON"
    try:
        r = _get(url)
        if r.status_code != 200:
            empty = {"cid": cid, "total": 0, "active": 0, "inactive": 0, "assays": []}
            _cache_put(key, empty)
            return empty
        table = r.json().get("Table", {})
        columns = [c for c in table.get("Columns", {}).get("Column", [])]
        rows = table.get("Row", []) or []
    except Exception as exc:
        log.warning("PubChem bioassay_summary error: %s", exc)
        return {"cid": cid, "total": 0, "active": 0, "inactive": 0, "assays": []}

    idx = {name: i for i, name in enumerate(columns)}

    def cell(cells, col):
        i = idx.get(col)
        return cells[i] if (i is not None and i < len(cells)) else ""

    assays = []
    active = inactive = 0
    for row in rows:
        cells = row.get("Cell", [])
        outcome = cell(cells, "Activity Outcome")
        if outcome == "Active":
            active += 1
        elif outcome == "Inactive":
            inactive += 1
        if len(assays) < MAX_ASSAY_ROWS:
            assays.append({
                "aid":               cell(cells, "AID"),
                "activity":          outcome,
                "target_gene_id":    cell(cells, "Target GeneID"),
                "target_accession":  cell(cells, "Target Accession"),
                "activity_value_um": cell(cells, "Activity Value [uM]"),
                "activity_name":     cell(cells, "Activity Name"),
                "assay_name":        cell(cells, "Assay Name"),
                "assay_type":        cell(cells, "Assay Type"),
            })

    # Activos primero (más informativos), luego el resto
    assays.sort(key=lambda a: 0 if a["activity"] == "Active" else 1)

    result = {
        "cid": cid,
        "total": len(rows),
        "active": active,
        "inactive": inactive,
        "assays": assays,
    }
    _cache_put(key, result)
    return result
