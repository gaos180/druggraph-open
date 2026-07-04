"""
chembl_service.py — Cliente de la API REST de ChEMBL (EBI) para bioactividad.

ChEMBL aporta la POTENCIA cuantitativa (IC50/Ki/EC50/Kd, con valor pChEMBL) y el
MECANISMO DE ACCIÓN curado de un compuesto. Es el complemento cuantitativo a la
señal activo/inactivo de PubChem.

API base: https://www.ebi.ac.uk/chembl/api/data
Operaciones usadas:
    - molecule   : resuelve SMILES → molécula ChEMBL (flexmatch de estructura)
    - mechanism  : mecanismo de acción curado (MoA + action_type)
    - activity   : actividades con pChEMBL (potencia estandarizada)

No requiere API key.

Dependencias: pip install requests
"""

import logging
import threading
import time

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

log = logging.getLogger(__name__)

CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"

HTTP_TIMEOUT = 30
MIN_CALL_INTERVAL = 0.2
STANDARD_TYPES = {"IC50", "Ki", "EC50", "Kd"}
MAX_ACTIVITIES = 50

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


def _get(path: str, params: dict):
    _rate_limit()
    return requests.get(
        f"{CHEMBL_API}/{path}", params=params, timeout=HTTP_TIMEOUT,
        headers={"Accept": "application/json"},
    )


def molecule_from_smiles(smiles: str) -> dict | None:
    """Resuelve un SMILES a su molécula ChEMBL (flexmatch). None si no hay match."""
    if not REQUESTS_OK or not smiles:
        return None
    key = f"mol:{smiles}"
    cached = _cache_get(key)
    if cached is not None:
        return cached or None
    try:
        r = _get("molecule.json", {
            "molecule_structures__canonical_smiles__flexmatch": smiles,
            "limit": 1,
        })
        if r.status_code != 200:
            _cache_put(key, {})
            return None
        mols = r.json().get("molecules", []) or []
    except Exception as exc:
        log.warning("ChEMBL molecule_from_smiles error: %s", exc)
        return None

    if not mols:
        _cache_put(key, {})
        return None

    m = mols[0]
    info = {
        "chembl_id":  m.get("molecule_chembl_id"),
        "pref_name":  m.get("pref_name"),
        "max_phase":  m.get("max_phase"),
        "molecule_type": m.get("molecule_type"),
    }
    _cache_put(key, info)
    return info


def mechanisms(chembl_id: str) -> list[dict]:
    """Mecanismos de acción curados para una molécula ChEMBL."""
    if not REQUESTS_OK or not chembl_id:
        return []
    key = f"mech:{chembl_id}"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    try:
        r = _get("mechanism.json", {"molecule_chembl_id": chembl_id})
        mechs = r.json().get("mechanisms", []) if r.status_code == 200 else []
    except Exception as exc:
        log.warning("ChEMBL mechanisms error: %s", exc)
        return []

    out = [{
        "mechanism_of_action": x.get("mechanism_of_action"),
        "action_type":         x.get("action_type"),
        "target_chembl_id":    x.get("target_chembl_id"),
        "max_phase":           x.get("max_phase"),
    } for x in mechs]
    _cache_put(key, out)
    return out


def activities(chembl_id: str, human_only: bool = True) -> list[dict]:
    """
    Actividades con pChEMBL (potencia estandarizada), ordenadas por pChEMBL desc.
    Filtra a tipos estándar (IC50/Ki/EC50/Kd) y, por defecto, a humano.
    """
    if not REQUESTS_OK or not chembl_id:
        return []
    key = f"act:{chembl_id}:{human_only}"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    params = {
        "molecule_chembl_id": chembl_id,
        "pchembl_value__isnull": "false",
        "limit": 200,
    }
    if human_only:
        params["target_organism"] = "Homo sapiens"
    try:
        r = _get("activity.json", params)
        acts = r.json().get("activities", []) if r.status_code == 200 else []
    except Exception as exc:
        log.warning("ChEMBL activities error: %s", exc)
        return []

    filtered = []
    for a in acts:
        if a.get("standard_type") not in STANDARD_TYPES:
            continue
        try:
            pchembl = float(a.get("pchembl_value")) if a.get("pchembl_value") else None
        except (TypeError, ValueError):
            pchembl = None
        filtered.append({
            "standard_type":   a.get("standard_type"),
            "standard_value":  a.get("standard_value"),
            "standard_units":  a.get("standard_units"),
            "pchembl_value":   pchembl,
            "target_pref_name": a.get("target_pref_name"),
            "target_organism":  a.get("target_organism"),
            "assay_description": (a.get("assay_description") or "")[:160],
        })

    filtered.sort(key=lambda x: (x["pchembl_value"] is not None, x["pchembl_value"] or 0), reverse=True)
    result = filtered[:MAX_ACTIVITIES]
    _cache_put(key, result)
    return result


def full_profile(smiles: str) -> dict:
    """
    Perfil ChEMBL completo desde un SMILES: molécula + mecanismos + actividades.
    Retorna {available, molecule, mechanisms, activities}.
    """
    mol = molecule_from_smiles(smiles)
    if not mol or not mol.get("chembl_id"):
        return {"available": False, "molecule": None, "mechanisms": [], "activities": []}
    chembl_id = mol["chembl_id"]
    return {
        "available": True,
        "molecule": mol,
        "mechanisms": mechanisms(chembl_id),
        "activities": activities(chembl_id),
    }
