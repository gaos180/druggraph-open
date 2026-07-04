"""
string_service.py — Cliente de la API de STRING (string-db.org) para DrugGraph.

STRING aporta el EFECTO INDIRECTO de un fármaco: dadas las proteínas que el
fármaco toca directamente (sus targets en DrugBank), STRING devuelve las
proteínas que interactúan físicamente/funcionalmente con ellas. Esas vecinas
están indirectamente afectadas por el fármaco a través de la red PPI.

Ubicación sugerida: config/string_service.py

API base: https://string-db.org/api/{formato}/{método}
Métodos usados:
    - get_string_ids       : mapea identificadores (gene/UniProt) a STRING IDs
    - interaction_partners : vecinos PPI de las proteínas dadas

Buenas prácticas de STRING (de su FAQ):
    - Pausar >=1s entre llamadas si se hacen muchas.
    - Identificar la app con caller_identity.
    - Para grandes volúmenes, usar el dump descargable en vez de la API.

Dependencias: pip install requests
"""

import time
import logging
import threading

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

log = logging.getLogger(__name__)

STRING_API = "https://string-db.org/api"
CALLER_IDENTITY = "druggraph.app"   # identifica nuestra app ante STRING

# Especies comunes (NCBI taxonomy id)
TAXON_HUMAN = 9606

# ── Límites y caché ─────────────────────────────────────────────────────────────
DEFAULT_REQUIRED_SCORE = 400    # confianza media (escala 0–1000)
DEFAULT_MAX_PARTNERS   = 20     # vecinos por proteína
MIN_CALL_INTERVAL      = 1.0    # segundos entre llamadas (recomendación STRING)
HTTP_TIMEOUT           = 20

# Caché en memoria simple { cache_key: (timestamp, data) } con TTL
_CACHE: dict = {}
_CACHE_TTL = 60 * 60 * 6        # 6 horas
_cache_lock = threading.Lock()

# Rate limiter global (STRING pide >=1s entre llamadas)
_last_call_time = [0.0]
_rate_lock = threading.Lock()


def _rate_limit():
    with _rate_lock:
        elapsed = time.time() - _last_call_time[0]
        if elapsed < MIN_CALL_INTERVAL:
            time.sleep(MIN_CALL_INTERVAL - elapsed)
        _last_call_time[0] = time.time()


def _cache_get(key):
    with _cache_lock:
        entry = _CACHE.get(key)
        if entry and (time.time() - entry[0]) < _CACHE_TTL:
            return entry[1]
        if entry:
            del _CACHE[key]
    return None


def _cache_set(key, value):
    with _cache_lock:
        _CACHE[key] = (time.time(), value)


def _post(method: str, params: dict, output_format: str = "json"):
    """POST a STRING con rate limiting. Retorna data parseada o None."""
    if not REQUESTS_OK:
        raise RuntimeError("'requests' no está instalado. pip install requests")

    url = f"{STRING_API}/{output_format}/{method}"
    params = {**params, "caller_identity": CALLER_IDENTITY}

    _rate_limit()
    try:
        r = requests.post(url, data=params, timeout=HTTP_TIMEOUT)
        if r.status_code != 200:
            log.warning("STRING %s: HTTP %s", method, r.status_code)
            return None
        if output_format == "json":
            return r.json()
        return r.text
    except Exception as exc:
        log.error("STRING %s error: %s", method, exc)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# MAPEO DE IDENTIFICADORES
# ══════════════════════════════════════════════════════════════════════════════

def map_identifiers(identifiers: list[str], species: int = TAXON_HUMAN) -> dict[str, str]:
    """
    Mapea una lista de identificadores (gene symbols, UniProt accessions) a
    STRING IDs. Retorna { input_id: string_id }.

    STRING acepta varios tipos de id mezclados; resuelve el mejor match.
    """
    if not identifiers:
        return {}

    cache_key = f"map:{species}:{','.join(sorted(identifiers))}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # STRING separa identificadores con "%0d" (retorno de carro codificado)
    data = _post(
        "get_string_ids",
        {
            "identifiers": "\r".join(identifiers),
            "species": species,
            "limit": 1,            # 1 match por identificador
            "echo_query": 1,       # incluir el id original en la respuesta
        },
    )

    mapping = {}
    if isinstance(data, list):
        for row in data:
            query_id  = row.get("queryItem", "")
            string_id = row.get("stringId", "")
            if query_id and string_id:
                mapping[query_id] = string_id

    _cache_set(cache_key, mapping)
    return mapping


