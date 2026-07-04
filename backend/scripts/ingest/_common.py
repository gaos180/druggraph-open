"""Utilidades compartidas por el pipeline de ingesta.

Bootstrap de Django (para reutilizar settings + los servicios mongo/neo4j/postgres),
esquema del ID abierto y helpers de logging/chunking.
"""
from __future__ import annotations

import os
import sys
import logging
from pathlib import Path

# ── Bootstrap de Django ────────────────────────────────────────────────────────
# Los scripts de ingesta corren como `python -m scripts.ingest.stepNN` desde backend/.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

try:
    django.setup()
except Exception:  # pragma: no cover - ya configurado
    pass

from django.conf import settings  # noqa: E402

log = logging.getLogger("ingest")
if not log.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )


# ── Esquema de ID abierto ──────────────────────────────────────────────────────
def open_id(struct_id: int | str) -> str:
    """DrugCentral struct_id → ID primario abierto (p.ej. 1234 → 'DC1234')."""
    return f"{settings.OPEN_ID_PREFIX}{struct_id}"


def struct_id_from_open(oid: str) -> str:
    """Inversa de open_id: 'DC1234' → '1234'."""
    prefix = settings.OPEN_ID_PREFIX
    return oid[len(prefix):] if oid.startswith(prefix) else oid


# ── Conexiones (reutilizan los servicios de la app) ────────────────────────────
def mongo_db():
    from config.services.mongo import get_db
    return get_db()


def neo4j_driver():
    from config.services.neo4j_service import get_driver
    return get_driver()


def staging_conn(dbname: str | None = None, autocommit: bool = True):
    """Conexión al Postgres de staging (o a una base restaurada concreta)."""
    from config.services.postgres import get_connection
    return get_connection(dbname=dbname, autocommit=autocommit)


# ── Helpers ────────────────────────────────────────────────────────────────────
def chunked(iterable, size: int):
    """Parte un iterable en lotes de `size` (para inserciones/UNWIND por lotes)."""
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch
