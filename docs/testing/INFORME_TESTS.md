# Informe de Tests — DrugGraph

**Fecha:** 2026-07-02
**Rama:** `main` (commit `27f7ad9`)
**Ejecutado por:** Agente QA (solo lectura, sin modificar código fuente)

---

## 1. Resumen ejecutivo

| Suite | Estado | Resultado |
|-------|--------|-----------|
| Backend (Django) | 🟢 **VERDE** | 80/80 tests pasan |
| Frontend (React) | 🟡 **AMARILLO** | 11/12 tests pasan — 1 fallo (test boilerplate obsoleto de CRA) |
| Smoke test estructura | 🟢 **VERDE** | `django check` OK, 21/21 servicios importan, `tsc --noEmit` OK |
| Infra (Docker/DBs) | 🟢 **VERDE** | MongoDB y Neo4j arriba (47 h de uptime) |
| Cobertura de features | 🟡 **AMARILLO** | Varias features clave sin tests (BLAST, pathways, propagación, herramientas DEG/toxicidad/repurposing) |

**Semáforo global: 🟡 AMARILLO.** El sistema está sano y compila; la única falla de test es un vestigio del template de Create React App (no un bug de producto). El punto de atención real es la **cobertura**: la suite backend es amplia pero se apoya en mocks (no ejercita las DBs reales), y varios endpoints importantes no tienen tests.

---

## 2. Entorno de ejecución

- **Working dir:** `/home/gabriel/Escritorio/2026-semestre-01/base_de_datos_avanzada/proyecto/druggraph/druggraph`
- **Bases de datos (Docker):**
  - `druggraph-mongodb` (mongo:7) → `Up 47 hours`, puerto 27017 ✅
  - `druggraph-neo4j` (neo4j:5) → `Up 47 hours`, puertos 7474/7687 ✅
- **venv backend:** presente en `backend/venv/`, dependencias instaladas correctamente.
- **Dependencias opcionales (todas presentes):**
  - `rdkit` 2026.03.3, `torch` 2.12.1+cpu, `transformers` 5.12.1, `omnipath` 1.0.12
  - `bcrypt` 5.0.0, `pyjwt` 2.13.0, `pymongo` 4.17.0, `neo4j` 6.2.0

> **Nota metodológica:** Los tests del backend usan `django.test.SimpleTestCase` con `unittest.mock`, es decir **mockean** Mongo/Neo4j y las APIs externas (STRING, KEGG, ChEMBL, Gemini, etc.). Por lo tanto, aunque las DBs están arriba, **la suite no valida integración real contra ellas** — se validan las vistas/serialización/lógica de forma aislada.

---

## 3. Resultados por suite

### 3.1 Backend — Django (`python manage.py test`)

```
Ran 80 tests in 15.683s
OK
System check identified no issues (0 silenced).
```

Desglose por módulo:

| Módulo | Tests | Estado |
|--------|-------|--------|
| `users.tests` | 22 | 🟢 |
| `drugs.tests` | 28 | 🟢 |
| `drugs.test_bioactivity` | 5 | 🟢 |
| `drugs.test_reports` | 7 | 🟢 |
| `drugs.test_similarity` | 4 | 🟢 |
| `drugs.test_embedding_similarity` | 4 | 🟢 |
| `drugs.test_ddi_risk` | 3 | 🟢 |
| `drugs.test_proximity` | 3 | 🟢 |
| `drugs.test_disease_evidence` | 2 | 🟢 |
| `drugs.test_signature_reversion` | 2 | 🟢 |
| **Total** | **80** | **🟢 100%** |

Áreas cubiertas: registro/login/logout, auth por cookie httpOnly + prioridad de header, JWT, CRUD admin de usuarios, listado/detalle/filtros de fármacos, paginación, sandbox (casos de error SMILES), GDS (centrality/communities/predict), grafo de targets, comparación de targets, DDI (pairwise y all), stats, bioactividad (ChEMBL/PubChem mock), riesgo DDI PK/PD, proximidad de red, evidencia de enfermedad, reportería IA (kinds inválidos, Gemini 503, fallback de modelo, auth), reversión de firma (LINCS), similitud por embedding (503, índice no poblado).

