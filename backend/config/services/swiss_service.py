"""
swiss_service.py — Integración con SwissTargetPrediction.

Dos modos de uso:
  1. parse_swiss_csv(text)    — parsea el CSV exportado desde la web
  2. predict_targets(smiles)  — llama directamente a la API REST

Formato CSV esperado (encabezados entre comillas):
  "Target","Common name","Uniprot ID","ChEMBL ID",
  "Target Class","Probability*","Known actives (3D/2D)"

Ambas funciones devuelven listas del mismo shape:
  {
    "uniprot_id":    str,
    "gene_name":     str,
    "target_name":   str,
    "probability":   float,   # 0–1
    "target_class":  str,
    "chembl_id":     str,
    "known_actives": int,
  }
"""
import csv
import io
import logging
import time
import requests
from threading import Lock

log = logging.getLogger(__name__)

_BASE_URL   = "https://www.swisstargetprediction.ch"
_TIMEOUT    = 40
_CACHE: dict[str, tuple[list, float]] = {}
_CACHE_TTL  = 3600
_CACHE_LOCK = Lock()

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "DrugGraph/1.0 (academic; contact: druggraph@academic.dev)",
    "Accept": "application/json, text/plain, */*",
})

ORGANISMS = [
    "Homo sapiens",
    "Mus musculus",
    "Rattus norvegicus",
    "Bos taurus",
    "Equus caballus",
    "Sus scrofa",
    "Oryctolagus cuniculus",
]


# ── Parseo de CSV exportado ────────────────────────────────────────────────────

def parse_swiss_csv(content: str) -> list[dict]:
    """
    Parsea el CSV descargado desde swisstargetprediction.ch.

    Encabezados reconocidos (en orden):
      "Target", "Common name", "Uniprot ID", "ChEMBL ID",
      "Target Class", "Probability*", "Known actives (3D/2D)"
    """
    reader = csv.DictReader(io.StringIO(content.strip()))
    results = []

    for row in reader:
        uniprot = _col(row, "Uniprot ID", "UniprotID", "uniprot_id")
        gene    = _col(row, "Common name", "Gene", "gene", "gene_name")
        name    = _col(row, "Target", "target_name", "Target name")
        tclass  = _col(row, "Target Class", "class", "target_class")
        chembl  = _col(row, "ChEMBL ID", "chembl_id")

        raw_prob = _col(row, "Probability*", "Probability", "probability") or "0"
        try:
            prob = round(float(raw_prob), 4)
        except ValueError:
            prob = 0.0

        raw_act = _col(row, "Known actives (3D/2D)", "Known actives") or "0 / 0"
        actives = _parse_actives(raw_act)

        if not (uniprot or gene):
            continue

        results.append({
            "uniprot_id":    uniprot,
            "gene_name":     gene,
            "target_name":   name,
            "probability":   prob,
            "target_class":  tclass,
            "chembl_id":     chembl,
            "known_actives": actives,
        })

    return sorted(results, key=lambda x: x["probability"], reverse=True)


# ── Llamada directa a la API REST ─────────────────────────────────────────────

def predict_targets(smiles: str, organism: str = "Homo sapiens") -> list[dict]:
    """
    Llama al endpoint REST de SwissTargetPrediction y devuelve predicciones
    ordenadas por probabilidad descendente.

    Usa caché en memoria (TTL 1 hora) para no sobrecargar la API.

    Raises:
        RuntimeError — si la API no responde o devuelve formato inesperado.
    """
    cache_key = f"{smiles}||{organism}"
    with _CACHE_LOCK:
        if cache_key in _CACHE:
            data, ts = _CACHE[cache_key]
            if time.time() - ts < _CACHE_TTL:
                return data

    raw = _call_api(smiles, organism)
    parsed = _parse_api_response(raw)

    with _CACHE_LOCK:
        _CACHE[cache_key] = (parsed, time.time())

    return parsed


