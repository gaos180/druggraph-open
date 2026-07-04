# 05 — Vista de Bloques

## 5.1 Nivel 1 — Sistema completo

```
┌─────────────────────────────────────────────────────────────────────┐
│                           DrugGraph                                  │
│                                                                      │
│  ┌───────────────────┐         ┌──────────────────────────────────┐  │
│  │   Frontend (React)│◄───────►│        Backend (Django)          │  │
│  └───────────────────┘  HTTP   └──────────────────────────────────┘  │
│                                         │         │                  │
│                                    ┌────▼───┐ ┌───▼────┐            │
│                                    │MongoDB │ │ Neo4j  │            │
│                                    └────────┘ └────────┘            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5.2 Nivel 2 — Backend

```
backend/
├── manage.py
├── config/
│   ├── settings.py          ← Config global. DATABASES['default']=sqlite (admin/sessions);
│   │                          DATABASES_NOSQL['mongodb'|'neo4j'] = conexiones del dominio
│   ├── urls.py              ← Montaje de prefijos: /api/auth/, /api/drugs/, /api/tools/
│   ├── wsgi.py · asgi.py
│   └── services/           ← Paquete de servicios singleton (acceso a datos + APIs)
│       ├── __init__.py     ← re-exporta get_db, get_driver, get_drug_graph
│       ├── mongo.py             ← Singleton pymongo  →  get_db()
│       ├── neo4j_service.py     ← Singleton neo4j    →  get_driver(), _session(), get_drug_graph()
│       ├── blast_service.py     ← Lanza blastp, parsea salida tabular
│       ├── gds_service.py       ← Proyecciones GDS (Louvain, PageRank, link pred.)
│       ├── kegg_service.py      ← Cliente KEGG REST (UniProt→gen→pathway)
│       ├── string_service.py    ← Cliente STRING API (PPI vecinos + enrichment con FDR real)
│       ├── ctd_service.py       ← Consulta interacciones químico-gen de CTD (MongoDB)
│       ├── propagation_service.py ← PageRank personalizado (STRING) + difusión firmada (KEGG)
│       ├── sandbox_service/    ← paquete: _chemistry (fingerprints), _nodes
│       │                         (:SandboxDrug), _similarity (Tanimoto+Jaccard/GDS)
│       ├── swiss_service.py     ← Cliente SwissTargetPrediction (API + parseo CSV)
│       ├── uniprot_service.py   ← Cliente UniProt (detalles de proteína)
│       └── gprofiler_service.py ← Enriquecimiento GO vía g:Profiler
│
├── scripts/                ← Scripts standalone (carga de datos / seed, fuera del runserver)
│   ├── seed_admin.py             ← crea el usuario admin inicial
│   ├── build_blast_db.py         ← índice BLAST de secuencias
│   ├── populate_fingerprints.py  ← fingerprints Morgan en :Drug
│   ├── populate_targets.py · populate_uniprot.py ← pueblan/enriquecen :Target
│   ├── load_ctd_interactions.py  ← descarga CTD y carga ctd_gene_interactions (Mongo)
│   ├── load_string_network.py    ← descarga STRING humano y carga (:Gene)-[:STRING_ASSOC] (Neo4j)
│   ├── load_kegg_regulatory.py   ← descarga KGML de KEGG y carga (:Gene)-[:REGULATES {sign}] (Neo4j)
│   └── ensure_indexes.py         ← gestor idempotente de índices MongoDB (drugs, users, ctd)
│
├── users/
│   ├── authentication.py    ← MongoJWTAuthentication + SimpleUser
│   ├── services.py          ← bcrypt hash, JWT gen/verify, CRUD db.users
│   ├── views.py             ← /api/auth/register, login, me
│   └── urls.py
│
└── drugs/
    ├── services.py          ← list_drugs(), drug_detail() con proyecciones Mongo
    ├── views/              ← Paquete de vistas, una por dominio funcional
    │   ├── __init__.py     ← re-exporta todas las vistas para urls.py / urls_tools.py
    │   ├── drugs.py            ← list_drugs_view, drug_filters_view, drug_detail
    │   ├── graph.py            ← drug_graph_view  → Neo4j 4-query pipeline
    │   ├── blast.py            ← blast_search_view → blast_service
    │   ├── gds.py              ← gds_centrality, gds_communities, gds_link_prediction
    │   ├── pathways.py         ← drug_pathways_view → neo4j + string + kegg
    │   ├── sandbox.py          ← sandbox_analyze, sandbox_targets, sandbox_cleanup,
    │   │                          sandbox_pathways_view, sandbox_propagation_view
    │   ├── targets.py          ← targets_list_view, target_detail_view, …
    │   ├── tools/             ← paquete: _common (helpers), deg, repurposing, toxicity
    │   │                         (deg_analysis_view, repurposing_view, toxicity_view)
    │   ├── ddi.py              ← ddi_check_view
    │   └── stats.py            ← stats_view
    ├── urls.py              ← Todas las rutas de /api/drugs/
    └── urls_tools.py        ← Rutas de /api/tools/ (DEG, reposicionamiento, toxicidad, DDI)
