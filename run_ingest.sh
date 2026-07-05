#!/usr/bin/env bash
# =============================================================================
# run_ingest.sh — Orquestador ÚNICO del pipeline de ingesta de DrugGraph Open.
#
# Ejecuta TODO el pipeline `backend/scripts/ingest/` (+ los enriquecedores
# heredados de `backend/scripts/`) en el ORDEN SERIAL "memory-safe" con el que
# se pobló el stack real (DrugCentral + TWOSIDES + STITCH + KEGG + Open Targets
# + PubChem + ChEMBL).
#
# -----------------------------------------------------------------------------
# LECCIÓN CLAVE (por qué este script existe y por qué el BLOQUE 6 es SERIAL):
# -----------------------------------------------------------------------------
# En equipos con poca RAM (swap lleno) Neo4j NO soporta escrituras CONCURRENTES:
# dos cargas simultáneas al grafo saturan el heap/pagecache y el contenedor se
# cae o queda inestable. Por eso todas las cargas que ESCRIBEN en Neo4j se
# ejecutan de UNA EN UNA, esperando a que la base vuelva a estar SANA
# (`wait_neo4j`) antes de lanzar la siguiente. Como los scripts son idempotentes
# (MERGE/upsert), reintentar un paso caído es siempre seguro.
#
# STRING bulk (`load_string_network.py`) queda como paso OPCIONAL COMENTADO al
# final: la red PPI completa (~11M aristas) no cabe en la RAM de este equipo y
# tumba Neo4j. Descoméntalo solo en una máquina con memoria holgada.
#
# -----------------------------------------------------------------------------
# USO:
#   ./run_ingest.sh                        # usa las rutas por defecto de data/
#   ./run_ingest.sh /ruta/drugcentral.dump.sql.gz
#
# Requisitos previos:
#   - Docker + docker compose.
#   - backend/venv/ con requirements.txt + requirements-ingest.txt instalados.
#   - Los datos crudos descargados en data/ (ver docs/DATASET_STATE.md y
#     backend/scripts/ingest/README.md).
#
# NO carga datos por su cuenta más allá de lo aquí orquestado; NO edita .env ni
# docker-compose.yml.
# =============================================================================
set -euo pipefail

# ── Rutas base ───────────────────────────────────────────────────────────────
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
DATA_DIR="$ROOT/data"
PY="$BACKEND/venv/bin/python"     # intérprete del venv del clon (no el del sistema)

# ── Datos crudos (ajústalos si tus ficheros tienen otro nombre) ──────────────
DRUGCENTRAL_DUMP="${1:-$DATA_DIR/drugcentral.dump.11012023.sql.gz}"
# TWOSIDES crudo (nSIDES, CC0). Se normaliza a un CSV DEDUPLICADO por par.
TWOSIDES_RAW="$DATA_DIR/TWOSIDES.csv.gz"
DDI_CSV="$DATA_DIR/ddi_open.csv"                 # salida de prepare_ddi_stitch
# STITCH químico-proteína (CPI) + crosswalk ENSP→gen.
STITCH_LINKS="$DATA_DIR/9606.protein_chemical.links.detailed.v5.0.tsv.gz"
STRING_INFO="$DATA_DIR/9606.protein.info.v12.0.txt.gz"
# Tope de pares DDI únicos (memory-safe: acota lo que se escribe en Neo4j).
DDI_MAX_PAIRS="${DDI_MAX_PAIRS:-200000}"

# ── Config Neo4j (contenedor aislado del stack Open) ─────────────────────────
NEO4J_CONTAINER="druggraph-open-neo4j"
NEO4J_USER="neo4j"
NEO4J_PASS="druggraphopen123"

# ── Config Postgres de staging ───────────────────────────────────────────────
# docker-compose mapea el host a POSTGRES_HOST_PORT (5434 en .env). restore_dumps.sh
# lee POSTGRES_PORT (default 5433), así que lo exportamos para que apunte al puerto real.
export POSTGRES_PORT="${POSTGRES_HOST_PORT:-5434}"

