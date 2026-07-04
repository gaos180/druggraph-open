"""
lincs_service.py — Reversión de firma transcriptómica vía L1000CDS2 (LINCS).

Paradigma clásico de reposicionamiento (Connectivity Map): dada una firma de genes
al alza/baja de una enfermedad o condición, encuentra las perturbaciones (fármacos)
cuyo perfil L1000 REVIERTE esa firma → candidatos terapéuticos.

API: https://maayanlab.cloud/L1000CDS2/query (sin API key).
Con `aggravate:false` devuelve perturbaciones que revierten la firma de entrada.

Dependencias: pip install requests
"""

import hashlib
import logging
import threading
import time

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

log = logging.getLogger(__name__)

L1000CDS2_URL = "https://maayanlab.cloud/L1000CDS2/query"

HTTP_TIMEOUT = 60
MIN_CALL_INTERVAL = 1.0
MAX_GENES = 150          # límite práctico de L1000CDS2

_CACHE: dict = {}
_CACHE_TTL = 60 * 60 * 12
_cache_lock = threading.Lock()
_last_call = [0.0]
_rate_lock = threading.Lock()


def _rate_limit():
    with _rate_lock:
        elapsed = time.time() - _last_call[0]
        if elapsed < MIN_CALL_INTERVAL:
            time.sleep(MIN_CALL_INTERVAL - elapsed)
        _last_call[0] = time.time()


def _sig_key(up, dn, reverse):
    h = hashlib.md5((",".join(sorted(up)) + "|" + ",".join(sorted(dn)) + f"|{reverse}").encode()).hexdigest()
    return f"lincs:{h}"


def signature_reversion(up_genes: list[str], dn_genes: list[str], reverse: bool = True,
                        top: int = 25) -> dict:
    """
    Busca perturbaciones (fármacos) que revierten (reverse=True) o imitan (False) la
    firma dada.

    Retorna:
        { "available": bool, "mode": "reverse"|"mimic",
          "results": [ {name, pert_id, score, cell_id, dose} ],
          "share_id": str, "genes_used": {up:int, dn:int} }
    """
    if not REQUESTS_OK:
        return {"available": False, "results": [], "mode": "reverse" if reverse else "mimic"}

    up = list(dict.fromkeys(g.upper() for g in up_genes if g))[:MAX_GENES]
    dn = list(dict.fromkeys(g.upper() for g in dn_genes if g))[:MAX_GENES]
    if not up and not dn:
        return {"available": False, "results": [], "mode": "reverse" if reverse else "mimic",
                "reason": "Firma vacía (se requieren genes al alza y/o baja)."}

    key = _sig_key(up, dn, reverse)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    payload = {
        "data": {"upGenes": up, "dnGenes": dn},
        # aggravate:false → revierte la firma; true → la imita
        "config": {"aggravate": not reverse, "searchMethod": "geneSet",
                   "share": False, "combination": False, "db-version": "latest"},
        "metadata": [],
    }

    _rate_limit()
    try:
        r = requests.post(L1000CDS2_URL, json=payload, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        log.error("L1000CDS2 error: %s", exc)
        return {"available": False, "results": [], "mode": "reverse" if reverse else "mimic",
                "reason": f"Error consultando L1000CDS2: {exc}"}

    results = []
    for t in data.get("topMeta", [])[:top]:
        name = (t.get("pert_desc") or "").strip()
        if not name or name == "-666":
            name = t.get("pert_id") or "desconocido"
        results.append({
            "name":    name,
            "pert_id": t.get("pert_id"),
            "score":   round(float(t.get("score", 0)), 4),
            "cell_id": t.get("cell_id"),
            "dose":    t.get("pert_dose"),
        })

    out = {
        "available": True,
        "mode": "reverse" if reverse else "mimic",
        "results": results,
        "share_id": data.get("shareId"),
        "genes_used": {"up": len(up), "dn": len(dn)},
    }
    _cache_put(key, out)
    return out


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