```

El módulo `drugs/views/tools.py` concentra las tres herramientas analíticas. Cada vista usa
servicios compartidos del paquete `config/services/`:

- `deg_analysis_view` — Neo4j (targets) + g:Profiler (GO)
- `repurposing_view` — Neo4j (Jaccard de targets) + g:Profiler (GO perfil)
- `toxicity_view` — Neo4j (anti-targets directos + Adamic-Adar off-targets + cluster Jaccard)

---

## 5.3 Nivel 2 — Frontend

```
frontend/src/
├── api/
│   ├── client.ts          ← Axios instance (baseURL, JWT interceptor, 401 redirect)
│   ├── drugs.ts           ← listDrugs(), getDrug(), getFilters()
│   ├── blast.ts           ← blastSearch()
│   ├── gds.ts             ← getCentrality(), getCommunities(), getPredictions()
│   ├── pathways.ts        ← pathwaysApi.forDrug()
│   ├── sandbox.ts         ← sandboxAnalyze(), sandboxTargets(), sandboxCleanup(),
│   │                          sandboxPathways()
│   ├── targets.ts         ← targetsApi.list(), targetsApi.detail()
│   ├── tools.ts           ← toolsApi.degAnalysis(), repurposing(), toxicity(), checkDdi()
│   └── users.ts           ← usersApi (gestión de cuenta)
│
├── context/
│   └── AuthContext.tsx    ← user, login, register, logout; envuelve toda la app
│
├── pages/
│   ├── LoginPage.tsx
│   ├── RegisterPage.tsx
│   ├── DashboardPage.tsx      ← Cards de acceso a funcionalidades
│   ├── DrugsListPage.tsx      ← Listado paginado con filtros
│   ├── DrugDetailPage.tsx     ← Detalle con pestañas (Chemistry, Clinical, etc.)
│   ├── BlastSearchPage.tsx    ← FASTA input + resultados con HitCard
│   ├── SandboxPage.tsx        ← SMILES input + comparación estructural + lazy-load pathways
│   ├── NetworkAnalysisPage.tsx← Centralidad, comunidades, predicción de enlaces
│   ├── TargetsPage.tsx        ← Navegador de proteínas diana (búsqueda + filtro humanos)
│   ├── TargetDetailPage.tsx   ← Perfil de diana: UniProt, SwissBioPics, red, rutas
│   ├── ToolsPage.tsx          ← Hub con sidebar; renderiza sub-rutas via <Outlet>
│   └── tools/
│       ├── DegAnalysisTool.tsx   ← CSV parser + volcano + overlap + GO enrichment
│       ├── RepurposingTool.tsx   ← Jaccard table + shared genes + GO perfil
│       ├── ToxicityTool.tsx      ← RiskMeter + AlertCard + CYPs + off-targets + cluster
│       └── DdiCheckerPage.tsx    ← Verificador de DDIs (modo par y modo lista)
│
├── hooks/
│   └── usePageTitle.ts        ← Actualiza document.title: "Nombre — DrugGraph"
│
├── components/
│   ├── CytoscapeGraph.tsx     ← Wrapper Cytoscape.js con cleanup seguro
│   ├── VolcanoPlot.tsx        ← SVG volcano plot (genes DEG + targets resaltados)
│   ├── GoEnrichmentChart.tsx  ← Barras horizontales SVG para términos GO/KEGG
│   └── drug-sections/
│       ├── Chemistry.tsx
│       ├── Clinical.tsx
│       ├── Genomics.tsx
│       ├── Market.tsx
│       ├── Targets.tsx
│       ├── GraphInteractionsSection.tsx  ← tabla + vista Cytoscape
│       └── PathwaysSection.tsx           ← 3 sub-tabs: directo/indirecto/KEGG
│
└── App.tsx                ← React Router: rutas públicas y protegidas
```

---

## 5.4 Responsabilidades por bloque

| Bloque | Responsabilidad única |
|--------|-----------------------|
| `config/services/mongo.py` | Proveer la conexión MongoDB; no ejecuta queries |
| `config/services/neo4j_service.py` | Proveer driver + sesiones + pipeline del grafo de un fármaco |
| `config/services/swiss_service.py` | Llamar a SwissTargetPrediction (API y CSV); cruzar resultados con Neo4j |
| `config/services/string_service.py` | PPI vecinos + enriquecimiento funcional con FDR real (endpoint `enrichment`) |
| `users/authentication.py` | Validar JWT en cada request; construir `request.user` |
| `drugs/services.py` | Queries MongoDB con proyecciones correctas; paginación |
| `drugs/views/targets.py` | Listar y detallar targets desde Neo4j; enriquecer con datos UniProt |
| `drugs/views/sandbox.py` | Sandbox analítico + rutas metabólicas (KEGG, GO, PPI) de targets |
| `drugs/views/tools.py` | DEG, reposicionamiento, toxicidad y verificación DDI |
| `drugs/urls.py` | Orden correcto de rutas (específicas antes del wildcard `<drug_id>/`) |
| `api/client.ts` | Un único punto de configuración Axios; adjunta JWT; maneja 401 global |
| `context/AuthContext.tsx` | Estado de sesión global; resuelve `me()` antes de renderizar hijos |
| `hooks/usePageTitle.ts` | Sincronizar `document.title` con el contexto de la página activa |
