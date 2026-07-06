# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**DrugGraph Open** is the open-data edition of DrugGraph: same platform and tools, but the
proprietary **DrugBank** catalog is replaced by **open, redistributable sources**
(DrugCentral, ChEMBL, Open Targets, PubChem, UniProt, CTD). See `docs/DATA_SOURCES.md`
for the source→field mapping and `backend/scripts/ingest/` for the ingestion pipeline.

It uses **four data stores**:
- **PostgreSQL** — two roles: (1) **ingestion staging** — DrugCentral/ChEMBL ship as native
  Postgres dumps, restored here and projected by the ETL (`backend/scripts/ingest/`) into
  Mongo/Neo4j; (2) **runtime, for DDI** — the drug–drug interaction checker reads the flat
  `ddi` table (147k pairs) via `config/services/ddi_service.py` for fast tabular lookups (SQL
  is the right tool for a single-hop pairwise lookup; the graph is not). So **Postgres must be
  running at runtime** for the DDI checker (degrades to 503 otherwise). Config in
  `settings.DATABASES_NOSQL['postgres']`, accessed via `config/services/postgres.py` (dep
  `psycopg`). NOTE: the DDI **graph** edges `(:Drug)-[:INTERACTS_WITH]->(:Drug)` are ALSO kept
  in Neo4j on purpose — for advanced traversal queries (drug chains with shared reactions,
  neighborhoods). SQL = tabular lookup; Neo4j = graph analytics. Both coexist by design.
- **MongoDB** — stores user accounts and the drug documents (rich nested JSON). The document
  keeps DrugGraph's legacy field names (`drugbank-id`, `name`, `type`, `groups`, `targets`…)
  for app compatibility, but the primary ID holds an **open ID** derived from DrugCentral
  (`DC<struct_id>`, prefix in `settings.OPEN_ID_PREFIX`).
- **Neo4j** — stores the molecular interaction graph (Drug → Target, Drug → Category,
  Drug ↔ Drug, and the **`:Disease` layer** `(:Drug)-[:ASSOCIATED_WITH]->(:Disease)` from Open
  Targets, for the Tier 4.7 drug→disease repurposing GNN), including temporary `:SandboxDrug`
  nodes. `:Drug.drugbank_id` holds the open ID.
- Django's ORM is unused for the domain. Both `users/models.py` and `drugs/models.py` are empty
  stubs. `settings.DATABASES['default']` is a throwaway sqlite (only so Django's
  admin/sessions/test-runner work); the Mongo/Neo4j/Postgres connections are declared,
  engine-style, in `settings.DATABASES_NOSQL` (kept out of `DATABASES` because Django's test
  runner tries to load an ORM backend for every alias there). The singleton services in
  `config/services/` consume `DATABASES_NOSQL`, never `django.db.connections`.

The Docker stack is **isolated by ports** from an original DrugGraph on the same machine:
MongoDB **27018**, Neo4j **7475/7688**, Postgres **5433** (the host Postgres port is
configurable via `POSTGRES_HOST_PORT` in the root `.env` — this machine uses **5434** because
it already runs a system Postgres on 5433).

**Current loaded state** (see `docs/DATASET_STATE.md` for counts + the memory-safe load order):
the databases are populated from real DrugCentral (4995 drugs; Neo4j TARGETS 16947, KEGG
`:REGULATES` 16778, STITCH `:STITCH_TARGET` 17441, DDI `:INTERACTS_WITH` 147982, STRING
`:STRING_ASSOC` 100856 at score≥900; Mongo enrichers ChEMBL/PubChem/Open Targets; fingerprints
4310). **Neo4j runs on a 1 GB heap** on this machine and restarts under heavy concurrent
writes / deep `shortestPath` queries — load Neo4j layers **serially** (see `run_ingest.sh`)
and expect the permutation-heavy `proximity_significance` to need more heap for big modules.

**Network-medicine services** implemented on this substrate (from `docs/SYSTEMS_BIOLOGY_REVIEW.md`):
`propagation_service.propagate_signed` uses a **per-target sign** from the drug's action
(`sign_for_action`); `proximity_service.proximity_significance` adds a **degree-preserving
null model** (z-score/p-value, Guney 2016) behind `?significance=true`; `tools/repurposing`
weights shared targets by **information content / IDF** `log2((N+1)/(n+1))` (Resnik/Lin lineage).

External APIs used (no API key required):
- **STRING** (`string-db.org`) — PPI neighbors for indirect drug effect + functional enrichment (GO/KEGG/Reactome/WikiPathways with FDR).
- **KEGG** (`rest.kegg.jp`) — biological pathways for drug targets.
- **BLAST+** (local binary) — sequence homology search against a pre-built target index.

