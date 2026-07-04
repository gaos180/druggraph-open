# 03 — Alcance y Contexto

## 3.1 Contexto de Negocio

```
                      ┌──────────────────────────────────────────────────────┐
                      │                    DrugGraph                         │
                      │                                                      │
  Usuario            │  ┌──────────────┐        ┌─────────────────────────┐│
  (navegador) ───────┼─►│  React SPA   │───────►│   Django REST API       ││
                     │  │  (port 3000) │◄───────│   (port 8000)           ││
                      │  └──────────────┘        └──────┬───────┬──────────┘│
                      │                                 │       │            │
                      │                          ┌──────▼──┐  ┌─▼────────┐  │
                      │                          │ MongoDB │  │  Neo4j   │  │
                      │                          │ :27017  │  │  :7687   │  │
                      │                          └─────────┘  └──────────┘  │
                      └──────────────────────────────────────────────────────┘
                                    │                  │
                         ┌──────────▼──┐    ┌──────────▼──────────────┐
                         │  STRING API │    │       KEGG API          │
                         │ string-db.org│   │    rest.kegg.jp         │
                         └─────────────┘   └─────────────────────────┘
                                    │
                         ┌──────────▼──┐
                         │ blastp      │
                         │ (proceso    │
                         │  local)     │
                         └─────────────┘
```

## 3.2 Actores

| Actor | Descripción | Interacción principal |
|-------|-------------|----------------------|
| Usuario anónimo | Intenta acceder al sistema | Solo puede ver `/login` y `/register`; cualquier otro endpoint devuelve 401 |
| Usuario autenticado | Investigador o estudiante con cuenta | Navega por fármacos, ejecuta análisis de red, sandbox, BLAST |
| Administrador | Usuario con `is_admin: true` en MongoDB | Acceso a panel de administración (visible en Dashboard) |
| Sistema de CI/CD | Ejecuta tests automáticos | `manage.py test`, `npm test` |

## 3.3 Sistemas Externos

| Sistema | Protocolo | Datos que aporta | Degradación si falla |
|---------|-----------|-----------------|---------------------|
| **MongoDB** | pymongo / BSON | Documentos completos de fármacos (DrugBank JSON) + cuentas de usuario | Error 503 en todos los endpoints de fármacos |
| **Neo4j** | Bolt (neo4j-driver) | Grafo molecular: Drugs, Targets, Categories, Interactions | Error 503 en endpoints de grafo y GDS |
| **Neo4j GDS plugin** | Procedimientos Cypher | Centralidad, comunidades, predicción de enlaces | Endpoints GDS retornan 503; el resto funciona |
| **STRING API** | HTTPS/JSON | Red PPI para efecto indirecto | La sección "Efecto indirecto" muestra error parcial; resto de pathways funciona |
| **KEGG API** | HTTPS/texto plano | Rutas biológicas metabólicas | La sección KEGG muestra error parcial; efecto directo e indirecto funcionan |
| **NCBI BLAST+** | Subproceso local | Homología de secuencia proteica | Endpoint blast retorna 503; resto del sistema funciona |

## 3.4 Interfaces Técnicas

**Frontend → Backend**
- Protocolo: HTTP/1.1 sobre `localhost`
- Base URL: `http://localhost:8000/api`
- Autenticación: cabecera `Authorization: Bearer <jwt>`
- Formato: JSON (UTF-8)

**Backend → MongoDB**
- Driver: `pymongo` (singleton en `config/mongo.py`)
- Colecciones: `db.users`, `db.drugs`

**Backend → Neo4j**
- Driver: `neo4j` (singleton en `config/neo4j_service.py`)
- Protocolo: Bolt (`bolt://localhost:7687`)
- Sesiones manejadas con context manager `_session()`

**Backend → APIs externas**
- Librería: `requests` con timeout de 20 s
- Caché en memoria para reducir llamadas repetidas
- Rate limiting activo (STRING: 1 req/s, KEGG: 3 req/s)
