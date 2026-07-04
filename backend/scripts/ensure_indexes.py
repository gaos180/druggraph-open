#!/usr/bin/env python3
"""
ensure_indexes.py — Crea/ajusta los índices de MongoDB de DrugGraph (idempotente).

Basado en la auditoría de las queries reales del código:

  drugs:
    - drugbank-id            (existente) — detalle por ID                → IXSCAN
    - name                   (existente) — match exacto de nombre
    - drugbank-id.value      (NUEVO)     — detalle fallback (IDs estructurados)
    - type                   (NUEVO)     — filtro por tipo               → evita COLLSCAN
    - groups                 (NUEVO)     — filtro por grupo (multikey)   → evita COLLSCAN
    - name (text)            (NUEVO)     — búsqueda por palabra rápida    → $text en vez de scan 646 ms
  users:
    - email (unique)         (existente)
  ctd_gene_interactions:
    - _id                    (existente) — única forma de consulta (find {_id:{$in}})
    - chemical_count         (ELIMINAR)  — nunca se consulta
    - interaction_count      (ELIMINAR)  — nunca se consulta

USO:
    python ensure_indexes.py            # aplica los cambios
    python ensure_indexes.py --dry-run  # solo muestra qué haría

Variables de entorno: MONGODB_URI / MONGO_URI, MONGODB_DB / MONGO_DB.
Dependencias: pip install pymongo
"""

import os
import sys
import argparse
import logging

from pymongo import ASCENDING, DESCENDING, TEXT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("indexes")


def get_db():
    from pymongo import MongoClient
    uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
    name = os.environ.get("MONGODB_DB") or os.environ.get("MONGO_DB", "druggraph")
    return MongoClient(uri)[name]


def ensure(coll, keys, dry: bool, **opts):
    existing = coll.index_information()
    # ¿ya existe un índice con esa misma especificación de claves?
    want = [(k, v) for k, v in keys]
    for name, info in existing.items():
        if info.get("key") == want:
            log.info("  = ya existe %s sobre %s", name, want)
            return
    if dry:
        log.info("  + (dry-run) crearía índice sobre %s %s", keys, opts or "")
        return
    name = coll.create_index(keys, **opts)
    log.info("  + creado %s sobre %s %s", name, keys, opts or "")


def drop_if_exists(coll, index_name: str, dry: bool):
    if index_name in coll.index_information():
        if dry:
            log.info("  - (dry-run) eliminaría índice %s", index_name)
        else:
            coll.drop_index(index_name)
            log.info("  - eliminado índice sin uso: %s", index_name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    dry = args.dry_run

    db = get_db()
    log.info("Base: %s", db.name)

    # ── drugs ──────────────────────────────────────────────────────────────────
    log.info("drugs:")
    ensure(db.drugs, [("type", ASCENDING)], dry)
    ensure(db.drugs, [("groups", ASCENDING)], dry)              # multikey (array de grupos)
    ensure(db.drugs, [("drugbank-id.value", ASCENDING)], dry)   # detalle fallback IDs estructurados
    # Índice de texto para acelerar la búsqueda por palabra sobre `name`.
    # No se incluye synonyms.value: sus sub-documentos llevan un campo `language`
    # (english/spanish/german) que este MongoDB rechaza como override de texto al
    # construir. Las búsquedas que solo coinciden por sinónimo caen al regex.
    has_text = any(
        any("text" in str(v) for k, v in info.get("key", []))
        for info in db.drugs.index_information().values()
    )
    if has_text:
        log.info("  = ya existe índice de texto sobre name (drug_text)")
    elif dry:
        log.info("  + (dry-run) crearía índice de texto drug_text sobre name")
    else:
        db.drugs.create_index([("name", TEXT)], name="drug_text", default_language="none")
        log.info("  + creado índice de texto drug_text sobre name")

    # ── ctd_gene_interactions: quitar índices sin uso ──────────────────────────
    log.info("ctd_gene_interactions:")
    if "ctd_gene_interactions" in db.list_collection_names():
        drop_if_exists(db.ctd_gene_interactions, "chemical_count_1", dry)
        drop_if_exists(db.ctd_gene_interactions, "interaction_count_1", dry)
    else:
        log.info("  (colección no existe aún)")

    # ── reports: historial de informes IA por usuario ─────────────────────────
    log.info("reports:")
    ensure(db.reports, [("user_id", ASCENDING), ("created_at", DESCENDING)], dry)

    # ── Tier 4: mapa de espacio químico (una fila por fármaco) ────────────────
    log.info("chemical_space:")
    ensure(db.chemical_space, [("drugbank_id", ASCENDING)], dry, unique=True)
    # model_metrics usa _id = nombre del modelo (find_one por _id), no requiere índice extra.

    # ── users: garantizar unicidad de email ────────────────────────────────────
    log.info("users:")
    info = db.users.index_information().get("email_1")
    if info and info.get("unique"):
        log.info("  = email_1 ya es único")
    elif not dry:
        # recrea como único si existía sin unique
        try:
            if info:
                db.users.drop_index("email_1")
            db.users.create_index([("email", ASCENDING)], unique=True, name="email_1")
            log.info("  + email_1 (unique) creado")
        except Exception as exc:
            log.warning("  ! no se pudo forzar unique en email (¿duplicados?): %s", exc)

    log.info("Listo.")


if __name__ == "__main__":
    main()
