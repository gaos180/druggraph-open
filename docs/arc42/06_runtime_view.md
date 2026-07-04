# 06 — Vista de Tiempo de Ejecución

## 6.1 Flujo: Login de usuario

```
Navegador                 React SPA               Django                MongoDB
   │                          │                      │                      │
   │──POST /api/auth/login────►│                      │                      │
   │                          │──POST /api/auth/login►│                      │
   │                          │                      │──find_one(email)─────►│
   │                          │                      │◄──user doc────────────│
   │                          │                      │  bcrypt.verify()      │
   │                          │                      │  jwt.encode()         │
   │                          │◄──{ token, user }────│                      │
   │                          │ localStorage.set(     │                      │
   │                          │   'dg_token', token)  │                      │
   │◄──redirect /dashboard────│                      │                      │
```

## 6.2 Flujo: Listado de fármacos con paginación

```
Navegador          Axios (client.ts)    drugs/views.py    drugs/services.py   MongoDB
   │                     │                   │                  │                │
   │──GET /drugs─────────►│                  │                  │                │
   │                     │──GET /api/drugs/──►                  │                │
   │                     │  (Bearer: token)  │──list_drugs()───►│                │
   │                     │                   │                  │──cursor.limit  │
   │                     │                   │                  │  (per_page+1)──►│
   │                     │                   │                  │◄──docs──────────│
   │                     │                   │◄──{results,      │                │
   │                     │                   │    next_cursor,  │                │
   │                     │                   │    has_more}─────│                │
   │◄──{drugs, meta}─────│◄──200 JSON────────│                  │                │
```

**Nota**: `list_drugs()` pide `per_page+1` documentos. Si llegan más de `per_page`, existe página siguiente y se emite un `next_cursor` (ID del último documento). Esto evita `count_documents()` que es costoso en colecciones grandes.

## 6.3 Flujo: Vista de grafo de un fármaco (Neo4j)

```
DrugDetailPage        drugs/views_graph.py    neo4j_service.py      Neo4j
      │                       │                      │                 │
      │──GET /api/drugs/DB001/graph/─►               │                 │
      │                       │──get_drug_graph()───►│                 │
      │                       │                      │──Query 1: Drug+Targets──►│
      │                       │                      │◄──rows───────────────────│
      │                       │                      │──Query 2: Categories────►│
      │                       │                      │◄──rows───────────────────│
      │                       │                      │──Query 3: Drug-Drug──────►│
      │                       │                      │◄──rows───────────────────│
      │                       │                      │──Query 4: Polypeptides───►│
      │                       │                      │◄──rows───────────────────│
      │                       │◄──{nodes, edges}─────│                 │
      │◄──JSON────────────────│                      │                 │
      │  CytoscapeGraph.tsx   │                      │                 │
      │  renderiza el grafo   │                      │                 │
```

## 6.4 Flujo: Búsqueda BLAST

```
BlastSearchPage    views_blast.py    blast_service.py   blastp (OS)   Neo4j
      │                 │                  │                  │          │
      │──POST /blast/search/─►             │                  │          │
      │  {sequence, organism}  │──run()───►│                  │          │
      │                        │           │──subprocess──────►│          │
      │                        │           │  (blastp -outfmt 6)          │
      │                        │           │◄──stdout (TSV)───│          │
      │                        │           │  parse_hits()     │          │
      │                        │           │──enrich_hits()────────────── ►│
      │                        │           │  (MATCH Drug WHERE id IN …) │
      │                        │           │◄──drug metadata──────────────│
      │◄──{hits}───────────────│◄──hits────│                  │          │
```

## 6.5 Flujo: Análisis GDS (centralidad)

```
NetworkAnalysisPage   views_gds.py   gds_service.py   Neo4j (GDS plugin)
        │                  │               │                    │
        │──GET /gds/centrality/──►         │                    │
        │                  │──centrality()►│                    │
        │                  │               │──CALL gds.graph    │
        │                  │               │  .project(uuid)────►│
        │                  │               │◄──graph projected───│
        │                  │               │──CALL gds.pageRank──►│
        │                  │               │◄──scores────────────│
        │                  │               │──DROP projection────►│
        │                  │               │◄──ok────────────────│
        │◄──{nodes}─────────│◄──results─────│                    │
```

Si el plugin GDS no está instalado, Neo4j devuelve un error en `CALL gds.*`; `gds_service.py` lo captura y lanza `GDSUnavailable`, que el view convierte en HTTP 503.

## 6.6 Flujo: Sandbox (nuevo compuesto virtual)

```
SandboxPage    views_sandbox.py    sandbox_service.py   RDKit   Neo4j
     │               │                   │               │        │
     │──POST /sandbox/analyze/──►        │               │        │
     │  {smiles, name, targets}  │──analyze()──►         │        │
     │                           │               │──MolFromSmiles()►│
     │                           │               │  Morgan FP      │
     │                           │               │──CREATE (:SandboxDrug)──►│
     │                           │               │◄──node created───────────│
     │                           │               │──MATCH drugs WHERE …─────►│
     │                           │               │  Tanimoto similarity      │
     │                           │               │◄──similar drugs──────────│
     │◄──{sandbox_id, similar}───│◄──results─────│               │        │
     │                           │               │               │        │
     │──DELETE /sandbox/{id}/──►│               │               │        │
     │                           │──cleanup()───►│               │        │
     │                           │               │──DETACH DELETE─────────►│
```