# ── Utilidades ───────────────────────────────────────────────────────────────
step() { echo; echo "════════════════════════════════════════════════════════"; \
         echo ">> $*"; echo "════════════════════════════════════════════════════════"; }

# Espera bloqueante hasta que Neo4j responda un Cypher trivial. Se llama ANTES de
# cada carga que escribe en el grafo, para no encadenar escrituras concurrentes.
wait_neo4j() {
  echo ">> Esperando a que Neo4j ($NEO4J_CONTAINER) esté sano…"
  until docker exec "$NEO4J_CONTAINER" \
        cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASS" "RETURN 1;" >/dev/null 2>&1; do
    echo "   … Neo4j aún no responde; reintento en 5 s"
    sleep 5
  done
  echo ">> Neo4j OK."
}

# Todos los `python -m scripts.ingest.*` deben correr desde backend/.
run_py() { ( cd "$BACKEND" && "$PY" "$@" ); }

# ═════════════════════════════════════════════════════════════════════════════
# PASO 0 — Levantar el stack de bases de datos (Mongo 27018 / Neo4j 7688 /
#          Postgres 5434). Postgres puede tardar en aceptar conexiones.
# ═════════════════════════════════════════════════════════════════════════════
step "0. docker compose up -d (Mongo + Neo4j + Postgres)"
( cd "$ROOT" && docker compose up -d )
wait_neo4j

# ═════════════════════════════════════════════════════════════════════════════
# PASO 1 — Restaurar el dump SQL de DrugCentral en el Postgres de staging.
# ═════════════════════════════════════════════════════════════════════════════
step "1. Restaurar DrugCentral en Postgres de staging"
bash "$BACKEND/scripts/ingest/restore_dumps.sh" "$DRUGCENTRAL_DUMP"

# ═════════════════════════════════════════════════════════════════════════════
# PASO 2 — DrugCentral (Postgres) → Mongo `drugs` (backbone del catálogo).
# ═════════════════════════════════════════════════════════════════════════════
step "2. step01_drugcentral_to_mongo → Mongo drugs"
run_py -m scripts.ingest.step01_drugcentral_to_mongo

# ═════════════════════════════════════════════════════════════════════════════
# PASO 3 — Mongo → grafo Neo4j (:Drug/:Target/:Category + TARGETS/IN_CATEGORY).
#          Primera escritura al grafo → espera de salud antes.
# ═════════════════════════════════════════════════════════════════════════════
step "3. step03_build_graph → Neo4j (:Drug/:Target/:Category)"
wait_neo4j
run_py -m scripts.ingest.step03_build_graph

# ═════════════════════════════════════════════════════════════════════════════
# PASO 4 — Poblar/normalizar la colección Mongo `targets` + UniProt.
# ═════════════════════════════════════════════════════════════════════════════
step "4. populate_targets.py --uniprot"
wait_neo4j
run_py scripts/populate_targets.py --uniprot

# ═════════════════════════════════════════════════════════════════════════════
# PASO 5 — Morgan fingerprints en :Drug (prerequisito del sandbox estructural).
#          Escribe en Neo4j (propiedad d.fingerprint) → espera de salud.
# ═════════════════════════════════════════════════════════════════════════════
step "5. populate_fingerprints.py (necesita rdkit)"
wait_neo4j
run_py scripts/populate_fingerprints.py

# ═════════════════════════════════════════════════════════════════════════════
# PASO 6 — BLOQUE NEO4J *SERIAL* (una carga a la vez, con wait_neo4j entre cada
#          una). En equipos con poca RAM Neo4j NO aguanta escrituras concurrentes;
#          serializar es la única forma estable de cargar estas redes pesadas.
# ═════════════════════════════════════════════════════════════════════════════
step "6. BLOQUE NEO4J SERIAL — KEGG :REGULATES · STITCH :STITCH_TARGET · DDI :INTERACTS_WITH"