# ══════════════════════════════════════════════════════════════════════════════
# VECINOS PPI (EFECTO INDIRECTO)
# ══════════════════════════════════════════════════════════════════════════════

def interaction_partners(
    identifiers: list[str],
    species: int = TAXON_HUMAN,
    required_score: int = DEFAULT_REQUIRED_SCORE,
    max_partners: int = DEFAULT_MAX_PARTNERS,
) -> list[dict]:
    """
    Devuelve los vecinos PPI de las proteínas dadas (efecto indirecto).

    Parámetros:
        identifiers    : gene symbols o UniProt accessions de los targets directos.
        species        : NCBI taxonomy id (default humano 9606).
        required_score : umbral de confianza STRING 0–1000 (default 400).
        max_partners   : máximo de vecinos por proteína de entrada.

    Retorna lista de interacciones:
        [
            {
                "query_protein":   str,   # proteína de entrada (preferredName)
                "partner_protein": str,   # vecino PPI (preferredName)
                "partner_string_id": str,
                "score":           float, # confianza combinada 0–1
                "nscore", "fscore", "pscore", "ascore", "escore", "dscore", "tscore": float
            }
        ]
    """
    if not identifiers:
        return []

    cache_key = f"partners:{species}:{required_score}:{max_partners}:{','.join(sorted(identifiers))}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    data = _post(
        "interaction_partners",
        {
            "identifiers": "\r".join(identifiers),
            "species": species,
            "required_score": required_score,
            "limit": max_partners,
        },
    )

    partners = []
    if isinstance(data, list):
        for row in data:
            partners.append({
                "query_protein":     row.get("preferredName_A", ""),
                "partner_protein":   row.get("preferredName_B", ""),
                "partner_string_id": row.get("stringId_B", ""),
                "score":  float(row.get("score", 0) or 0),
                "nscore": float(row.get("nscore", 0) or 0),  # neighborhood
                "fscore": float(row.get("fscore", 0) or 0),  # fusion
                "pscore": float(row.get("pscore", 0) or 0),  # phylogenetic profile
                "ascore": float(row.get("ascore", 0) or 0),  # coexpression
                "escore": float(row.get("escore", 0) or 0),  # experimental
                "dscore": float(row.get("dscore", 0) or 0),  # database
                "tscore": float(row.get("tscore", 0) or 0),  # textmining
            })

    _cache_set(cache_key, partners)
    return partners


def functional_annotations(
    gene_symbols: list[str],
    species: int = TAXON_HUMAN,
    fdr_cutoff: float = 0.05,
) -> dict:
    """
    Análisis de enriquecimiento funcional (GO, KEGG, Reactome, WikiPathways)
    para un set de genes via STRING enrichment endpoint.

    Retorna:
        {
            "go_process":    [ {term, description, gene_count, genes, fdr} ],
            "go_function":   [...],
            "go_component":  [...],
            "kegg":          [...],
            "reactome":      [...],
            "wikipathways":  [...],
        }
    """
    empty = {
        "go_process": [], "go_function": [], "go_component": [],
        "kegg": [], "reactome": [], "wikipathways": [],
    }
    if not gene_symbols:
        return empty

    cache_key = f"enrich:{species}:{fdr_cutoff}:{','.join(sorted(gene_symbols))}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    data = _post(
        "enrichment",
        {"identifiers": "\r".join(gene_symbols), "species": species},
    )

    result: dict = {
        "go_process": [], "go_function": [], "go_component": [],
        "kegg": [], "reactome": [], "wikipathways": [],
    }
    # STRING usa "RCTM" para Reactome y "WikiPathways" para WikiPathways
    cat_map = {
        "Process":      "go_process",
        "Function":     "go_function",
        "Component":    "go_component",
        "KEGG":         "kegg",
        "RCTM":         "reactome",
        "WikiPathways": "wikipathways",
    }

    if isinstance(data, list):
        for item in data:
            key = cat_map.get(item.get("category", ""))
            if not key:
                continue
            fdr = item.get("fdr")
            fdr = float(fdr) if fdr is not None else 1.0
            if fdr > fdr_cutoff:
                continue
            # STRING devuelve inputGenes como lista en /enrichment
            genes_raw = item.get("inputGenes") or item.get("preferredNames") or []
            if isinstance(genes_raw, str):
                genes_list = [g.strip() for g in genes_raw.split(",") if g.strip()]
            else:
                genes_list = [g for g in genes_raw if g]
            result[key].append({
                "term":        item.get("term", ""),
                "description": item.get("description", ""),
                "gene_count":  int(item.get("number_of_genes", 0) or 0),
                "genes":       genes_list,
                "fdr":         round(fdr, 8),
            })

    for key in result:
        result[key].sort(key=lambda x: x["fdr"])

    _cache_set(cache_key, result)
    return result