Bulk external datasets (downloaded once, stored locally):
- **CTD** (`ctdbase.org`) — curated chemical–gene interactions. `CTD_chem_gene_ixns.csv.gz` is loaded by `scripts/load_ctd_interactions.py` (filtered to human + Neo4j genes) into the MongoDB `ctd_gene_interactions` collection; queried via `config/services/ctd_service.py` to enrich the sandbox network analysis.
- **STRING bulk** (`stringdb-downloads.org`) — human PPI network loaded into Neo4j (not the API) for effect propagation. `9606.protein.links.v12.0.txt.gz` (filtered to score ≥ 700) is loaded by `scripts/load_string_network.py` as `(:Gene)-[:STRING_ASSOC {score}]->(:Gene)`. Used by `config/services/propagation_service.py` (Personalized PageRank via GDS) for the **diffusion** cascade mode (magnitude, undirected/unsigned) — the on-demand STRING API can't sustain multi-hop propagation.
- **KEGG KGML** (`rest.kegg.jp/get/<pathway>/kgml`) — directed signed regulatory relations. `scripts/load_kegg_regulatory.py` fetches all human pathway KGMLs, extracts activation/expression (+1) and inhibition/repression (−1) relations, and loads `(:Gene)-[:REGULATES {sign}]->(:Gene)` into Neo4j. Used by `propagation_service.propagate_signed()` for the **directed** cascade mode (activation/inhibition sign + upstream→downstream direction).

## Running the Stack

### 1. Start databases
```bash
docker compose up -d        # MongoDB (27018), Neo4j (7475/7688), Postgres (5433)
```

### 1b. Ingest open-source data (first time)
See `backend/scripts/ingest/README.md` (the definitive step list) and `run_ingest.sh` (root
orchestrator). In short: `pip install -r requirements-ingest.txt`, restore the DrugCentral
dump into the Postgres staging DB, then run the numbered `scripts.ingest.stepNN` modules in
order — `step01` DrugCentral→Mongo, `step02` ChEMBL enrich, `step03` build Neo4j graph,
`step04` DDI (TWOSIDES), `step05` STITCH chem-protein, `step06` Open Targets, `step07`
PubChem, `step08b` UniProt peptide sequences, `step08` ToxinPred (manual FASTA round-trip, no
API). Then the inherited enrichers from `scripts/` (`populate_targets.py`, `populate_uniprot.py`,
`populate_fingerprints.py`, `load_ctd_interactions.py`, `load_string_network.py`,
`load_kegg_regulatory.py`, `ensure_indexes.py`, `seed_admin.py`). Steps are idempotent
(upsert/MERGE). Use `step01 --limit 200` + `step03` for a quick end-to-end smoke test without
loading the full catalog. **Load Neo4j layers serially** — the 1 GB heap on this machine
restarts under heavy concurrent writes.

### 2. Backend (Django, port 8000)
```bash
cd backend
source venv/bin/activate    # venv lives at backend/venv/
pip install -r requirements.txt
python manage.py runserver
```

Seed admin user (first time):
```bash
python scripts/seed_admin.py        # creates admin@druggraph.dev / admin1234
```

### 3. Frontend (React, port 3000)
```bash
cd frontend
npm install
npm start
```

### Tests
```bash
# Backend
cd backend && python manage.py test

# Frontend
cd frontend && npm test

# Single backend test module
cd backend && python manage.py test drugs.tests
```

## Architecture

### Backend (`backend/`)

**No Django ORM.** All DB access goes through two service singletons:

- `config/services/mongo.py` — `get_db()` returns the `druggraph` MongoDB database (lazy singleton).
- `config/services/neo4j_service.py` — `get_driver()` returns the Neo4j driver (lazy singleton). `get_drug_graph(drugbank_id, drug_name)` runs the four Cypher queries that populate the interaction graph view.

**App: `users/`**
- Services in `users/services.py`: password hashing (bcrypt), JWT generation/verification, user CRUD in `db.users`.
- Custom DRF authentication class `MongoJWTAuthentication` (`users/authentication.py`): reads `Authorization: Bearer <token>`, decodes JWT, fetches user from MongoDB. Registered globally in `REST_FRAMEWORK` settings.
- `SimpleUser` is the request user object (not a Django model instance).

