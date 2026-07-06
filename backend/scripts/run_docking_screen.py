#!/usr/bin/env python3
"""
run_docking_screen.py — Cribado batch del catálogo por docking (Tier 5.3).

Acopla los fármacos del catálogo contra una diana preparada y PERSISTE la afinidad por fármaco en
la colección Mongo `docking_results` (patrón compute-once → read-cheap: el endpoint solo lee la
lista rankeada). Los mapas de Vina se calculan una sola vez (docking_service.dock_many).

USO (desde backend/, con el venv activo; requiere el receptor preparado):
    python -m scripts.run_docking_screen --target ndm1 --limit 200
    python -m scripts.run_docking_screen --target ndm1               # todo el catálogo (horas)

Idempotente: upsert por (target, drug_id). Correr offline.
"""
import argparse
import datetime as dt
import logging
import os

import django

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("docking_screen")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from config.services import docking_service as dsv


def _catalog(limit: int):
    from config.services.mongo import get_db
    db = get_db()
    q = db.drugs.find({"smiles": {"$exists": True, "$ne": ""}},
                      {"drugbank-id": 1, "name": 1, "smiles": 1})
    if limit:
        q = q.limit(limit)
    out = []
    for d in q:
        dbid = d.get("drugbank-id")
        if isinstance(dbid, dict):
            dbid = dbid.get("value")
        if dbid and d.get("smiles"):
            out.append((str(dbid), d.get("name", ""), d["smiles"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="ndm1")
    ap.add_argument("--limit", type=int, default=0, help="0 = todo el catálogo")
    ap.add_argument("--exhaustiveness", type=int, default=8)
    args = ap.parse_args()

    if not dsv.DOCKING_OK:
        raise SystemExit("Docking no disponible (vina/meeko/openbabel).")
    try:
        dsv._receptor_paths(args.target)
    except dsv.DockingUnavailable as exc:
        raise SystemExit(str(exc))

    drugs = _catalog(args.limit)
    log.info("Acoplando %d fármacos a '%s'…", len(drugs), args.target)
    smiles = [s for _id, _n, s in drugs]
    scores = dsv.dock_many(smiles, args.target, args.exhaustiveness,
                           on_progress=lambda i, n: log.info("  … %d/%d", i, n))

    from config.services.mongo import get_db
    col = get_db().docking_results
    now = dt.datetime.now(dt.timezone.utc)
    n_ok = 0
    ranked = []
    for dbid, name, smi in drugs:
        aff = scores.get(smi)
        if aff is None:
            continue
        col.update_one({"target": args.target, "drug_id": dbid},
                       {"$set": {"target": args.target, "drug_id": dbid, "name": name,
                                 "smiles": smi, "affinity_kcal_mol": aff, "docked_at": now}},
                       upsert=True)
        n_ok += 1
        ranked.append((aff, dbid, name))
    col.create_index([("target", 1), ("affinity_kcal_mol", 1)])

    ranked.sort()
    log.info("Persistidos %d resultados en Mongo `docking_results`.", n_ok)
    log.info("Top-10 hits (más negativo = mejor):")
    for aff, dbid, name in ranked[:10]:
        log.info("  %-8s %-30s %.2f kcal/mol", dbid, str(name)[:30], aff)


if __name__ == "__main__":
    main()
