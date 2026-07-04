# Pipeline de ingesta open-source

Puebla MongoDB (`druggraph_open`) + Neo4j desde datos redistribuibles, produciendo el
mismo esquema que consumía DrugGraph sobre DrugBank. Ver atribuciones y mapeo de campos
en [`docs/DATA_SOURCES.md`](../../../docs/DATA_SOURCES.md).

## Prerrequisitos

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-ingest.txt      # psycopg, tqdm…

# Stack de BD aislado (Mongo 27018 / Neo4j 7688 / Postgres 5433)
docker compose up -d          # desde la raíz del proyecto
```

Descarga los dumps (no se versionan — varios GB):
- **DrugCentral** (obligatorio): https://drugcentral.org/download → `drugcentral.dump.*.sql.gz`
- **ChEMBL** (opcional, enriquecimiento): https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/latest/

## Orden de ejecución

```bash
cd backend

# 0. Restaurar los dumps SQL en el Postgres de staging
bash scripts/ingest/restore_dumps.sh /ruta/drugcentral.dump.sql.gz [/ruta/chembl_dump]

# 1. DrugCentral → Mongo `drugs`  (backbone del catálogo)
python -m scripts.ingest.step01_drugcentral_to_mongo
#    prueba rápida sin cargar todo:  --limit 200

# 2. (opcional) Enriquecer con ChEMBL (MoA, SMILES canónico)
python -m scripts.ingest.step02_chembl_enrich --source postgres   # o --source api

# 3. Mongo → grafo Neo4j (:Drug/:Target/:Category + TARGETS/IN_CATEGORY)
python -m scripts.ingest.step03_build_graph

# 4. DDI open (reemplaza las DDI de DrugBank) — TWOSIDES (CC0) por defecto
python -m scripts.ingest.step04_ddi_open --csv data/ddi_twosides.csv --source TWOSIDES
```

## Enriquecedores heredados (ya eran open — se reutilizan tal cual)

Tras los pasos 1–3, corre los scripts existentes de `scripts/` para completar dianas,
fingerprints y las redes de pathways/propagación (idénticos a DrugGraph):

```bash
python scripts/populate_targets.py --uniprot    # colección Mongo `targets` + UniProt
python scripts/populate_uniprot.py              # enriquecer :Target con UniProt canónico
python scripts/populate_fingerprints.py         # Morgan fingerprints (sandbox)  [necesita rdkit]
python scripts/load_ctd_interactions.py         # CTD (chem-gene) — colección ctd_gene_interactions
python scripts/load_string_network.py           # STRING bulk → :STRING_ASSOC (cascada difusión)
python scripts/load_kegg_regulatory.py          # KEGG KGML → :REGULATES (cascada dirigida)
python scripts/ensure_indexes.py                # índices Mongo
python scripts/seed_admin.py                    # usuario admin inicial
```

Opcionales avanzados (Tier 3.2 / Tier 4), igual que en DrugGraph:
`populate_chemberta_embeddings.py`, `build_chemical_space.py`, `train_dti_gnn.py`,
`train_admet_models.py`.

## Notas

- **step04 / DDI**: el CSV normalizado (`name_a,name_b,description,severity`) resuelve
  fármacos por nombre contra el catálogo ya cargado. TWOSIDES crudo usa STITCH CIDs;
  prepara el crosswalk STITCH→nombre antes (o usa DDInter, académico). Sin DDI el
  verificador documentado queda vacío, pero el **riesgo PK/PD predicho** sigue operativo.
- **Modo prueba**: `step01 --limit 200` + `step03` levanta un grafo pequeño en minutos
  para validar la app end-to-end sin cargar el catálogo completo.
- Los pasos son idempotentes: puedes re-correrlos (usan upsert/MERGE).
