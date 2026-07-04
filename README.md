# DrugGraph Open

Plataforma de información farmacológica con grafo de interacciones moleculares, sobre
**datos 100% open-source y redistribuibles**. Construida sobre una persistencia poliglota:
**PostgreSQL** como capa de staging (dumps DrugCentral/ChEMBL), **MongoDB** para los
documentos de fármacos, **Neo4j** para el grafo de interacciones, y Django como API
unificadora.

Es la versión de datos abiertos de DrugGraph: reemplaza el dataset propietario de DrugBank
por **DrugCentral, ChEMBL, Open Targets, PubChem, UniProt y CTD** (licencias CC BY / CC BY-SA
/ dominio público), de modo que el proyecto y sus datos pueden publicarse libremente.
Las fuentes y el mapeo de campos están en [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md);
la tubería de ingesta en [`backend/scripts/ingest/`](backend/scripts/ingest/README.md).

Desarrollada como proyecto de investigación académica (Base de Datos Avanzada, 2026).

---

## Características principales

### Catálogo y búsqueda
- Listado paginado de fármacos con búsqueda de texto completo (índice MongoDB)
- Detalle con 7 secciones: Química, Clínica, Genómica, Mercado, Dianas, Grafo, Pathways
- Filtros por tipo de fármaco y grupos terapéuticos

### Grafo de interacciones (Neo4j + Cytoscape.js)
- Visualización interactiva: Fármaco → Diana, Fármaco → Categoría, Fármaco ↔ Fármaco
- Nodos coloreados por tipo, zoom, pan, click para detalle

### Sandbox molecular
- Análisis de compuestos nuevos ingresados como SMILES
- **Similitud estructural**: Tanimoto con fingerprints Morgan/ECFP4 (RDKit) + consenso multi-fingerprint
- **Similitud por embedding**: ChemBERTa (índice vectorial nativo de Neo4j) — similitud aprendida (opcional)
- **Similitud de comportamiento**: Jaccard sobre proteínas diana compartidas (UniProt canónico)
- **Análisis de pathways**: STRING PPI + KEGG enriquecimiento funcional
- **CTD**: interacciones curadas gen-químico (CTD Database)
- **Bioactividad experimental**: ChEMBL + PubChem BioAssay
- **Efecto en cascada**: propagación difusión (Personalized PageRank/GDS) y dirigida-firmada (K-step sobre KEGG y/o OmniPath/SIGNOR REGULATES)

### BLAST+
- Búsqueda de secuencias proteicas contra índice local de dianas
- Hits enriquecidos con datos de Neo4j (fármacos vinculados, pathways)

### Análisis de red (GDS)
- PageRank sobre el grafo de interacciones
- Detección de comunidades (algoritmo Louvain)
- Predicción de enlaces (link prediction)
- Visualización del grafo global con Cytoscape.js

### Pathways
- Dianas del fármaco → PPI vecinos (STRING API) → enriquecimiento GO/KEGG/Reactome con FDR

### Herramientas analíticas
- **Verificador de DDI**: interacciones documentadas (DrugBank) + riesgo PK/PD predicho (CYPs, dianas compartidas, proximidad) sin ML
- **Análisis DEG**: clasificación up/down/significativo, cruce con dianas del fármaco y enriquecimiento GO (g:Profiler)
- **Reposicionamiento**: candidatos por similitud de red de dianas (Jaccard) + perfil GO
- **Toxicidad**: alertas por anti-targets (hERG, CYPs…), off-targets topológicos y score de riesgo agregado
- **Proximidad de red**: distancia `d_c` entre módulos de dianas de dos fármacos en el interactoma STRING (network medicine)
- **Evidencia diana→enfermedad**: enfermedades asociadas al módulo de dianas vía Open Targets
- **Reversión de firma transcriptómica**: fármacos que revierten/imitan una firma de genes up/down (LINCS L1000)

### Reportería con IA (Gemini)
- Genera informes en lenguaje natural de cualquier análisis (sandbox, reposicionamiento, toxicidad, DEG, DDI)
- Dos estilos (científico / ejecutivo), prompts anti-alucinación (solo usa el JSON del análisis), historial por usuario
- Requiere `GEMINI_API_KEY`; sin ella los endpoints `/api/reports/` devuelven 503