**App: `drugs/`**
- `drugs/services.py`: queries `db.drugs` (MongoDB). Uses `LIST_PROJECTION` for paginated listing (lightweight fields only) and `DETAIL_EXCLUDE` for full document retrieval. The `list_drugs()` function uses N+1 cursor strategy to detect next-page without `count_documents`. Search fast-path: for full-word terms it probes the `name` text index (`$text`, ~5 ms) and falls back to the case-insensitive regex `$or` (substring/prefix/synonyms, type-ahead) when there's no whole-word match. Indexes are managed by `scripts/ensure_indexes.py`.
- **`drugs/views/` is a package** (not a single `views.py`); its `__init__.py` re-exports the view callables so `from . import views` and `from .views import …` work. Modules:
- `drugs/views/drugs.py`: list, detail, and filter endpoints (all from MongoDB).
- `drugs/views/graph.py`: `drug_graph_view` — fetches interaction graph from Neo4j via `get_drug_graph()`.
- `drugs/views/blast.py`: BLAST sequence search endpoint. Requires `BLAST+` installed and index built with `backend/scripts/build_blast_db.py`.
- `drugs/views/gds.py`: GDS analysis endpoints (centrality, communities, link prediction). Returns 503 gracefully if Neo4j GDS plugin is not installed.
- `drugs/views/pathways.py`: combines Neo4j targets + STRING PPI + KEGG pathways.
- `drugs/views/sandbox.py`: creates temporary `:SandboxDrug` nodes in Neo4j, computes Tanimoto + Jaccard similarity, then deletes the node (TTL 30 min). Lazy sections in `similarity.py` (multi-fingerprint detail) and `embedding_similarity.py` (ChemBERTa).
- `drugs/views/stats.py`: global counters for the dashboard (`stats` auth + `stats/public` for the landing page).
- `drugs/views/targets.py`: targets browser — list/detail, UniProt profile, Neo4j graph, pathways, and two-target comparison.
- `drugs/views/bioactivity.py`: experimental bioactivity (ChEMBL + PubChem).
- `drugs/views/ddi.py` + `drugs/views/ddi_risk.py`: documented DDI lookup and predicted PK/PD interaction risk (no ML).
- `drugs/views/tools/`: analytical tools — `deg.py`, `repurposing.py`, `toxicity.py`, `proximity.py`, `disease_evidence.py`, `signature_reversion.py`, and the **Tier 4 (ML propio)** tools: `chemical_space.py` (mapa UMAP+HDBSCAN), `denovo.py` (diseño de novo), `admet.py` (ADMET supervisado), `dti_gnn.py` (predicción DTI por GNN).
- `drugs/views/reports.py`: AI reporting (see below).

