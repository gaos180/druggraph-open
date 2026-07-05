# Estado del dataset — DrugGraph Open

_Última actualización: 2026-07-05._

Este documento resume **qué datos hay cargados** en el stack de DrugGraph Open, **qué
quedó pendiente** y **por qué**, más el **orden serial "memory-safe"** con el que se
pobló (y la lección de infraestructura que lo motiva).

Fuentes, licencias y mapeos de campo: [`../backend/scripts/ingest/README.md`](../backend/scripts/ingest/README.md)
y [`DATA_SOURCES.md`](DATA_SOURCES.md).

---

## Qué está cargado

Datos reales de **DrugCentral** (dump `drugcentral.dump.11012023`) más enriquecedores open.

### MongoDB — colección `drugs` (4995 fármacos)

| Métrica | Conteo |
|---------|-------:|
| Fármacos totales | **4995** |
| Con SMILES | 4310 |
| Con propiedades fisicoquímicas de PubChem | 4714 |
| Con mecanismo de acción de ChEMBL | 1888 |

### Neo4j — grafo de interacción molecular

| Relación / nodo | Conteo | Origen |
|-----------------|-------:|--------|
| `:Target` (dianas) | **16947** | `step03_build_graph` + `populate_targets --uniprot` |
| `(:Gene)-[:REGULATES {sign}]->(:Gene)` | **16778** | `load_kegg_regulatory` (KEGG KGML) |
| `(:Drug)-[:STITCH_TARGET]->(:Target)` | **17441** | `step05_stitch_cpi` (STITCH CPI) |
| `(:Drug)-[:INTERACTS_WITH]-(:Drug)` | **147982** | `step04_ddi_open` (TWOSIDES, modo nombre dedup) |
| Fingerprints Morgan (`:Drug.fingerprint`) | **4310** | `populate_fingerprints` |

---

## Qué quedó pendiente

- **STRING bulk `(:Gene)-[:STRING_ASSOC]->(:Gene)`** (`scripts/load_string_network.py`) —
  **DIFERIDO**. La red PPI humana completa (score ≥ 700, millones de aristas) es
  demasiado pesada para la RAM del equipo actual y tumba Neo4j durante la carga. Sin ella
  quedan inactivas las funciones que dependen del interactoma STRING local:
  la **cascada por difusión** (Personalized PageRank) y la **proximidad de red**
  (`proximity_service`, que lanza `ProximityUnavailable`). La **cascada dirigida/con
  signo** sí funciona (usa `:REGULATES` de KEGG, ya cargado). Para habilitarlo hace falta
  una máquina con memoria holgada; el paso está comentado al final de `run_ingest.sh`.

---

## Orden serial "memory-safe"

El orquestador [`../run_ingest.sh`](../run_ingest.sh) ejecuta el pipeline completo en este
orden:

0. `docker compose up -d` — Mongo (27018) · Neo4j (7688) · Postgres (5434).
1. `restore_dumps.sh` — dump DrugCentral → Postgres de staging.
2. `step01_drugcentral_to_mongo` → Mongo `drugs`.
3. `step03_build_graph` → Neo4j (`:Drug`/`:Target`/`:Category`).
4. `populate_targets.py --uniprot` → colección `targets` + UniProt.
5. `populate_fingerprints.py` → Morgan fingerprints.
6. **Bloque Neo4j SERIAL** (una carga a la vez, con espera de salud entre cada una):
   `load_kegg_regulatory` → `step05_stitch_cpi` → `prepare_ddi_stitch` (modo nombre,
   dedup) → `step04_ddi_open`.
7. Enriquecedores Mongo (ligeros): `step02_chembl_enrich --source api`, `step07_pubchem`,
   `step06_opentargets`.
8. `ensure_indexes.py` + `seed_admin.py`.

Paso opcional (comentado): `load_string_network.py` — ver "Qué quedó pendiente".

---

## Lección clave: Neo4j y la concurrencia en equipos con poca RAM

En equipos con poca RAM (swap lleno) **Neo4j NO soporta escrituras concurrentes**: dos
cargas simultáneas al grafo saturan heap + pagecache y el contenedor se cae o queda
inestable. Por eso el **bloque 6** es estrictamente **serial**: cada carga que escribe en
Neo4j se lanza de una en una y sólo después de que la base vuelva a estar sana
(`wait_neo4j`, un `until cypher-shell "RETURN 1;"`).

Como todos los scripts de carga son **idempotentes** (usan `MERGE`/upsert), reintentar un
paso que se cayó es siempre seguro: no duplica datos.

Detalle adicional de memoria en la DDI: `prepare_ddi_stitch` se corre en **modo nombre**,
que **deduplica por par no ordenado**. TWOSIDES trae una fila por `(par, evento adverso)`
—millones de filas—; sin dedup el CSV y la carga a Neo4j serían inviables en este equipo.