### Navegador de dianas
- Tabla paginada de proteínas diana con panel de detalle
- Comparador de dos dianas: PathSim, vecinos comunes, pathways compartidos

### Administración
- Panel admin para gestión de usuarios (solo admin)
- Registro, login y perfil con cambio de contraseña
- Auth JWT + bcrypt, expiración 24h con banner de advertencia

---

## Stack técnico

```
Frontend          Backend              Bases de datos
─────────         ──────────           ──────────────
React 18          Django 4.2           PostgreSQL 16  (staging de ingesta: DrugCentral/ChEMBL)
TypeScript        Django REST          MongoDB 7      (documentos de fármacos)
Cytoscape.js      Framework            Neo4j 5        (grafo de interacciones)
Axios             PyJWT + bcrypt       SQLite         (solo sesiones Django)
RDKit (WASM)      MongoJWTAuthentication
```

> Puertos del stack Docker (aislados de un DrugGraph original en la misma máquina):
> MongoDB **27018**, Neo4j **7475/7688**, Postgres **5433**.

APIs externas (sin API key, salvo Gemini):
- **STRING** — PPI neighbors + enrichment GO/KEGG/Reactome
- **KEGG REST** — pathways por gen diana
- **BLAST+** — búsqueda de homología local
- **ChEMBL / PubChem** — bioactividad experimental
- **Open Targets** — evidencia diana→enfermedad
- **g:Profiler** — enriquecimiento GO (DEG / reposicionamiento)
- **LINCS L1000CDS2** — reversión de firma transcriptómica
- **UniProt / SwissBioPics** — perfil de proteínas diana
- **Google Gemini** — reportería IA (requiere `GEMINI_API_KEY`)

Datasets descargados una vez:
- **CTD** — interacciones curadas químico-gen (ctdbase.org)
- **STRING bulk** — red PPI humana para propagación (score ≥ 700)
- **KEGG KGML** — relaciones dirigidas firmadas (+1 activación, −1 inhibición)

---

## Arquitectura

```
┌──────────────────────────────────────────────────────┐
│                    React / TypeScript                │
│  drugs  │  sandbox  │  blast  │  network  │  tools  │
└─────────────────────┬────────────────────────────────┘
                      │ REST / JSON
┌─────────────────────▼────────────────────────────────┐
│               Django REST Framework                  │
│   users/   │   drugs/views/   │   config/services/   │
│   JWT auth │   graph blast    │   mongo neo4j gds    │
│            │   gds sandbox    │   string kegg blast  │
└──────┬─────────────────┬──────────────────────────────┘
       │                 │
┌──────▼──────┐   ┌──────▼──────────────────────────┐
│  MongoDB    │   │  Neo4j                           │
│  druggraph  │   │  (:Drug)-[:HAS_TARGET]->(:Target)│
│  ├ drugs    │   │  (:Drug)-[:IN_CATEGORY]->(:Cat.) │
│  ├ users    │   │  (:Drug)-[:INTERACTS_WITH]->(:D) │
│  └ ctd_*   │   │  (:Gene)-[:STRING_ASSOC]->(:Gene) │
└─────────────┘   │  (:Gene)-[:REGULATES]->(:Gene)   │
                  └──────────────────────────────────┘
```

**No hay ORM SQL** para el dominio. Los servicios singleton en `config/services/` consumen directamente MongoDB y Neo4j. `settings.DATABASES['default']` es SQLite temporal solo para que el test-runner de Django funcione.

---

## Configuración

### Requisitos
- Docker y Docker Compose
- Python 3.11+
- Node.js 18+
- `ncbi-blast+` (para BLAST search)

### 1. Bases de datos

```bash
docker compose up -d   # MongoDB :27018 · Neo4j :7475/:7688 · Postgres :5433
```

### 2. Datos open-source (ingesta)

DrugGraph Open **no usa DrugBank**. El catálogo se construye desde fuentes abiertas y
redistribuibles con la tubería de `backend/scripts/ingest/`. Resumen:

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt -r requirements-ingest.txt

# 0. Descarga el dump de DrugCentral (https://drugcentral.org/download) y restáuralo
bash scripts/ingest/restore_dumps.sh /ruta/drugcentral.dump.sql.gz