**Config services:**
- `config/services/blast_service.py` — runs `blastp` subprocess, parses hits, enriches from Neo4j.
- `config/services/gds_service.py` — GDS projections (Louvain, PageRank, link prediction). Each projection is named uniquely and dropped in a `finally` block.
- `config/services/kegg_service.py` — KEGG REST client with a two-level cache (24h TTL, rate-limited ~3 req/s): L1 in-memory per process + L2 persistent in MongoDB `kegg_cache` (write-through, shared across workers, survives restarts; degrades to L1-only if Mongo is down). Pre-warm L2 with `scripts/warm_kegg_cache.py`.
- `config/services/string_service.py` — STRING API client with in-memory cache (6h TTL, rate-limited 1 req/s). Uses the `enrichment` endpoint (not `functional_annotation`) for real FDR values.
- `config/services/sandbox_service/` — **package** (not a single module): `_chemistry.py` (RDKit fingerprints Morgan/ECFP4, physchem properties), `_nodes.py` (Neo4j `:SandboxDrug` lifecycle), `_similarity.py` (Tanimoto structural + Jaccard behavioural, multi-fingerprint consensus). Re-exported from `sandbox_service/__init__.py`.
- `config/services/ctd_service.py` — queries the `ctd_gene_interactions` MongoDB collection (curated chemical–gene interactions) to enrich the sandbox pathways/network analysis.
- `config/services/propagation_service.py` — chain-effect propagation seeded from a drug's target genes. `propagate()` = diffusion mode (Personalized PageRank via GDS over `:STRING_ASSOC`, magnitude). `propagate_signed()` = directed mode (K-step signed diffusion over `:REGULATES`, predicts activation ↑ / inhibition ↓ per downstream gene assuming the drug inhibits its targets). `:REGULATES` may come from KEGG and/or OmniPath/SIGNOR.
- `config/services/chembl_service.py` + `config/services/pubchem_service.py` — experimental bioactivity clients (ChEMBL + PubChem BioAssay, no key). Back the bioactivity endpoint (Tier 1.1).
- `config/services/proximity_service.py` — network-medicine proximity (`d_c` distance between two drugs' target modules over the local `:STRING_ASSOC` interactome). Raises `ProximityUnavailable` if the STRING network isn't loaded (Tier 1.3).
- `config/services/opentargets_service.py` — Open Targets GraphQL client; `diseases_for_genes()` returns target→disease evidence for the repurposing hypothesis endpoint (Tier 2.1).
- `config/services/lincs_service.py` — LINCS L1000 (L1000CDS2 API) transcriptomic signature reversion; `signature_reversion()` ranks drugs that reverse/mimic an up/down gene signature (Tier 3.1).
- `config/services/chemberta_service.py` + `config/services/chemberta_index.py` — ChemBERTa embedding (torch+transformers) and Neo4j native vector index (`drug_chemberta`) helpers for learned molecular similarity (Tier 3.2). Degrade with 503 if the model/index is absent.
- `config/services/gprofiler_service.py` — g:Profiler GO enrichment client (`run_enrichment`), used by the DEG and repurposing tools.
- **Tier 4 (ML propio)** — modelos entrenados por nosotros + diseño generativo, todos con degradación 503:
  - `config/services/chemical_space_service.py` (4.1) — UMAP (2D) + HDBSCAN sobre los embeddings ChemBERTa; `build()` (offline) persiste el modelo `joblib` + la nube en la colección Mongo `chemical_space`; `load_points()`/`locate(smiles)` para los endpoints. Deps: `umap-learn`+`hdbscan`+`joblib` (`SPACE_OK`).
  - `config/services/dti_gnn_service.py` (4.2) — GNN de interacción fármaco-diana: embeddings de grafo GraphSAGE (fallback FastRP) vía GDS + cabezal Link Prediction (regresión logística sklearn, muestreo negativo, AUCPR/AP en test). `train()` escribe top-K `(:Drug)-[:PREDICTED_TARGET {score}]->(:Target)` y persiste métricas en Mongo `model_metrics`; `predict_for_drug()` lee esas aristas. `DTIUnavailable`→503.
  - `config/services/disease_gnn_service.py` (4.7, **BiomedGPS**) — extiende la GNN de 4.2 al par **fármaco→enfermedad** (repurposing): embeddings FastRP del subgrafo `Drug↔Target↔Disease` + cabezal LP. Reusa helpers de `dti_gnn_service`. `train()` escribe top-K `(:Drug)-[:PREDICTED_DISEASE {score}]->(:Disease)` + métricas; `predict_for_drug()` lee esas aristas. Requiere la capa de enfermedad (`load_disease_associations.py`). `DiseaseGNNUnavailable`→503.
  - `config/services/admet_service.py` (4.3) — ADMET/toxicidad supervisada: `featurize()` (descriptores RDKit + Morgan) compartida con el entrenamiento; `predict(smiles)` carga modelos `joblib` desde `backend/models/admet/` + métricas de `metrics.json`. Deps: `scikit-learn`+`joblib` (`ADMET_OK`).
  - `config/services/chemprop_service.py` (4.6) — GNN **Chemprop** (D-MPNN, Heid *JCIM* 2024; del repo `Antibiotics_Chemprop`): predictor multi-tarea de las 12 toxicidades de Tox21. GNN que APRENDE la representación (vs. features RDKit fijos del ADMET 4.3); también sirve como score model de SyntheMol. `predict(smiles)` invoca el CLI `chemprop predict` por subprocess sobre el modelo de `backend/models/chemprop/tox21/`. Deps `chemprop`+torch (`CHEMPROP_OK`/`model_ready()`). 503 sin paquete/modelo.
  - `config/services/denovo_service.py` (4.4) — diseño de novo: motor **CReM** por defecto (grow/mutate/link; deps `crem` + base de fragmentos en env `CREM_DB_PATH`) con scoring QED/SA/Lipinski/similitud al seed; delega en `denovo_synthemol.py` (`engine='synthemol'`) o `denovo_reinvent.py` (`engine='reinvent'`).
  - `config/services/denovo_synthemol.py` (4.4c, opcional) — motor **SyntheMol** (Swanson, *Nat. Mach. Intell.* 2024, Stanford): búsqueda combinatoria MCTS/RL sobre bloques comprables + reacciones reales guiada por un predictor de bioactividad → **síntesis garantizada por construcción**. No parte del seed (lo usa solo para similitud). Invoca el CLI `synthemol` por subprocess. Deps `synthemol` + env `SYNTHEMOL_BUILDING_BLOCKS` (biblioteca de bloques Enamine/WuXi) + `SYNTHEMOL_SCORE_MODEL`/`SYNTHEMOL_SCORE_TYPE` (predictor entrenado) (`SYNTHEMOL_OK`/`space_ready()`). Setup con `scripts/build_synthemol_space.py`. 503 si falta algo.
  - `config/services/denovo_reinvent.py` (4.4b, opcional) — motor generativo **REINVENT4** (prior RNN ChEMBL); deps `reinvent` + env `REINVENT_PRIOR_PATH` (`REINVENT_OK`). 503 si no está.
- **Tier 5 (estructural)** — inicio: modelado de pharmacóforos (ver `docs/TIER5_PLAN.md`, `docs/PHARMACO_SUITE_INTEGRATION.md`):
  - `config/services/pharmacophore_service.py` (5.1) — pharmacóforo **ligand-based** con RDKit: `build([smiles])` de 1 molécula → rasgos 3D (Donor/Acceptor/Aromatic/Hydrophobe/ionizables, familias de `BaseFeatures.fdef`) + distancias par a par; de ≥2 activos → perfil de **consenso** (familias en ≥50%). `pharmacophore_for_drug(id)` desde el catálogo. Implementación PROPIA (solo RDKit, open); enfoque inspirado en pharmaco-suite de E. Cubillos (ver NOTICE). 503 sin RDKit.
- `config/services/uniprot_service.py` + `config/services/swiss_service.py` — UniProt canonical protein data and SwissBioPics subcellular-localization images for the targets browser.
- `config/services/gemini_service.py` — Google Gemini REST client (`generateContent`, no SDK, uses `requests`). Model whitelist (`gemini-2.5-flash` default, `gemini-2.5-pro`), rate-limit + retry with backoff on transient 429/500/503. Reads `GEMINI_API_KEY` / `GEMINI_MODEL` from settings; raises `GeminiUnavailable` (→ 503) when the key is not set.
- `config/services/report_service.py` — AI reporting orchestration. Per-analysis payload trimming (`_TRIMMERS` for sandbox/repurposing/toxicity/deg/ddi/bioactivity + Tier 4: denovo/admet/dti_gnn) + strict anti-hallucination prompts (system instruction: use only provided JSON, no invented genes/pathways/numbers, mark uncertainty, in-silico disclaimer) × two styles (`scientific` | `executive`). Persists each report per user in the MongoDB `reports` collection; `build_report`, `list_reports`, `get_report`, `delete_report`.

**App-agnostic reporting views:** `drugs/views/reports.py` — `report_generate_view` / `report_list_view` / `report_detail_view`, routed under `/api/reports/` (`drugs/urls_reports.py`). Auth required (`IsAuthenticated`) so reports attribute to a user.

**Standalone scripts** (run from `backend/`, ubicados en `backend/scripts/`):
- `scripts/build_blast_db.py` — builds BLAST index from a targets NDJSON file.
- `scripts/populate_fingerprints.py` — computes Morgan fingerprints for all `:Drug` nodes in Neo4j (prerequisite for structural similarity in sandbox). Can also be run as a Django management command.
- `scripts/load_ctd_interactions.py` — downloads `CTD_chem_gene_ixns.csv.gz` from ctdbase.org, filters to human + Neo4j genes, aggregates per gene, and loads the `ctd_gene_interactions` collection (prerequisite for the CTD section in the sandbox).
- `scripts/load_string_network.py` — downloads STRING human bulk (`9606.protein.links/info`), filters to score ≥ 700, maps ENSP→gene symbol, and loads `(:Gene)-[:STRING_ASSOC {score}]->(:Gene)` into Neo4j (prerequisite for the diffusion cascade mode).
- `scripts/load_kegg_regulatory.py` — fetches all human KEGG pathway KGMLs, extracts signed directed relations (activation/inhibition), and loads `(:Gene)-[:REGULATES {sign}]->(:Gene)` into Neo4j (prerequisite for the directed/signed cascade mode).
- `scripts/load_omnipath_regulatory.py` — loads richer signed directed relations from OmniPath/SIGNOR as `(:Gene)-[:REGULATES {source:'OMNIPATH'}]->(:Gene)` (coexists with KEGG; optional, requires `pip install omnipath`).
- `scripts/populate_chemberta_embeddings.py` — computes ChemBERTa embeddings for every `:Drug` (stored on `d.chemberta`) and builds the Neo4j native vector index `drug_chemberta` (prerequisite for embedding similarity, Tier 3.2; needs `torch`+`transformers`).
- `scripts/populate_targets.py` — populates/normalises `:Target` nodes and their gene/DrugBank links in Neo4j.
- `scripts/populate_uniprot.py` — enriches `:Target` nodes with UniProt canonical data for the targets browser.
- `scripts/seed_admin.py` — creates the seed admin user (`admin@druggraph.dev` / `admin1234`) in the MongoDB `users` collection.
- `scripts/ensure_indexes.py` — idempotent MongoDB index manager (run after seeding data). Adds `drugs` indexes (`type`, `groups`, `drugbank-id.value`, text index on `name`), keeps `users.email` unique, and drops unused `ctd_gene_interactions` indexes. `--dry-run` previews changes.
- `scripts/prune_neo4j_indexes.py` — idempotent Neo4j index cleanup: drops indexes/constraints whose label has 0 nodes (currently the orphan `:Polypeptide` ones — that node type was never materialised; the gene symbol lives on `:Target.gene_name`). Conservative: only drops if the label is truly empty. `--dry-run` previews.
- **Tier 4 (ML propio) scripts:**
  - `scripts/build_chemical_space.py` (4.1) — ajusta UMAP+HDBSCAN sobre `:Drug.chemberta`, guarda `backend/models/chemical_space/umap.joblib` + la colección Mongo `chemical_space`.
  - `scripts/train_dti_gnn.py` (4.2) — entrena la GNN DTI (GraphSAGE/FastRP + LP), reporta AUCPR/AP, escribe `:PREDICTED_TARGET` y `model_metrics`. Requiere GDS.
  - `scripts/train_admet_models.py` (4.3) — descarga MoleculeNet (Tox21/BBBP/ESOL), entrena RandomForest por endpoint, guarda `backend/models/admet/*.joblib` + `metrics.json`.
  - `scripts/train_chemprop.py` (4.6) — entrena el GNN **Chemprop** D-MPNN multi-tarea sobre los 12 ensayos de Tox21 (filtra SMILES inválidos, split por scaffold), guarda el checkpoint en `backend/models/chemprop/tox21/` + `metrics.json`. Requiere `pip install chemprop`.
  - `scripts/load_disease_associations.py` (4.7) — proyecta `open_targets_diseases` (Mongo) a la capa de enfermedad de Neo4j: `(:Disease)` + `(:Drug)-[:ASSOCIATED_WITH {score,gene}]->(:Disease)` (~2280 enfermedades, 24790 aristas). Prerrequisito de la Disease-GNN.
  - `scripts/train_disease_gnn.py` (4.7) — entrena la GNN de repurposing fármaco→enfermedad (FastRP + LP), reporta AUCPR/AP, escribe `:PREDICTED_DISEASE` y `model_metrics`. Requiere GDS + la capa de enfermedad.
  - `scripts/eval_*.py` — **evaluación held-out** de los modelos Tier 4 (`eval_graph_models` Disease/DTI-GNN, `eval_admet`, `eval_chemprop`, `eval_disease_realworld`). Escriben datasets de test (aciertos/errores) + métricas (ROC/PR/correlación/confusión) + curvas a `dataset_testing/`; ver `dataset_testing/REPORT.md`. Plan del Tier 5 (docking estructural NDM-1) en `docs/TIER5_PLAN.md`.
  - `scripts/build_crem_db.py` (4.4) — exporta los SMILES del catálogo y documenta cómo construir/descargar la base de fragmentos de CReM (`CREM_DB_PATH`).
  - `scripts/build_synthemol_space.py` (4.4c) — exporta un CSV de entrenamiento (`smiles,activity`) desde el catálogo y documenta cómo descargar la biblioteca de bloques (Enamine/WuXi) y entrenar el predictor Chemprop para el motor de novo **SyntheMol** (`SYNTHEMOL_BUILDING_BLOCKS`, `SYNTHEMOL_SCORE_MODEL`).
- `scripts/warm_kegg_cache.py` — pre-warms the persistent KEGG cache (MongoDB `kegg_cache`) for the N drugs with the most UniProt targets (or specific `--drug DBID`s). Cold `pathways/` requests take tens of seconds due to KEGG rate-limiting; warming makes later requests near-instant and survives restarts. Run once offline after loading the graph.

**URL layout** (`drugs/urls.py` under `/api/drugs/`, `drugs/urls_tools.py` under `/api/tools/`, `drugs/urls_reports.py` under `/api/reports/`, `users/urls.py` under `/api/auth/`; **everything is under `/api/`**):

_Auth & account (`users/views.py`):_
| Path | Notes |
|------|-------|
| `POST /api/auth/register/` · `POST /api/auth/login/` · `POST /api/auth/logout/` | public |
| `GET /api/auth/me/` · `PUT /api/auth/me/update/` · `POST /api/auth/me/password/` | own profile |
| `GET/POST/DELETE /api/auth/users/…` · `POST /api/auth/users/<id>/reset-password/` | admin-only CRUD |

_Drugs, targets, stats (`drugs/views/`):_
| Path | Source |
|------|--------|
| `GET  /api/drugs/` · `GET /api/drugs/filters/` | `drugs/views/drugs.py` |
| `GET  /api/drugs/<drug_id>/` | `drugs/views/drugs.py` |
| `GET  /api/drugs/<drug_id>/graph/` | `drugs/views/graph.py` (IS under `/api/`) |
| `GET  /api/drugs/<drug_id>/pathways/` | `drugs/views/pathways.py` |
| `GET  /api/drugs/<drug_id>/bioactivity/` | `drugs/views/bioactivity.py` |
| `GET  /api/drugs/stats/` · `GET /api/drugs/stats/public/` | `drugs/views/stats.py` |
| `GET  /api/drugs/targets/` · `.../targets/<id>/` · `.../targets/<id>/graph|uniprot|pathways/` · `.../targets/compare|by-gene|kegg-gene/` | `drugs/views/targets.py` |
| `GET  /api/drugs/ddi/` · `GET /api/drugs/ddi/risk/` | `drugs/views/ddi.py`, `drugs/views/ddi_risk.py` |

_BLAST & GDS:_
| Path | Source |
|------|--------|
| `POST /api/drugs/blast/search/` | `drugs/views/blast.py` |
| `GET  /api/drugs/gds/centrality|communities/` · `.../gds/predict/<drug_id>/` · `.../gds/predict-global/` | `drugs/views/gds.py` |

_Sandbox (`drugs/views/sandbox.py`, `similarity.py`, `embedding_similarity.py`):_
| Path | Notes |
|------|-------|
| `POST /api/drugs/sandbox/analyze/` · `GET /api/drugs/sandbox/targets/` | analyze + target autocomplete |
| `GET  /api/drugs/sandbox/pathways/` · `.../propagation/` · `.../swiss-targets/` · `.../bioactivity/` | lazy-loaded sections |
| `GET  /api/drugs/sandbox/similarity-detail/` · `POST /api/drugs/sandbox/embedding-similarity/` | multi-fingerprint + ChemBERTa |
| `DELETE /api/drugs/sandbox/<sandbox_id>/` | manual cleanup |

_Tools (`drugs/urls_tools.py` → `drugs/views/*` + `drugs/views/tools/*`):_
| Path | Source |
|------|--------|
| `POST /api/tools/deg-analysis/` | `drugs/views/tools/deg.py` |
| `GET  /api/tools/repurposing/<drug_id>/` | `drugs/views/tools/repurposing.py` |
| `GET  /api/tools/toxicity/<drug_id>/` | `drugs/views/tools/toxicity.py` |
| `GET  /api/tools/proximity/` | `drugs/views/tools/proximity.py` |
| `GET  /api/tools/disease-evidence/<drug_id>/` | `drugs/views/tools/disease_evidence.py` |
| `POST /api/tools/signature-reversion/` | `drugs/views/tools/signature_reversion.py` |
| `GET  /api/tools/chemical-space/` · `POST /api/tools/chemical-space/locate/` | `drugs/views/tools/chemical_space.py` (Tier 4.1) |
| `POST /api/tools/denovo/` | `drugs/views/tools/denovo.py` (Tier 4.4) |
| `POST /api/tools/admet/` | `drugs/views/tools/admet.py` (Tier 4.3) |
| `POST /api/tools/chemprop-tox/` | `drugs/views/tools/chemprop_tox.py` (Tier 4.6) |
| `GET  /api/tools/disease-gnn/<drug_id>/` | `drugs/views/tools/disease_gnn.py` (Tier 4.7, BiomedGPS) |
| `POST /api/tools/pharmacophore/` | `drugs/views/tools/pharmacophore.py` (Tier 5.1) |
| `GET  /api/tools/dti-gnn/<drug_id>/` | `drugs/views/tools/dti_gnn.py` (Tier 4.2) |

_AI reporting (`drugs/views/reports.py`, auth required):_
| Path | Notes |
|------|-------|
| `POST /api/reports/generate/` | AI reporting, any analysis kind |
| `GET  /api/reports/` | user history |
| `GET/DELETE /api/reports/<report_id>/` | detail / delete |

_Docs:_ `GET /api/schema/` (OpenAPI) and `GET /api/docs/` (Swagger UI) via `drf-spectacular`.

### Frontend (`frontend/src/`)

- **API layer**: `api/client.ts` — Axios instance pointing to `http://localhost:8000/api`. Attaches JWT from `localStorage` (`dg_token`) via request interceptor; redirects to `/login` on 401.
- **Auth state**: `context/AuthContext.tsx` — provides `user`, `login`, `register`, `logout`. Wraps entire app; children only render after the initial `me()` check resolves.
- **Routing**: `App.tsx` — public routes (`/`, `/login`, `/register`) and protected routes (`/dashboard`, `/drugs`, `/drugs/:id`, `/targets`, `/targets/compare`, `/targets/:id`, `/sandbox`, `/blast`, `/network`, `/tools` with nested `deg|repurposing|toxicity|ddi|chemical-space|denovo|admet|dti-gnn`, `/help`, `/profile`, `/admin`) using `<ProtectedRoute>`.
- **Drug detail sections**: `features/drugs/drug-sections/` — modular components (Chemistry, Clinical, Genomics, Market, Targets, GraphInteractions, Pathways, Bioactivity) composed inside `features/drugs/DrugDetailPage`.
- **CytoscapeGraph**: `components/CytoscapeGraph.tsx` — reusable Cytoscape.js wrapper with DrugGraph dark theme. Used by GraphInteractionsSection, PathwaysSection, and NetworkAnalysisPage.
- **API modules** (`api/`): `auth.ts`, `users.ts`, `drugs.ts`, `blast.ts`, `gds.ts`, `pathways.ts`, `sandbox.ts`, `targets.ts`, `bioactivity.ts`, `tools.ts`, `stats.ts`, `reports.ts` — one module per feature.
- **Feature folders** (`features/`): `drugs/`, `targets/`, `sandbox/`, `tools/` (DegAnalysisTool, RepurposingTool, ToxicityTool, DdiCheckerPage under ToolsPage), `reports/`.
- **AI reporting**: `features/reports/ReportPanel.tsx` — reusable panel (style + model selector, generate, modal, copy/download MD) dropped into SandboxPage and the tools (Repurposing, Toxicity, DEG, DDI). `features/reports/MarkdownView.tsx` renders the report with a minimal, XSS-safe Markdown renderer (no `dangerouslySetInnerHTML`, no extra deps).

### Environment Variables (backend)

Defaults work for local development with Docker Compose:

| Variable | Default | Notes |
|----------|---------|-------|
| `MONGODB_URI` | `mongodb://localhost:27017/` | |
| `MONGODB_DB` | `druggraph` | Default del código; el `.env` de este proyecto lo sobreescribe a `druggraph_open` (la BD real cargada) |
| `NEO4J_URI` | `bolt://localhost:7687` | |
| `NEO4J_USER` | `neo4j` | |
| `NEO4J_PASSWORD` | `druggraph123` | |
| `JWT_SECRET` | `druggraph-jwt-secret-change-in-production` | |
| `BLAST_DB_PATH` | `""` | Path without extension to blastp index |
| `BLAST_MAP_PATH` | `""` | Path to `.map.json` generated by `scripts/build_blast_db.py` |
| `BLAST_THREADS` | `2` | Threads for blastp subprocess |
| `GEMINI_API_KEY` | `""` | Google Gemini key for AI reporting (empty → `/api/reports/` returns 503) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Default model; per-request override limited to the whitelist |

Frontend API base URL: set `REACT_APP_API_URL` env var (defaults to `http://localhost:8000/api`).

### Feature dependencies

| Feature | Extra requirement |
|---------|------------------|
| Sandbox (structural similarity) | `rdkit` + `scripts/populate_fingerprints.py` run once |
| BLAST search | `ncbi-blast+` installed, index built with `scripts/build_blast_db.py` |
| GDS (communities, global predict) | Neo4j GDS plugin installed (endpoints return 503 without it) |
| Pathways (STRING + KEGG) | Internet access; no API key needed |
| Sandbox CTD interactions | `scripts/load_ctd_interactions.py` run once (section shows "not loaded" otherwise) |
| Sandbox cascade — diffusion mode | Neo4j GDS plugin + `scripts/load_string_network.py` run once (local STRING PPI) |
| Sandbox cascade — directed/signed mode | `scripts/load_kegg_regulatory.py` run once (loads `:REGULATES` from KEGG KGML) |
| Sandbox cascade — OmniPath/SIGNOR (optional, richer) | `pip install omnipath` + `scripts/load_omnipath_regulatory.py` (adds `:REGULATES {source:'OMNIPATH'}`, coexists with KEGG; `propagate_signed` uses all sources) |
| AI reporting (`/api/reports/`) | `GEMINI_API_KEY` set; `scripts/ensure_indexes.py` for the `reports` index. Reads a valid Gemini key; nothing else external |
| Bioactivity, disease evidence, proximity | Internet access (ChEMBL/PubChem/Open Targets APIs, no key); proximity needs the local STRING network loaded |
| Signature reversion (repurposing from DEG) | Internet access (LINCS L1000CDS2 API, no key) |
| Embedding similarity (ChemBERTa, Tier 3.2) | `pip install torch transformers` + `scripts/populate_chemberta_embeddings.py` (populates `d.chemberta` + Neo4j native vector index `drug_chemberta`). Endpoint returns 503 without the model/index |
| Chemical space map (Tier 4.1) | `pip install umap-learn hdbscan joblib` + ChemBERTa embeddings poblados + `scripts/build_chemical_space.py` run once. `locate` also needs torch+transformers. 503 sin la nube |
| DTI GNN prediction (Tier 4.2) | Neo4j GDS plugin + `pip install scikit-learn` + `scripts/train_dti_gnn.py` run once (escribe `:PREDICTED_TARGET`). 503 sin GDS/modelo |
| ADMET supervisado (Tier 4.3) | `pip install scikit-learn pandas joblib` + `scripts/train_admet_models.py` run once (descarga MoleculeNet). 503 sin modelos |
| GNN Chemprop toxicidad (Tier 4.6) | `pip install chemprop` (compatible torch 2.x) + `scripts/train_chemprop.py` run once (Tox21 multi-tarea). 503 sin paquete/modelo |
| Disease-GNN repurposing (Tier 4.7, BiomedGPS) | Neo4j GDS + `scikit-learn` + `scripts/load_disease_associations.py` (capa de enfermedad) + `scripts/train_disease_gnn.py` run once (escribe `:PREDICTED_DISEASE`). 503 sin GDS/capa/modelo |
| De novo — CReM (Tier 4.4) | `pip install crem` + base de fragmentos (`scripts/build_crem_db.py` / descarga) + env `CREM_DB_PATH`. 503 sin la base |
| De novo — SyntheMol (Tier 4.4c, opcional) | `pip install synthemol` + biblioteca de bloques (env `SYNTHEMOL_BUILDING_BLOCKS`) + predictor entrenado (env `SYNTHEMOL_SCORE_MODEL`). Setup con `scripts/build_synthemol_space.py`. 503 sin bloques/predictor |
| De novo — REINVENT4 (Tier 4.4b, opcional) | `pip install -r requirements-ml.txt` + modelo prior + env `REINVENT_PRIOR_PATH`. 503 sin el prior |
