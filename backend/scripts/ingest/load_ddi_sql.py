"""Proyecta las DDI de MongoDB a la tabla relacional `ddi` de PostgreSQL.

Decisión de diseño (usuario): los DDI viven en DOS almacenes.
  - **SQL (esta tabla `ddi`)** — consultas tabulares rápidas del verificador.
  - **Neo4j `:INTERACTS_WITH`** — se conserva tal cual para consultas de grafo.
    Este script NO toca Neo4j.

Lee el array `drug-interactions` de cada documento de `db.drugs` (denormalizado en
ambas direcciones), deduplica a pares NO ordenados (`drug_a < drug_b`) y hace UPSERT
por lotes en `ddi`. Idempotente: reejecutarlo no duplica ni cambia el conteo.

Uso (desde backend/, con Postgres arriba):
    python -m scripts.ingest.load_ddi_sql
    python -m scripts.ingest.load_ddi_sql --batch 5000
"""
from __future__ import annotations

import argparse

from scripts.ingest._common import chunked, log, mongo_db
from config.services import ddi_service


def _to_severity(value) -> float | None:
    """La severity en Mongo viene como string ('20.0') o None; a real o None."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _collect_pairs(db) -> dict[tuple[str, str], dict]:
    """Recorre los fármacos y deduplica a pares no ordenados (drug_a < drug_b).

    Cada par aparece dos veces en Mongo (denormalizado en ambas direcciones); nos
    quedamos con la primera aparición no vacía. Devuelve {(a, b): {desc, sev, src}}.
    """
    pairs: dict[tuple[str, str], dict] = {}
    cursor = db.drugs.find(
        {"drug-interactions": {"$exists": True, "$ne": []}},
        {"drugbank-id": 1, "drug-interactions": 1},
    )
    n_docs = 0
    n_items = 0
    for doc in cursor:
        me = doc.get("drugbank-id")
        if not me:
            continue
        n_docs += 1
        for item in doc.get("drug-interactions") or []:
            other = item.get("drugbank-id")
            if not other or other == me:
                continue
            n_items += 1
            a, b = ddi_service.normalize_pair(me, other)
            key = (a, b)
            if key in pairs:
                continue
            pairs[key] = {
                "description": item.get("description"),
                "severity": _to_severity(item.get("severity")),
                "source": item.get("source"),
            }
    log.info("Recorridos %d fármacos, %d items DDI → %d pares únicos",
             n_docs, n_items, len(pairs))
    return pairs


def load(batch_size: int = 5000) -> int:
    db = mongo_db()
    ddi_service.ensure_schema()
    pairs = _collect_pairs(db)

    rows = [
        (a, b, v["description"], v["severity"], v["source"])
        for (a, b), v in pairs.items()
    ]

    conn = ddi_service.get_connection()
    try:
        upsert = """
            INSERT INTO ddi (drug_a, drug_b, description, severity, source)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (drug_a, drug_b) DO UPDATE SET
                description = EXCLUDED.description,
                severity    = EXCLUDED.severity,
                source      = EXCLUDED.source
        """
        total = 0
        with conn.cursor() as cur:
            for batch in chunked(rows, batch_size):
                cur.executemany(upsert, batch)
                total += len(batch)
                log.info("UPSERT %d/%d pares", total, len(rows))
        cur2 = conn.execute("SELECT count(*) FROM ddi")
        count = cur2.fetchone()[0]
    finally:
        conn.close()

    log.info("Tabla `ddi`: %d pares en total (upserted %d)", count, len(rows))
    return count


def main() -> None:
    ap = argparse.ArgumentParser(description="Carga DDI de Mongo → tabla SQL `ddi`.")
    ap.add_argument("--batch", type=int, default=5000, help="Tamaño de lote UPSERT.")
    args = ap.parse_args()
    load(batch_size=args.batch)


if __name__ == "__main__":
    main()
