"""ETL paso 2 (opcional) — enriquecer `drugs` con ChEMBL.

Rellena descripción/mecanismo de acción y un SMILES canónico de respaldo desde ChEMBL,
emparejando por el cross-ref ChEMBL que DrugCentral ya provee (external-identifiers).

Dos modos:
  --source postgres   (por defecto) lee la base 'chembl' restaurada en el staging
  --source api        usa la API REST de ChEMBL (sin dump; más lento, para subconjuntos)

Uso:  python -m scripts.ingest.step02_chembl_enrich [--source postgres|api] [--limit N]
"""
from __future__ import annotations

import argparse

from scripts.ingest._common import log, mongo_db, staging_conn

CHEMBL_DB = "chembl"


def _chembl_ids(db, limit=None):
    """Devuelve [(mongo_id, chembl_id)] de los fármacos con cross-ref ChEMBL."""
    q = {"external-identifiers.resource": "ChEMBL"}
    proj = {"external-identifiers": 1}
    cur = db.drugs.find(q, proj)
    if limit:
        cur = cur.limit(limit)
    out = []
    for doc in cur:
        for x in doc.get("external-identifiers", []):
            if x.get("resource") == "ChEMBL" and x.get("identifier"):
                out.append((doc["_id"], x["identifier"]))
                break
    return out


def _enrich_postgres(db, pairs):
    conn = staging_conn(dbname=CHEMBL_DB)
    cur = conn.cursor()
    updated = 0
    for mongo_id, chembl_id in pairs:
        cur.execute("""
            SELECT md.molregno, cs.canonical_smiles,
                   string_agg(DISTINCT dm.mechanism_of_action, '; ') AS moa
            FROM molecule_dictionary md
            LEFT JOIN compound_structures cs ON cs.molregno = md.molregno
            LEFT JOIN drug_mechanism dm      ON dm.molregno = md.molregno
            WHERE md.chembl_id = %s
            GROUP BY md.molregno, cs.canonical_smiles
        """, (chembl_id,))
        row = cur.fetchone()
        if not row:
            continue
        _, smiles, moa = row
        update = {}
        if moa:
            update["chembl_mechanism"] = moa
            doc = db.drugs.find_one({"_id": mongo_id}, {"description": 1, "smiles": 1})
            if doc and not doc.get("description"):
                update["description"] = moa
            if doc and not doc.get("smiles") and smiles:
                update["smiles"] = smiles
        elif smiles:
            doc = db.drugs.find_one({"_id": mongo_id}, {"smiles": 1})
            if doc and not doc.get("smiles"):
                update["smiles"] = smiles
        if update:
            db.drugs.update_one({"_id": mongo_id}, {"$set": update})
            updated += 1
    cur.close()
    conn.close()
    return updated


def _enrich_api(db, pairs):
    import requests
    session = requests.Session()
    base = "https://www.ebi.ac.uk/chembl/api/data"
    updated = 0
    for mongo_id, chembl_id in pairs:
        try:
            r = session.get(f"{base}/mechanism.json", params={"molecule_chembl_id": chembl_id}, timeout=15)
            moas = [m["mechanism_of_action"] for m in r.json().get("mechanisms", []) if m.get("mechanism_of_action")]
        except Exception:  # noqa: BLE001
            continue
        if moas:
            db.drugs.update_one({"_id": mongo_id}, {"$set": {"chembl_mechanism": "; ".join(moas)}})
            updated += 1
    return updated


def run(source: str = "postgres", limit: int | None = None):
    db = mongo_db()
    pairs = _chembl_ids(db, limit=limit)
    log.info("%d fármacos con cross-ref ChEMBL a enriquecer (%s)…", len(pairs), source)
    updated = _enrich_postgres(db, pairs) if source == "postgres" else _enrich_api(db, pairs)
    log.info("ChEMBL: %d fármacos enriquecidos.", updated)
    return updated


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Enriquecer drugs con ChEMBL")
    ap.add_argument("--source", choices=["postgres", "api"], default="postgres")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    run(source=args.source, limit=args.limit)
