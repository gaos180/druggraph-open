"""Servicio de interacciones fármaco–fármaco (DDI) sobre PostgreSQL.

Decisión de diseño: los DDI viven en DOS almacenes simultáneos.
  - **SQL (Postgres, tabla `ddi`)** — consultas tabulares rápidas del verificador de
    DDI (este módulo). Cada par se guarda UNA sola vez, normalizado `drug_a < drug_b`.
  - **Neo4j `:INTERACTS_WITH`** — se conserva tal cual para consultas de grafo
    (cadenas, vecindarios). Este módulo NO lo toca.

La fuente de verdad denormalizada sigue siendo el array `drug-interactions` de cada
documento en MongoDB; `scripts/ingest/load_ddi_sql.py` proyecta esos pares a la tabla
`ddi`. Aquí solo se lee (más `ensure_schema`, idempotente).

`PostgresUnavailable` se propaga hacia el caller, que degrada con 503.
"""
from __future__ import annotations

from config.services.postgres import PostgresUnavailable, get_connection

__all__ = [
    "PostgresUnavailable",
    "ensure_schema",
    "interactions_for",
    "check_pair",
    "normalize_pair",
]


def normalize_pair(a: str, b: str) -> tuple[str, str]:
    """Ordena un par para que siempre se almacene/consulte con drug_a < drug_b."""
    return (a, b) if a <= b else (b, a)


def ensure_schema() -> None:
    """Crea (idempotente) la tabla `ddi` + índices en drug_a y drug_b."""
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ddi (
                drug_a      text,
                drug_b      text,
                description text,
                severity    real,
                source      text,
                PRIMARY KEY (drug_a, drug_b)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS ddi_drug_a_idx ON ddi (drug_a)")
        conn.execute("CREATE INDEX IF NOT EXISTS ddi_drug_b_idx ON ddi (drug_b)")
    finally:
        conn.close()


def interactions_for(drug_id: str, enrich_names: bool = True) -> list[dict]:
    """Todas las DDI de `drug_id`: el OTRO fármaco + description/severity/source.

    Ordenado por severity descendente (NULLS last). Si `enrich_names`, completa el
    nombre del otro fármaco desde MongoDB (best-effort; ignora errores de Mongo).
    """
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT
                CASE WHEN drug_a = %(id)s THEN drug_b ELSE drug_a END AS other,
                description,
                severity,
                source
            FROM ddi
            WHERE drug_a = %(id)s OR drug_b = %(id)s
            ORDER BY severity DESC NULLS LAST
            """,
            {"id": drug_id},
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    results = [
        {
            "drugbank_id": other,
            "name": "",
            "description": description,
            "severity": severity,
            "source": source,
        }
        for (other, description, severity, source) in rows
    ]

    if enrich_names and results:
        _fill_names(results)
    return results


def check_pair(a: str, b: str) -> dict | None:
    """Devuelve la interacción entre A y B (o None si no interactúan)."""
    drug_a, drug_b = normalize_pair(a, b)
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT drug_a, drug_b, description, severity, source
            FROM ddi
            WHERE drug_a = %(a)s AND drug_b = %(b)s
            """,
            {"a": drug_a, "b": drug_b},
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None
    return {
        "drug_a": row[0],
        "drug_b": row[1],
        "description": row[2],
        "severity": row[3],
        "source": row[4],
    }


def _fill_names(results: list[dict]) -> None:
    """Enriquece `name` de cada resultado desde MongoDB (best-effort)."""
    try:
        from config.services.mongo import get_db

        db = get_db()
        ids = [r["drugbank_id"] for r in results]
        name_by_id: dict[str, str] = {}
        for doc in db.drugs.find(
            {"drugbank-id": {"$in": ids}}, {"drugbank-id": 1, "name": 1}
        ):
            name_by_id[doc.get("drugbank-id")] = doc.get("name", "")
        for r in results:
            r["name"] = name_by_id.get(r["drugbank_id"], "")
    except Exception:  # noqa: BLE001 - enriquecimiento opcional, nunca rompe la consulta
        pass
