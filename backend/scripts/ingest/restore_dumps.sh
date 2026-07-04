#!/usr/bin/env bash
# Restaura los dumps PostgreSQL de DrugCentral y (opcional) ChEMBL en el Postgres de
# staging del stack DrugGraph Open (contenedor druggraph-open-postgres, puerto 5433).
#
# Prerrequisitos:
#   docker compose up -d postgres
#   Descargar los dumps (no se versionan — pesan varios GB):
#     DrugCentral:  https://drugcentral.org/download   (drugcentral.dump.<fecha>.sql.gz)
#     ChEMBL:       https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/latest/
#                   (chembl_XX_postgresql.tar.gz)  — OPCIONAL, solo si vas a enriquecer
#
# Uso:
#   bash scripts/ingest/restore_dumps.sh /ruta/drugcentral.dump.sql.gz [/ruta/chembl_pg_dump]
set -euo pipefail

PGHOST="${POSTGRES_HOST:-localhost}"
PGPORT="${POSTGRES_PORT:-5433}"
PGUSER="${POSTGRES_USER:-druggraph}"
export PGPASSWORD="${POSTGRES_PASSWORD:-druggraphopen123}"

DRUGCENTRAL_DUMP="${1:-}"
CHEMBL_DUMP="${2:-}"

if [[ -z "$DRUGCENTRAL_DUMP" ]]; then
  echo "Uso: $0 <drugcentral.dump.sql.gz> [chembl_dump]" >&2
  exit 1
fi

echo ">> Creando base 'drugcentral' en el Postgres de staging…"
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d staging \
  -c "DROP DATABASE IF EXISTS drugcentral;" -c "CREATE DATABASE drugcentral;"

echo ">> Restaurando DrugCentral (esto tarda unos minutos)…"
# El dump de DrugCentral es SQL plano comprimido con gzip.
gunzip -c "$DRUGCENTRAL_DUMP" | psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d drugcentral

echo ">> DrugCentral restaurado. Tablas clave:"
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d drugcentral -c "\dt" | grep -E \
  "structures|identifier|act_table_full|pharma_class|omop_relationship|approval|structure_type" || true

if [[ -n "$CHEMBL_DUMP" ]]; then
  echo ">> Restaurando ChEMBL (opcional)…"
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d staging \
    -c "DROP DATABASE IF EXISTS chembl;" -c "CREATE DATABASE chembl;"
  # El dump de ChEMBL es un pg_dump custom (usa pg_restore). Ajusta si descargaste el .sql.
  pg_restore -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d chembl --no-owner -j 4 "$CHEMBL_DUMP"
  echo ">> ChEMBL restaurado."
fi

echo ">> Listo. Siguiente paso: python -m scripts.ingest.step01_drugcentral_to_mongo"
