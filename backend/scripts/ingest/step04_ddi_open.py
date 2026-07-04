"""ETL paso 4 — interacciones fármaco-fármaco (DDI) desde una fuente OPEN.

Reemplaza las DDI documentadas de DrugBank. Ingesta un CSV normalizado de pares y:
  1. rellena el array `drug-interactions` de cada fármaco en Mongo, y
  2. crea (:Drug)-[:INTERACTS_WITH {description, source, severity}]-(:Drug) en Neo4j.

Fuente por defecto: **TWOSIDES** (nSIDES, CC0) — DDI de farmacovigilancia, uso libre.
Alternativa documentada: **DDInter 2.0** (CC BY-NC-SA, solo académico).

Dos vías de resolución fármaco→ID (se autodetecta por las columnas del CSV):

  A) Por **PubChem CID** (recomendado, más robusto). Columnas:
        cid_a,cid_b,description,severity
     El índice CID→mongo_id se construye desde `external-identifiers`
     (resource == "PubChem CID") del catálogo `drugs`. Es el formato que produce
     `prepare_ddi_stitch.py` a partir de TWOSIDES (que trae STITCH stereo-CIDs).

  B) Por **nombre normalizado** (fallback). Columnas:
        name_a,name_b,description,severity
     Resuelve contra `name` del catálogo ya cargado. Útil para DDInter.

Los pares no resueltos (o auto-pares) se descartan y se reportan. La escritura es
idempotente (Mongo `$set` del array completo; Neo4j MERGE de la relación) y por lotes.

Uso:
    # modo CID (autodetectado por columnas cid_a,cid_b)
    python -m scripts.ingest.step04_ddi_open --csv data/ddi_twosides.csv --source TWOSIDES

    # modo nombre (autodetectado por columnas name_a,name_b)
    python -m scripts.ingest.step04_ddi_open --csv data/ddinter.csv --source DDInter

    # forzar el modo explícitamente si el CSV trae ambas familias de columnas
    python -m scripts.ingest.step04_ddi_open --csv data/x.csv --mode cid
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict

from scripts.ingest._common import log, mongo_db, neo4j_driver, chunked

# Etiqueta del cross-ref de PubChem tal como la escribe step01 (_EXTERNAL_ID_TYPES).
PUBCHEM_RESOURCE = "PubChem CID"

_CID_COLS = ("cid_a", "cid_b")
_NAME_COLS = ("name_a", "name_b")


# ── Índices de resolución ──────────────────────────────────────────────────────
def _name_index(db):
    """nombre_normalizado → (mongo_id, nombre)."""
    idx = {}
    for doc in db.drugs.find({}, {"name": 1}):
        if doc.get("name"):
            idx[doc["name"].strip().lower()] = (doc["_id"], doc["name"])
    return idx


def _norm_cid(raw) -> str | None:
    """Normaliza un CID a su forma entera canónica en texto.

    Acepta enteros, '12345', '000012345' (ceros a la izquierda) y, por robustez,
    identificadores STITCH residuales tipo 'CIDs00012345'/'CIDm12345'.
    Devuelve None si no hay dígitos.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    m = re.match(r"^CID[ms]?(\d+)$", s, flags=re.IGNORECASE)
    if m:
        s = m.group(1)
    digits = re.sub(r"\D", "", s)
    if not digits:
        return None
    return str(int(digits))  # colapsa ceros a la izquierda


def _cid_index(db):
    """PubChem CID (str canónico) → (mongo_id, nombre).

    Un mismo CID podría figurar en más de un fármaco; nos quedamos con el primero
    encontrado (los duplicados reales son raros en DrugCentral).
    """
    idx = {}
    cursor = db.drugs.find(
        {"external-identifiers.resource": PUBCHEM_RESOURCE},
        {"name": 1, "external-identifiers": 1},
    )
    for doc in cursor:
        for ext in doc.get("external-identifiers", []):
            if ext.get("resource") != PUBCHEM_RESOURCE:
                continue
            cid = _norm_cid(ext.get("identifier"))
            if cid and cid not in idx:
                idx[cid] = (doc["_id"], doc.get("name") or "")
    return idx