# 1. DrugCentral → Mongo `drugs`   (usa --limit 200 para una prueba rápida)
python -m scripts.ingest.step01_drugcentral_to_mongo
# 2. (opcional) Enriquecer con ChEMBL
python -m scripts.ingest.step02_chembl_enrich --source api
# 3. Mongo → grafo Neo4j
python -m scripts.ingest.step03_build_graph
# 4. DDI open (TWOSIDES, CC0)
python -m scripts.ingest.step04_ddi_open --csv data/ddi_twosides.csv

# Enriquecedores heredados (ya eran open):
python scripts/populate_targets.py --uniprot
python scripts/populate_fingerprints.py
python scripts/load_ctd_interactions.py
python scripts/ensure_indexes.py
```

> Detalle completo (orden, prerrequisitos, fuentes) en
> [`backend/scripts/ingest/README.md`](backend/scripts/ingest/README.md) y
> [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md). Todos los datos ingeridos son
> redistribuibles: el repositorio y su contenido pueden publicarse sin licencia externa.

### 3. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py runserver
```

Crear usuario admin (primera vez):

```bash
python scripts/seed_admin.py   # admin@druggraph.dev / admin1234
```

### 4. Frontend

```bash
cd frontend
npm install
npm start
```

Abre http://localhost:3000

### 5. Datasets opcionales

| Feature | Requisito |
|---------|-----------|
| Sandbox CTD | `python scripts/load_ctd_interactions.py` |
| Sandbox cascada (difusión) | GDS plugin Neo4j + `python scripts/load_string_network.py` |
| Sandbox cascada (dirigida/firmada) | `python scripts/load_kegg_regulatory.py` |
| Sandbox cascada (OmniPath/SIGNOR, opcional) | `pip install omnipath` + `python scripts/load_omnipath_regulatory.py` |
| Sandbox similitud estructural | `python scripts/populate_fingerprints.py` |
| Sandbox similitud por embedding (ChemBERTa) | `pip install torch transformers` + `python scripts/populate_chemberta_embeddings.py` |
| Bioactividad / evidencia enfermedad / proximidad | Acceso a internet (ChEMBL/PubChem/Open Targets); proximidad además requiere la red STRING cargada |
| Reversión de firma (repurposing DEG) | Acceso a internet (LINCS L1000CDS2) |
| BLAST search | `ncbi-blast+` instalado + `python scripts/build_blast_db.py` |
| GDS comunidades / predict | Neo4j GDS plugin (sin él devuelve 503) |
| Reportería IA (`/api/reports/`) | `GEMINI_API_KEY` definida (sin ella devuelve 503) |

---

## Tests

```bash
# Backend (32 tests, SimpleTestCase — sin SQL)
cd backend && python manage.py test

# Frontend
cd frontend && npm test
```

---

## Variables de entorno

Copia `.env.example` a `.env`. Los defaults funcionan con Docker Compose local.

| Variable | Default |
|----------|---------|
| `MONGODB_URI` | `mongodb://localhost:27017/` |
| `MONGODB_DB` | `druggraph` |
| `NEO4J_URI` | `bolt://localhost:7687` |
| `NEO4J_USER` | `neo4j` |
| `NEO4J_PASSWORD` | `druggraph123` |
| `JWT_SECRET` | `druggraph-jwt-secret-change-in-production` |
| `BLAST_DB_PATH` | `""` |
| `BLAST_MAP_PATH` | `""` |
| `BLAST_THREADS` | `2` |
| `GEMINI_API_KEY` | `""` (necesaria para la reportería IA) |
| `GEMINI_MODEL` | `gemini-2.5-flash` |

Frontend: `REACT_APP_API_URL` (default `http://localhost:8000/api`).

---

## Nota sobre los datos

Los documentos de fármacos provienen de **DrugBank**, que requiere registro para uso académico. El código de este repositorio es independiente de los datos y puede adaptarse a otras fuentes. Los datos **no se incluyen en el repositorio**.

Los datasets externos (STRING bulk, KEGG KGML, CTD) se descargan automáticamente por los scripts de carga desde sus fuentes públicas.

---

## Licencia

MIT — el código es libre. Los datos de DrugBank tienen su propia licencia (ver https://www.drugbank.ca/legal/terms_of_service).
