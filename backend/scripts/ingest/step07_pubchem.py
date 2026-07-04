"""ETL paso 7 (enriquecedor) — propiedades fisicoquímicas desde PubChem (por CID).

Para los fármacos con cross-ref `"PubChem CID"` en `external-identifiers`, consulta
la propiedad computada de PubChem (PUG-REST) y escribe en el documento Mongo `drugs`
el campo `pubchem_properties`:
    { cid, MolecularWeight, XLogP, TPSA, HBondDonorCount, HBondAcceptorCount,
      RotatableBondCount, source }

Fuente: PubChem PUG-REST (sin API key). Datos en dominio público.
Endpoint:
    https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/<CID>/property/
        MolecularWeight,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount,RotatableBondCount/JSON

Se respeta la política de PubChem (≤ 5 peticiones/segundo). Se reutiliza el patrón de
rate-limit de `config/services/pubchem_service.py`; ese cliente no expone un helper de
"propiedades por CID", así que aquí se hace la llamada PUG directa con `requests`.

Idempotente: `update_one($set)` por fármaco. Degradación limpia: un error de red por
fármaco se registra y se continúa con el siguiente.

Uso (desde backend/, con el venv activo):
    python -m scripts.ingest.step07_pubchem
    python -m scripts.ingest.step07_pubchem --limit 200
"""
from __future__ import annotations

import argparse
import threading
import time

try:
    import requests
    REQUESTS_OK = True
except ImportError:  # pragma: no cover
    REQUESTS_OK = False

from scripts.ingest._common import log, mongo_db

PUBCHEM_API = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
HTTP_TIMEOUT = 30
MIN_CALL_INTERVAL = 0.21   # ~5 req/s (política pública de PubChem)

# Propiedades computadas a pedir (perfil "regla de 5" de Lipinski + rotables/TPSA)
_PROPS = [
    "MolecularWeight", "XLogP", "TPSA",
    "HBondDonorCount", "HBondAcceptorCount", "RotatableBondCount",
]
_NUMERIC = {"MolecularWeight", "XLogP", "TPSA"}
_INTEGER = {"HBondDonorCount", "HBondAcceptorCount", "RotatableBondCount"}

_last_call = [0.0]
_rate_lock = threading.Lock()


def _rate_limit():
    with _rate_lock:
        elapsed = time.time() - _last_call[0]
        if elapsed < MIN_CALL_INTERVAL:
            time.sleep(MIN_CALL_INTERVAL - elapsed)
        _last_call[0] = time.time()


def _pubchem_cids(db, limit=None):
    """Devuelve [(mongo_id, cid)] de los fármacos con cross-ref 'PubChem CID'."""
    q = {"external-identifiers.resource": "PubChem CID"}
    proj = {"external-identifiers": 1}
    cur = db.drugs.find(q, proj)
    if limit:
        cur = cur.limit(limit)
    out = []
    for doc in cur:
        for x in doc.get("external-identifiers", []) or []:
            if x.get("resource") == "PubChem CID" and x.get("identifier"):
                cid = str(x["identifier"]).strip()
                if cid.isdigit():
                    out.append((doc["_id"], int(cid)))
                break
    return out


def _fetch_properties(cid: int) -> dict | None:
    """Propiedades computadas de un CID (None ante error o respuesta vacía)."""
    url = f"{PUBCHEM_API}/compound/cid/{cid}/property/{','.join(_PROPS)}/JSON"
    _rate_limit()
    try:
        r = requests.get(url, timeout=HTTP_TIMEOUT, headers={"Accept": "application/json"})
        if r.status_code != 200:
            return None
        rows = (r.json().get("PropertyTable", {}) or {}).get("Properties", []) or []
    except Exception as exc:  # noqa: BLE001
        log.warning("PubChem propiedades CID %s error: %s", cid, exc)
        return None
    if not rows:
        return None

    raw = rows[0]
    props: dict = {"cid": cid, "source": "PubChem"}
    for key in _PROPS:
        val = raw.get(key)
        if val is None:
            continue
        try:
            props[key] = float(val) if key in _NUMERIC else int(val)
        except (TypeError, ValueError):
            props[key] = val
    return props


def run(limit: int | None = None):
    if not REQUESTS_OK:
        log.warning("PubChem no disponible (falta `requests`); nada que hacer.")
        return 0

    db = mongo_db()
    pairs = _pubchem_cids(db, limit=limit)
    log.info("%d fármacos con cross-ref PubChem CID a enriquecer…", len(pairs))

    updated = 0
    for i, (mongo_id, cid) in enumerate(pairs, 1):
        props = _fetch_properties(cid)
        if props and len(props) > 2:  # más allá de cid+source
            db.drugs.update_one({"_id": mongo_id}, {"$set": {"pubchem_properties": props}})
            updated += 1
        if i % 50 == 0:
            log.info("  … %d/%d consultados (%d anotados)", i, len(pairs), updated)

    log.info("PubChem: %d/%d fármacos anotados con pubchem_properties.", updated, len(pairs))
    return updated


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Enriquecer drugs con propiedades fisicoquímicas de PubChem")
    ap.add_argument("--limit", type=int, default=None, help="límite de fármacos (prueba)")
    args = ap.parse_args()
    run(limit=args.limit)
