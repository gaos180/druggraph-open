"""
kegg_service.py — Cliente de la API REST de KEGG (rest.kegg.jp) para DrugGraph.

KEGG aporta las RUTAS biológicas que un fármaco afecta: mapea los targets
(proteínas) a las vías metabólicas y de señalización en las que participan,
mostrando qué procesos completos toca el fármaco.

Ubicación sugerida: config/kegg_service.py

API base: https://rest.kegg.jp/{operación}/...
Operaciones usadas (KEGG REST):
    - conv  : convierte UniProt <-> KEGG gene id   (conv/genes/uniprot:P00734)
    - link  : relaciona entradas entre bases       (link/pathway/hsa:2147)
    - get   : detalle de una entrada               (get/hsa00010)
    - list  : listado/etiqueta de entradas

Flujo para un target:
    UniProt accession ──conv──► KEGG gene id ──link──► pathways ──get/list──► nombres

Buenas prácticas KEGG:
    - get acepta máx. 10 entradas por llamada.
    - Uso académico/no comercial (revisar licencia para uso comercial).

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

KEGG_API = "https://rest.kegg.jp"

HTTP_TIMEOUT       = 20
MIN_CALL_INTERVAL  = 0.34      # ~3 req/s, cortés con KEGG
GET_MAX_ENTRIES    = 10        # límite duro de la operación get

# ── Caché de dos niveles con TTL ─────────────────────────────────────────────
# L1: dict en memoria (rápido, por proceso).
# L2: colección MongoDB `kegg_cache` (persistente, compartida entre workers y
#     sobrevive reinicios). El calentamiento offline puebla L2 una sola vez y
#     todos los procesos del servidor se benefician sin volver a pegarle a KEGG.
# Si Mongo no está disponible, L2 se desactiva y todo sigue funcionando sólo con L1.
_CACHE: dict = {}
_CACHE_TTL = 60 * 60 * 24       # 24 horas (los pathways cambian poco)
_cache_lock = threading.Lock()

_persist_coll = None
_persist_enabled = True

_last_call = [0.0]
_rate_lock = threading.Lock()


def _rate_limit():
    with _rate_lock:
        elapsed = time.time() - _last_call[0]
        if elapsed < MIN_CALL_INTERVAL:
            time.sleep(MIN_CALL_INTERVAL - elapsed)
        _last_call[0] = time.time()


def _persistent_collection():
    """Colección Mongo `kegg_cache` (L2), o None si Mongo no está disponible."""
    global _persist_coll, _persist_enabled
    if not _persist_enabled:
        return None
    if _persist_coll is not None:
        return _persist_coll
    try:
        from config.services.mongo import get_db
        _persist_coll = get_db().kegg_cache
        return _persist_coll
    except Exception as exc:
        log.warning("Caché KEGG persistente deshabilitada (Mongo no disponible): %s", exc)
        _persist_enabled = False
        return None


def _cache_get(key):
    now = time.time()
    with _cache_lock:
        entry = _CACHE.get(key)
        if entry:
            if (now - entry[0]) < _CACHE_TTL:
                return entry[1]
            del _CACHE[key]

    coll = _persistent_collection()
    if coll is not None:
        try:
            doc = coll.find_one({"_id": key})
        except Exception as exc:
            log.debug("KEGG L2 get falló (%s): %s", key, exc)
            doc = None
        if doc and (now - doc.get("ts", 0)) < _CACHE_TTL:
            value = doc.get("v")
            with _cache_lock:
                _CACHE[key] = (doc["ts"], value)  # promover a L1
            return value
    return None


def _cache_set(key, value):
    ts = time.time()
    with _cache_lock:
        _CACHE[key] = (ts, value)

    coll = _persistent_collection()
    if coll is not None:
        try:
            coll.update_one({"_id": key}, {"$set": {"ts": ts, "v": value}}, upsert=True)
        except Exception as exc:
            log.debug("KEGG L2 set falló (%s): %s", key, exc)


def _get(path: str) -> str | None:
    """GET a KEGG (respuestas en texto plano TSV). Retorna texto o None."""
    if not REQUESTS_OK:
        raise RuntimeError("'requests' no está instalado. pip install requests")

    url = f"{KEGG_API}/{path}"
    _rate_limit()
    try:
        r = requests.get(url, timeout=HTTP_TIMEOUT)
        if r.status_code != 200:
            # KEGG devuelve 404 cuando no hay resultados — no es un error real
            if r.status_code != 404:
                log.warning("KEGG %s: HTTP %s", path, r.status_code)
            return None
        return r.text
    except Exception as exc:
        log.error("KEGG %s error: %s", path, exc)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# CONVERSIÓN UniProt → KEGG gene id
# ══════════════════════════════════════════════════════════════════════════════

def uniprot_to_kegg(uniprot_id: str) -> str | None:
    """
    Convierte un UniProt accession (P00734) a KEGG gene id (hsa:2147).
    Usa: conv/genes/uniprot:P00734

    Retorna el primer KEGG gene id o None.
    """
    if not uniprot_id:
        return None

    cache_key = f"u2k:{uniprot_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached or None  # cached puede ser "" (sin match)

    text = _get(f"conv/genes/uniprot:{uniprot_id}")
    kegg_id = None
    if text:
        # Formato TSV: "up:P00734\thsa:2147"
        for line in text.strip().splitlines():
            parts = line.split("\t")
            if len(parts) == 2:
                kegg_id = parts[1].strip()
                break

    _cache_set(cache_key, kegg_id or "")
    return kegg_id


# ══════════════════════════════════════════════════════════════════════════════
# GEN KEGG → PATHWAYS
# ══════════════════════════════════════════════════════════════════════════════

def gene_symbol_to_kegg_id(symbol: str, organism: str = 'hsa') -> str | None:
    """
    Convierte un símbolo de gen (ej. 'ALOX5') al ID numérico de KEGG
    (ej. 'hsa:240') usando 'list/{organism}:{symbol}'.

    KEGG no acepta símbolos en link/pathway — necesita el ID numérico.
    """
    if not symbol:
        return None
    cache_key = f"sym2k:{organism}:{symbol}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached or None

    text = _get(f"list/{organism}:{symbol}")
    kegg_id = None
    if text:
        first_line = text.strip().splitlines()[0]
        parts = first_line.split("\t")
        if parts:
            kegg_id = parts[0].strip()   # ej. "hsa:240"

    _cache_set(cache_key, kegg_id or "")
    return kegg_id


def kegg_gene_to_pathways(kegg_gene_id: str) -> list[str]:
    """
    Lista los pathway ids de un gen KEGG.
    Usa: link/pathway/hsa:2147

    Retorna lista de pathway ids (ej. ["path:hsa04610", "path:hsa04810"]).
    """
    if not kegg_gene_id:
        return []

    cache_key = f"g2p:{kegg_gene_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    text = _get(f"link/pathway/{kegg_gene_id}")
    pathways = []
    if text:
        for line in text.strip().splitlines():
            parts = line.split("\t")
            if len(parts) == 2:
                pathways.append(parts[1].strip())

    _cache_set(cache_key, pathways)
    return pathways


# ══════════════════════════════════════════════════════════════════════════════
# NOMBRES DE PATHWAYS (batch con list)
# ══════════════════════════════════════════════════════════════════════════════

def pathway_names(pathway_ids: list[str]) -> dict[str, str]:
    """
    Obtiene los nombres legibles de una lista de pathway ids.
    Usa get/{id1+id2+...} (acepta hasta 10 por lote).

    Retorna { pathway_id: nombre }.
    """
    if not pathway_ids:
        return {}

    unique_ids = sorted(set(pathway_ids))
    names: dict[str, str] = {}

    # Revisar caché primero
    pending = []
    for pid in unique_ids:
        cached = _cache_get(f"pname:{pid}")
        if cached is not None:
            names[pid] = cached
        else:
            pending.append(pid)

    # Consultar pendientes con get en lotes de 10
    for i in range(0, len(pending), GET_MAX_ENTRIES):
        batch = pending[i:i + GET_MAX_ENTRIES]
        # get requiere IDs sin prefijo "path:"
        clean = [pid.replace("path:", "") for pid in batch]
        text = _get(f"get/{'+'.join(clean)}")
        if not text:
            continue

        # La respuesta es bloques ENTRY/NAME/...//// separados por "///"
        current_entry: str | None = None
        for line in text.splitlines():
            if line.startswith('ENTRY'):
                parts = line.split()
                current_entry = parts[1] if len(parts) >= 2 else None
            elif line.startswith('NAME') and current_entry:
                name = line[12:].strip()   # formato fijo: campo empieza en col 12
                # Cachear y mapear con y sin prefijo path:
                for fmt in (current_entry, f"path:{current_entry}"):
                    names[fmt] = name
                    _cache_set(f"pname:{fmt}", name)
            elif line.startswith('///'):
                current_entry = None

    # Mapear los IDs originales que puedan llevar prefijo path:
    for pid in unique_ids:
        if pid not in names:
            alt = pid.replace("path:", "")
            if alt in names:
                names[pid] = names[alt]
        names.setdefault(pid, pid)

    return names


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE: targets → pathways afectados
# ══════════════════════════════════════════════════════════════════════════════

def pathways_for_targets(targets: list[dict]) -> dict:
    """
    Dado un conjunto de targets con UniProt id, devuelve las rutas KEGG que
    tocan, agregadas y con conteo de cuántos targets caen en cada ruta.

    Parámetros:
        targets : [ { "uniprot_id": str, "name": str, "gene_name": str } ]

    Retorna:
        {
            "pathways": [
                {
                    "pathway_id": str,       # "path:hsa04610"
                    "name": str,             # "Complement and coagulation cascades"
                    "target_count": int,     # cuántos targets del fármaco caen aquí
                    "targets": [str],        # nombres de esos targets
                    "kegg_genes": [str]      # genes KEGG involucrados
                }
            ],
            "unmapped_targets": [str],       # targets sin UniProt o sin gen KEGG
            "pathway_count": int
        }
    """
    pathway_agg: dict[str, dict] = {}
    unmapped = []
    all_pathway_ids = set()

    for t in targets:
        uniprot = t.get("uniprot_id", "")
        tname   = t.get("name", "") or t.get("gene_name", "") or uniprot
        if not uniprot:
            unmapped.append(tname)
            continue

        kegg_gene = uniprot_to_kegg(uniprot)
        if not kegg_gene:
            unmapped.append(tname)
            continue

        pw_ids = kegg_gene_to_pathways(kegg_gene)
        if not pw_ids:
            unmapped.append(tname)
            continue

        for pid in pw_ids:
            all_pathway_ids.add(pid)
            entry = pathway_agg.setdefault(pid, {
                "pathway_id":   pid,
                "name":         "",
                "target_count": 0,
                "targets":      [],
                "kegg_genes":   [],
            })
            if tname not in entry["targets"]:
                entry["targets"].append(tname)
                entry["target_count"] += 1
            if kegg_gene not in entry["kegg_genes"]:
                entry["kegg_genes"].append(kegg_gene)

    # Resolver nombres de pathways en lote
    names = pathway_names(list(all_pathway_ids))
    for pid, entry in pathway_agg.items():
        # KEGG puede devolver el nombre indexado con o sin prefijo
        entry["name"] = (
            names.get(pid)
            or names.get(pid.replace("path:", ""))
            or pid
        )

    pathways = sorted(
        pathway_agg.values(),
        key=lambda x: x["target_count"],
        reverse=True,
    )

    return {
        "pathways":         pathways,
        "unmapped_targets": unmapped,
        "pathway_count":    len(pathways),
    }


def pathway_image_url(pathway_id: str) -> str:
    """
    URL de la imagen del diagrama de un pathway KEGG para incrustar.
    Acepta 'path:hsa04610' o 'hsa04610'.
    """
    pid = pathway_id.replace("path:", "")
    return f"https://www.kegg.jp/kegg/pathway/{pid[:3]}/{pid}.png"
