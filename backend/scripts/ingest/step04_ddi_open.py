"""ETL paso 4 — interacciones fármaco-fármaco (DDI) desde una fuente OPEN.

Reemplaza las DDI documentadas de DrugBank. Ingesta un CSV normalizado de pares y:
  1. rellena el array `drug-interactions` de cada fármaco en Mongo, y
  2. crea (:Drug)-[:INTERACTS_WITH {description, source, severity}]-(:Drug) en Neo4j.

Fuente por defecto: **TWOSIDES** (nSIDES, CC0) — DDI de farmacovigilancia, uso libre.
Alternativa documentada: **DDInter 2.0** (CC BY-NC-SA, solo académico).

El CSV de entrada debe tener columnas:  name_a,name_b,description,severity
(usa `prepare_twosides.py`/tu propia preparación para volcar la fuente a este formato;
raw TWOSIDES usa STITCH CIDs y requiere el crosswalk STITCH→nombre, ver README).

La resolución fármaco→ID es por **nombre normalizado** contra el catálogo ya cargado,
más los sinónimos si existen. Los pares no resueltos se descartan y se reportan.

Uso:  python -m scripts.ingest.step04_ddi_open --csv data/ddi_twosides.csv --source TWOSIDES
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict

from scripts.ingest._common import log, mongo_db, neo4j_driver, chunked


def _name_index(db):
    """nombre_normalizado → (mongo_id, nombre)."""
    idx = {}
    for doc in db.drugs.find({}, {"name": 1}):
        if doc.get("name"):
            idx[doc["name"].strip().lower()] = (doc["_id"], doc["name"])
    return idx


def _load_pairs(csv_path, name_idx, source):
    resolved, unresolved = [], 0
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
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


def run(csv_path: str, source: str = "TWOSIDES", batch: int = 1000):
    db = mongo_db()
    driver = neo4j_driver()

    log.info("Indexando nombres del catálogo…")
    name_idx = _name_index(db)
    pairs, unresolved = _load_pairs(csv_path, name_idx, source)
    log.info("%d pares DDI resueltos, %d descartados por nombre no encontrado.",
             len(pairs), unresolved)

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
    ap.add_argument("--csv", required=True, help="CSV normalizado name_a,name_b,description,severity")
    ap.add_argument("--source", default="TWOSIDES")
    args = ap.parse_args()
    run(csv_path=args.csv, source=args.source)
