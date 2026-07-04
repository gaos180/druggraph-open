"""
opentargets_service.py — Cliente GraphQL de Open Targets Platform.

Open Targets aporta la evidencia DIANA→ENFERMEDAD con score integrado (genética,
expresión, literatura, etc.). Convierte el reposicionamiento por similitud de dianas
en hipótesis diana→enfermedad defendibles.

API GraphQL: https://api.platform.opentargets.org/api/v4/graphql (sin API key).
Flujo: gene_symbol --search--> Ensembl gene id (ENSG) --target.associatedDiseases--> enfermedades.

Dependencias: pip install requests
"""

import logging
import threading
import time
from collections import defaultdict

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

log = logging.getLogger(__name__)

GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"

HTTP_TIMEOUT = 30
MIN_CALL_INTERVAL = 0.2
MAX_GENES = 15
DEFAULT_PER_TARGET = 15
DEFAULT_TOP = 25

_CACHE: dict = {}
_CACHE_TTL = 60 * 60 * 24
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


def _graphql(query: str, variables: dict) -> dict:
    _rate_limit()
    resp = requests.post(
        GRAPHQL_URL, json={"query": query, "variables": variables},
        timeout=HTTP_TIMEOUT, headers={"Content-Type": "application/json"},
    )
    resp.raise_for_status()
    return resp.json().get("data", {}) or {}


_SEARCH_Q = 'query($q:String!){ search(queryString:$q, entityNames:["target"]){ hits{ id name entity } } }'
_DISEASES_Q = ('query($id:String!,$size:Int!){ target(ensemblId:$id){ approvedSymbol '
               'associatedDiseases(page:{index:0,size:$size}){ count rows{ score '
               'disease{ id name } } } } }')


def ensembl_from_symbol(symbol: str) -> str | None:
    """Mapea un símbolo de gen a su Ensembl gene id (ENSG) vía search."""
    if not REQUESTS_OK or not symbol:
        return None
    key = f"ensg:{symbol.upper()}"
    cached = _cache_get(key)
    if cached is not None:
        return cached or None
    try:
        data = _graphql(_SEARCH_Q, {"q": symbol})
        hits = (data.get("search", {}) or {}).get("hits", []) or []
        # primer hit cuyo nombre coincide con el símbolo (case-insensitive), o el primero
        ensg = None
        for h in hits:
            if (h.get("name") or "").upper() == symbol.upper():
                ensg = h.get("id"); break
        if not ensg and hits:
            ensg = hits[0].get("id")
    except Exception as exc:
        log.warning("Open Targets ensembl_from_symbol(%s) error: %s", symbol, exc)
        return None
    _cache_put(key, ensg or "")
    return ensg or None


def target_diseases(ensembl_id: str, size: int = DEFAULT_PER_TARGET) -> list[dict]:
    """Enfermedades asociadas a un target (ENSG), con score."""
    if not REQUESTS_OK or not ensembl_id:
        return []
    key = f"dis:{ensembl_id}:{size}"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    try:
        data = _graphql(_DISEASES_Q, {"id": ensembl_id, "size": size})
        rows = ((data.get("target", {}) or {}).get("associatedDiseases", {}) or {}).get("rows", []) or []
    except Exception as exc:
        log.warning("Open Targets target_diseases(%s) error: %s", ensembl_id, exc)
        return []
    out = [{
        "disease_id": r["disease"]["id"],
        "disease_name": r["disease"]["name"],
        "score": round(float(r["score"]), 4),
    } for r in rows if r.get("disease")]
    _cache_put(key, out)
    return out


def diseases_for_genes(symbols: list[str], per_target: int = DEFAULT_PER_TARGET,
                       top: int = DEFAULT_TOP) -> dict:
    """
    Agrega enfermedades asociadas al módulo de dianas (lista de símbolos de gen).
    Por cada enfermedad conserva el score máximo entre las dianas y qué genes la soportan.

    Retorna:
        { "available": bool,
          "genes_mapped": [{gene, ensembl_id}],
          "genes_unmapped": [str],
          "diseases": [ {disease_id, disease_name, score, supporting_genes:[str], gene_count:int} ] }
    """
    if not REQUESTS_OK:
        return {"available": False, "genes_mapped": [], "genes_unmapped": symbols, "diseases": []}

    genes = list(dict.fromkeys(g.upper() for g in symbols if g))[:MAX_GENES]
    mapped: list[dict] = []
    unmapped: list[str] = []
    agg: dict = {}
    supporters: dict = defaultdict(set)

    for g in genes:
        ensg = ensembl_from_symbol(g)
        if not ensg:
            unmapped.append(g)
            continue
        mapped.append({"gene": g, "ensembl_id": ensg})
        for d in target_diseases(ensg, size=per_target):
            did = d["disease_id"]
            if did not in agg or d["score"] > agg[did]["score"]:
                agg[did] = {"disease_id": did, "disease_name": d["disease_name"], "score": d["score"]}
            supporters[did].add(g)

    diseases = []
    for did, info in agg.items():
        diseases.append({
            **info,
            "supporting_genes": sorted(supporters[did]),
            "gene_count": len(supporters[did]),
        })
    # ordena por nº de dianas que la soportan y luego por score
    diseases.sort(key=lambda x: (x["gene_count"], x["score"]), reverse=True)

    return {
        "available": True,
        "genes_mapped": mapped,
        "genes_unmapped": unmapped,
        "diseases": diseases[:top],
    }