def network_image_url(
    identifiers: list[str],
    species: int = TAXON_HUMAN,
    required_score: int = DEFAULT_REQUIRED_SCORE,
) -> str:
    """
    Construye la URL de la imagen de red de STRING para incrustar directamente
    (no consume nuestra API; el navegador la carga). Útil como vista rápida.
    """
    ids = "%0d".join(identifiers)
    return (
        f"{STRING_API}/image/network"
        f"?identifiers={ids}"
        f"&species={species}"
        f"&required_score={required_score}"
        f"&caller_identity={CALLER_IDENTITY}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# UTILIDAD: vecinos indirectos de un conjunto de targets
# ══════════════════════════════════════════════════════════════════════════════

def indirect_neighbors(
    gene_symbols: list[str],
    species: int = TAXON_HUMAN,
    required_score: int = DEFAULT_REQUIRED_SCORE,
    max_partners: int = DEFAULT_MAX_PARTNERS,
) -> dict:
    """
    Pipeline de alto nivel: dado un conjunto de genes (targets directos del
    fármaco), devuelve los vecinos PPI agrupados, listos para la UI.

    Retorna:
        {
            "direct_genes": [str],
            "neighbors": [
                {
                    "partner_protein": str,
                    "partner_string_id": str,
                    "max_score": float,            # mejor score entre conexiones
                    "connected_to": [str],         # genes directos a los que se une
                    "connection_count": int
                }
            ],
            "edges": [
                { "source": str, "target": str, "score": float }
            ]
        }
    """
    partners = interaction_partners(
        gene_symbols, species=species,
        required_score=required_score, max_partners=max_partners,
    )

    # Agrupar por proteína vecina
    grouped: dict[str, dict] = {}
    edges = []
    direct_set = {g.upper() for g in gene_symbols}

    for p in partners:
        partner = p["partner_protein"]
        # Evitar listar como "vecino indirecto" a otro target directo
        if partner.upper() in direct_set:
            continue

        entry = grouped.setdefault(partner, {
            "partner_protein":   partner,
            "partner_string_id": p["partner_string_id"],
            "max_score":         0.0,
            "connected_to":      [],
            "connection_count":  0,
        })
        entry["max_score"] = max(entry["max_score"], p["score"])
        if p["query_protein"] not in entry["connected_to"]:
            entry["connected_to"].append(p["query_protein"])
            entry["connection_count"] += 1

        edges.append({
            "source": p["query_protein"],
            "target": partner,
            "score":  round(p["score"], 3),
        })

    neighbors = sorted(
        grouped.values(),
        key=lambda x: (x["connection_count"], x["max_score"]),
        reverse=True,
    )
    for n in neighbors:
        n["max_score"] = round(n["max_score"], 3)

    return {
        "direct_genes": gene_symbols,
        "neighbors":    neighbors,
        "edges":        edges,
    }