Único ruido: warnings de deprecación de RDKit (`please use MorganGenerator` / `AtomPairGenerator`) — informativos, no fallan tests.

### 3.2 Frontend — React (`react-scripts test --watchAll=false`, CI=true)

```
Test Suites: 1 failed, 3 passed, 4 total
Tests:       1 failed, 11 passed, 12 total
Time:        16.608 s
```

| Archivo | Tests | Estado |
|---------|-------|--------|
| `src/context/AuthContext.test.tsx` | 4 | 🟢 |
| `src/components/ErrorBoundary.test.tsx` | 3 | 🟢 |
| `src/features/drugs/DrugsPage.test.tsx` | 4 | 🟢 |
| `src/App.test.tsx` | 1 | 🔴 FALLA |

**Fallo (`src/App.test.tsx` → "renders learn react link"):**

```
TestingLibraryElementError: Unable to find an element with the text: /learn react/i
  5 | test('renders learn react link', () => {
  6 |   render(<App />);
> 7 |   const linkElement = screen.getByText(/learn react/i);
```

**Diagnóstico:** Es el **test boilerplate por defecto de Create React App**. Busca el texto "learn react" del template original, que ya no existe porque `App.tsx` renderiza el router real de DrugGraph. **No es un bug de producto**, es un test obsoleto que nunca se actualizó ni se borró. Debe eliminarse o reescribirse (fuera del alcance de este agente QA; se anota para el flujo de arreglos).

> Además se observan warnings `act(...)` provenientes de `src/hooks/useDrugs.ts:41` (actualización de estado fuera de `act`). No hacen fallar la suite pero indican tests que no envuelven correctamente las actualizaciones asíncronas.

---

## 4. Smoke test de estructura

| Verificación | Resultado |
|--------------|-----------|
| `python manage.py check` | 🟢 "0 issues" |
| Importación de los 21 servicios en `config/services/` | 🟢 Todos OK (blast, chemberta_index/service, chembl, ctd, gds, gemini, gprofiler, kegg, lincs, mongo, neo4j, opentargets, propagation, proximity, pubchem, report, string, swiss, uniprot) |
| Resolución de URLs Django | 🟢 51 rutas resuelven sin error |
| `npx tsc --noEmit` (frontend) | 🟢 Exit 0, sin errores de tipos |
| `frontend/build/` | Presente (build previo existe) |

El mapa de URLs resuelto está completo y coincide con lo declarado en `CLAUDE.md`, incluyendo rutas nuevas no documentadas en la tabla original (p. ej. `api/auth/logout/`, `api/auth/me/update/`, `api/auth/me/password/`, `api/auth/users/...`, `api/drugs/targets/...`, `api/drugs/stats/`, `api/drugs/ddi/`, `api/drugs/sandbox/{pathways,propagation,swiss-targets,bioactivity,similarity-detail,embedding-similarity}/`, `api/tools/{deg-analysis,repurposing,toxicity,proximity,disease-evidence,signature-reversion}/`).

---

## 5. Gaps de cobertura (features SIN tests)

Endpoints/servicios existentes que **no** tienen tests dedicados:

| Feature / endpoint | Situación |
|--------------------|-----------|
| **BLAST** (`/api/drugs/blast/search/`, `blast_service`) | Sin ningún test. Feature compleja (subprocess `blastp` + parseo). |
| **Pathways** (`/api/drugs/<id>/pathways/`, `/targets/<id>/pathways/`, `/sandbox/pathways/`) | Sin test. Integra Neo4j + STRING + KEGG. |
| **Propagación de efectos** (`/api/drugs/sandbox/propagation/`, `propagation_service`) | Sin test. Modos diffusion (PageRank/GDS) y directed/signed (REGULATES). |
| **Herramienta DEG** (`/api/tools/deg-analysis/`) | Sin test de endpoint (solo se testea el *trimmer* de reporte). |
| **Herramienta Repurposing** (`/api/tools/repurposing/<id>/`) | Sin test de endpoint. |
| **Herramienta Toxicidad** (`/api/tools/toxicity/<id>/`) | Sin test de endpoint. |
| **Swiss targets** (`/api/drugs/sandbox/swiss-targets/`, `swiss_service`) | Sin test. |
| **GDS predict-global** (`/api/drugs/gds/predict-global/`) | Sin test (solo se testea predict por drug). |
| **Grafo de fármaco** (`/api/drugs/<id>/graph/`) | Sin test directo (sí existe test del grafo de *target*). |
| **Targets by-gene / kegg-gene / uniprot** | Sin test. |
| **CTD service** (`ctd_service`) | Sin test unitario. |
| Servicios externos (`string_service`, `kegg_service`, `chembl_service`, `pubchem_service`, `opentargets_service`, `gprofiler_service`, `uniprot_service`) | Sin tests de parseo/caché propios (se mockean donde se usan). |

**Cobertura de integración real:** ningún test ejercita Mongo/Neo4j en vivo ni las APIs externas de verdad — todo mockeado. No hay tests end-to-end ni de contrato.

**Frontend:** solo 3 archivos de test con contenido real (AuthContext, ErrorBoundary, DrugsPage). Sin tests para SandboxPage, BlastPage, NetworkAnalysisPage, CytoscapeGraph, ReportPanel, MarkdownView, ni los componentes `drug-sections/`.

---

## 6. Recomendaciones priorizadas

**P0 — Rápido / alto impacto**
1. **Eliminar o reescribir `src/App.test.tsx`** (el test "learn react"). Es el único fallo de toda la batería y es un falso positivo del template CRA. Reemplazar por un smoke test que verifique que la app monta (p. ej. redirección a `/login`).

**P1 — Cobertura de features críticas sin tests**
2. Agregar tests de endpoint (con mocks, siguiendo el patrón `SimpleTestCase` existente) para **BLAST**, **pathways**, **propagación** y las **tres herramientas** (`deg-analysis`, `repurposing`, `toxicity`). Son features destacadas en `CLAUDE.md` y hoy no tienen red de seguridad.
3. Añadir tests para `predict-global`, `sandbox/swiss-targets`, `drugs/<id>/graph` y las rutas `targets/by-gene|kegg-gene|uniprot`.

**P2 — Calidad y robustez de la suite**
4. Corregir los warnings `act(...)` en los tests que usan `useDrugs` (envolver actualizaciones asíncronas en `waitFor`/`act`) para evitar flakiness futura.
5. Añadir tests unitarios de parseo/caché para los clientes de servicios externos (`string_service`, `kegg_service`, `chembl_service`, etc.) usando fixtures de respuesta guardadas — no requieren red.
6. Silenciar los warnings de deprecación de RDKit migrando a `MorganGenerator` (mejora higiene de logs; no afecta resultados).

**P3 — Integración**
7. Considerar una capa mínima de tests de integración marcados (`@skipUnless` por variable de entorno) que sí golpeen Mongo/Neo4j locales, para validar los queries Cypher y proyecciones Mongo reales que hoy solo se mockean.
8. Ampliar cobertura de frontend a las páginas/componentes clave (Sandbox, Network, ReportPanel, MarkdownView).

---

## 7. Comandos ejecutados (reproducibilidad)

```bash
# Infra
docker compose ps

# Backend
cd backend && source venv/bin/activate
python manage.py test
python manage.py check

# Frontend
cd frontend
CI=true npx react-scripts test --watchAll=false
npx tsc --noEmit
```

*Nota: no se modificó código fuente. Los fallos y gaps se documentan para su resolución en un flujo separado.*