def _call_api(smiles: str, organism: str) -> object:
    url = f"{_BASE_URL}/predict.php"
    try:
        resp = _SESSION.post(
            url,
            data={"smiles": smiles, "organism": organism},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"SwissTargetPrediction no respondió en {_TIMEOUT}s. "
            "Intenta de nuevo o usa la importación desde CSV."
        )
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "No se pudo conectar a SwissTargetPrediction. "
            "Verifica la conexión a internet del servidor, "
            "o descarga el CSV manualmente desde swisstargetprediction.ch."
        )
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"SwissTargetPrediction devolvió error HTTP {e.response.status_code}. "
            "Intenta la importación desde CSV."
        )
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Error de red llamando a SwissTargetPrediction: {e}")

    ct = resp.headers.get("Content-Type", "")
    text = resp.text.strip()

    # Detectar HTML — la API fue reemplazada por una interfaz JS y ya no devuelve datos
    if "text/html" in ct or text.startswith("<!") or "<!DOCTYPE" in text[:100]:
        raise RuntimeError(
            "API_UNAVAILABLE: SwissTargetPrediction ya no ofrece un endpoint "
            "REST accesible programáticamente. Usa la opción de importar CSV: "
            "visita swisstargetprediction.ch, realiza la predicción y descarga el CSV."
        )

    if "json" in ct or text.startswith(("[", "{")):
        try:
            return resp.json()
        except ValueError:
            pass
    # Si devuelve CSV, parsearlo directamente
    if text.startswith('"Target"') or "Probability" in text:
        return parse_swiss_csv(text)

    raise RuntimeError(
        "SwissTargetPrediction devolvió un formato no reconocido. "
        f"Content-Type: {ct!r} | Inicio: {text[:120]!r}"
    )


def _parse_api_response(data: object) -> list[dict]:
    """Normaliza la respuesta JSON de la API."""
    if isinstance(data, list) and data and isinstance(data[0], dict) and "probability" in data[0]:
        # Ya fue parseado como CSV por _call_api
        return data

    if not isinstance(data, list):
        if isinstance(data, dict):
            for k in ("predictions", "results", "data", "targets"):
                if k in data:
                    data = data[k]
                    break
        if not isinstance(data, list):
            raise RuntimeError(
                f"Formato desconocido de la API de SwissTargetPrediction: {type(data).__name__}"
            )

    results = []
    for item in data:
        if not isinstance(item, dict):
            continue
        uniprot = _first(item, "UniprotID", "uniprot_id", "UniProtID", "Uniprot")
        gene    = _first(item, "Gene", "CommonName", "commonName", "gene_name", "Common name")
        name    = _first(item, "Target", "target_name", "Name")
        tclass  = _first(item, "class", "Class", "targetClass", "Target Class")
        chembl  = _first(item, "ChEMBLID", "ChEMBL ID", "chembl_id")

        raw_prob = item.get("Probability") or item.get("probability") or item.get("score") or 0.0
        try:
            prob = round(float(raw_prob), 4)
        except (TypeError, ValueError):
            prob = 0.0

        actives_raw = item.get("KnownActives") or item.get("known_actives") or "0"
        actives = _parse_actives(str(actives_raw))

        if not (uniprot or gene):
            continue

        results.append({
            "uniprot_id":    uniprot,
            "gene_name":     gene,
            "target_name":   name,
            "probability":   prob,
            "target_class":  tclass,
            "chembl_id":     chembl,
            "known_actives": actives,
        })

    return sorted(results, key=lambda x: x["probability"], reverse=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _col(row: dict, *keys: str) -> str:
    for k in keys:
        v = row.get(k)
        if v and str(v).strip():
            return str(v).strip()
    return ""


def _first(d: dict, *keys: str) -> str:
    for k in keys:
        v = d.get(k)
        if v and str(v).strip():
            return str(v).strip()
    return ""


def _parse_actives(raw: str) -> int:
    """'986 /  79   ' → 1065"""
    try:
        parts = raw.replace(",", "").split("/")
        return sum(int(p.strip()) for p in parts if p.strip().isdigit())
    except Exception:
        return 0