# 6a) KEGG KGML → (:Gene)-[:REGULATES {sign}]->(:Gene) (cascada dirigida/con signo).
wait_neo4j
run_py scripts/load_kegg_regulatory.py

# 6b) STITCH CPI → (:Drug)-[:STITCH_TARGET]->(:Target). --info da el crosswalk
#     ENSP→gen; --min-score 700 filtra por confianza; --create-missing materializa
#     :Target sintéticos por ENSP cuando no exista uno con ese gen.
wait_neo4j
run_py -m scripts.ingest.step05_stitch_cpi \
  --links "$STITCH_LINKS" \
  --info "$STRING_INFO" \
  --min-score 700 \
  --create-missing

# 6c) DDI: primero NORMALIZAR el crudo a un CSV. Usamos el MODO NOMBRE
#     (--source ddinter) porque DEDUPLICA por par NO ORDENADO: TWOSIDES trae una
#     fila por (par, evento adverso) → millones de filas. Sin dedup la carga a
#     Neo4j sería inviable en este equipo. `--max-pairs` acota el total escrito.
#     (Transformación fichero→fichero: no toca la BD, no requiere wait_neo4j.)
run_py -m scripts.ingest.prepare_ddi_stitch \
  --source ddinter \
  --twosides "$TWOSIDES_RAW" \
  --out "$DDI_CSV" \
  --max-pairs "$DDI_MAX_PAIRS"

# 6d) Cargar las DDI normalizadas → (:Drug)-[:INTERACTS_WITH]-(:Drug) + array
#     drug-interactions en Mongo. El modo (cid/name) se autodetecta por columnas.
wait_neo4j
run_py -m scripts.ingest.step04_ddi_open \
  --csv "$DDI_CSV" \
  --source TWOSIDES

# ═════════════════════════════════════════════════════════════════════════════
# PASO 7 — Enriquecedores Mongo (LIGEROS: no escriben en Neo4j, no compiten por
#          el heap del grafo; pueden ir seguidos).
# ═════════════════════════════════════════════════════════════════════════════
step "7. Enriquecedores Mongo — ChEMBL (MoA) · PubChem (fisicoquímica) · Open Targets"

# 7a) ChEMBL: mecanismo de acción / SMILES canónico. --source api evita depender
#     del dump de ChEMBL en Postgres.
run_py -m scripts.ingest.step02_chembl_enrich --source api

# 7b) PubChem: propiedades fisicoquímicas por CID → campo pubchem_properties.
run_py -m scripts.ingest.step07_pubchem

# 7c) Open Targets: evidencia diana→enfermedad → campo open_targets_diseases.
run_py -m scripts.ingest.step06_opentargets

# ═════════════════════════════════════════════════════════════════════════════
# PASO 8 — Índices Mongo + usuario admin inicial.
# ═════════════════════════════════════════════════════════════════════════════
step "8. ensure_indexes.py + seed_admin.py"
run_py scripts/ensure_indexes.py
run_py scripts/seed_admin.py

# ═════════════════════════════════════════════════════════════════════════════
# PASO OPCIONAL — STRING bulk (:Gene)-[:STRING_ASSOC]->(:Gene) para la cascada de
# DIFUSIÓN. DESACTIVADO por defecto: la red PPI humana completa (score ≥ 700)
# es demasiado pesada para la RAM de este equipo y tumba Neo4j. Descoméntalo SOLO
# en una máquina con memoria holgada, y siempre dentro del bloque serial.
# -----------------------------------------------------------------------------
# step "OPCIONAL. load_string_network.py → :STRING_ASSOC (ADVERTENCIA: RAM alta)"
# wait_neo4j
# run_py scripts/load_string_network.py \
#   --links "$DATA_DIR/9606.protein.links.v12.0.txt.gz" \
#   --info  "$STRING_INFO" \
#   --min-score 700
# ═════════════════════════════════════════════════════════════════════════════

step "PIPELINE COMPLETO ✓"
echo "Revisa docs/DATASET_STATE.md para los conteos esperados."