# ── Carga del CSV ───────────────────────────────────────────────────────────────
def _detect_mode(fieldnames, forced: str | None) -> str:
    """Devuelve 'cid' o 'name' según las columnas presentes (o el modo forzado)."""
    cols = {(c or "").strip().lower() for c in (fieldnames or [])}
    if forced in ("cid", "name"):
        need = _CID_COLS if forced == "cid" else _NAME_COLS
        if not all(c in cols for c in need):
            raise SystemExit(
                f"El CSV no tiene las columnas requeridas para --mode {forced}: {need}"
            )
        return forced
    if all(c in cols for c in _CID_COLS):
        return "cid"
    if all(c in cols for c in _NAME_COLS):
        return "name"
    raise SystemExit(
        "No se detecta el modo: el CSV debe traer (cid_a,cid_b) o (name_a,name_b). "
        f"Columnas encontradas: {sorted(cols)}"
    )


def _load_pairs(csv_path, mode, cid_idx, name_idx, source):
    resolved, unresolved = [], 0
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        real_mode = _detect_mode(reader.fieldnames, mode)
        log.info("Modo de resolución: %s", real_mode.upper())
        for row in reader:
            if real_mode == "cid":
                a = cid_idx.get(_norm_cid(row.get("cid_a")))
                b = cid_idx.get(_norm_cid(row.get("cid_b")))
            else:
                a = name_idx.get((row.get("name_a") or "").strip().lower())
                b = name_idx.get((row.get("name_b") or "").strip().lower())
            if not a or not b or a[0] == b[0]:
                unresolved += 1
                continue
            resolved.append({
                "a_id": a[0], "a_name": a[1],
                "b_id": b[0], "b_name": b[1],
                "description": (row.get("description") or "").strip(),
                "severity": (row.get("severity") or "").strip(),
                "source": source,
            })
    return resolved, unresolved


def run(csv_path: str, source: str = "TWOSIDES", mode: str | None = None,
        batch: int = 1000):
    db = mongo_db()
    driver = neo4j_driver()

    # Construimos ambos índices; el detector elige cuál se usa. El índice CID es
    # barato (solo docs con cross-ref de PubChem) y el de nombres recorre el catálogo.
    log.info("Indexando catálogo (CID + nombre)…")
    cid_idx = _cid_index(db)
    name_idx = _name_index(db)
    log.info("  %d CIDs indexados, %d nombres indexados.", len(cid_idx), len(name_idx))

    pairs, unresolved = _load_pairs(csv_path, mode, cid_idx, name_idx, source)
    log.info("%d pares DDI resueltos, %d descartados (par no resuelto/auto-par).",
             len(pairs), unresolved)
    if not pairs:
        log.warning("Sin pares resueltos; nada que escribir.")
        return 0

    # 1) Mongo: agregamos las DDI a cada fármaco (ambas direcciones)
    per_drug = defaultdict(list)
    for p in pairs:
        per_drug[p["a_id"]].append({"drugbank-id": p["b_id"], "name": p["b_name"],
                                     "description": p["description"], "severity": p["severity"],
                                     "source": source})
        per_drug[p["b_id"]].append({"drugbank-id": p["a_id"], "name": p["a_name"],
                                     "description": p["description"], "severity": p["severity"],
                                     "source": source})
    from pymongo import UpdateOne
    ops = [UpdateOne({"_id": did}, {"$set": {"drug-interactions": items}})
           for did, items in per_drug.items()]
    for group in chunked(ops, 1000):
        db.drugs.bulk_write(group, ordered=False)
    log.info("Mongo: DDI escritas en %d fármacos.", len(per_drug))

    # 2) Neo4j: relaciones INTERACTS_WITH
    cypher = """
    UNWIND $rows AS row
    MATCH (a:Drug {drugbank_id: row.a_id})
    MATCH (b:Drug {drugbank_id: row.b_id})
    MERGE (a)-[r:INTERACTS_WITH]-(b)
      SET r.description = row.description,
          r.severity    = row.severity,
          r.source      = row.source
    """
    written = 0
    for group in chunked(pairs, batch):
        with driver.session() as s:
            s.run(cypher, rows=group)
        written += len(group)
        log.info("  … %d relaciones INTERACTS_WITH", written)

    log.info("DDI open (%s) cargadas.", source)
    return len(pairs)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Cargar DDI open (TWOSIDES/DDInter)")
    ap.add_argument("--csv", required=True,
                    help="CSV normalizado: cid_a,cid_b,... (modo CID) o name_a,name_b,... (modo nombre)")
    ap.add_argument("--source", default="TWOSIDES")
    ap.add_argument("--mode", choices=["cid", "name"], default=None,
                    help="Forzar el modo de resolución (por defecto se autodetecta por columnas)")
    args = ap.parse_args()
    run(csv_path=args.csv, source=args.source, mode=args.mode)
