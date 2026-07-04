"""Conexión a la capa de STAGING PostgreSQL (solo pipeline de ingesta).

DrugCentral y ChEMBL se distribuyen como dumps PostgreSQL nativos. Se restauran en
este Postgres (contenedor druggraph-open-postgres, puerto 5433) y desde aquí el ETL
de scripts/ingest/ proyecta a MongoDB (documentos) y Neo4j (grafo).

La app en runtime NO usa esta conexión: es exclusiva de los scripts de ingesta. Por eso
`psycopg` es una dependencia opcional (requirements-ingest.txt) y este módulo degrada con
un mensaje claro si no está instalado.
"""
from django.conf import settings

try:
    import psycopg  # psycopg 3
    _HAS_PSYCOPG = True
except ImportError:  # pragma: no cover - dependencia opcional de ingesta
    psycopg = None
    _HAS_PSYCOPG = False


class PostgresUnavailable(RuntimeError):
    """psycopg no instalado o Postgres de staging inaccesible."""


def _dsn(dbname: str | None = None) -> str:
    cfg = settings.DATABASES_NOSQL['postgres']
    name = dbname or cfg['NAME']
    return (
        f"host={cfg['HOST']} port={cfg['PORT']} "
        f"user={cfg['USER']} password={cfg['PASSWORD']} dbname={name}"
    )


def get_connection(dbname: str | None = None, autocommit: bool = True):
    """Devuelve una conexión psycopg al Postgres de staging.

    `dbname` permite conectarse a una base distinta (p.ej. la base restaurada de
    DrugCentral o ChEMBL, que suelen crearse con su propio nombre) sin cambiar la
    config global. Por defecto usa POSTGRES_DB ('staging').
    """
    if not _HAS_PSYCOPG:
        raise PostgresUnavailable(
            "psycopg no está instalado. Instala las deps de ingesta:\n"
            "    pip install -r requirements-ingest.txt"
        )
    try:
        return psycopg.connect(_dsn(dbname), autocommit=autocommit)
    except Exception as exc:  # noqa: BLE001
        raise PostgresUnavailable(
            f"No se pudo conectar al Postgres de staging ({_dsn(dbname)}): {exc}\n"
            "¿Levantaste el stack?  docker compose up -d postgres"
        ) from exc
