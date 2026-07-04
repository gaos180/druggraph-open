# 10 — Requisitos de Calidad

## 10.1 Árbol de Calidad

```
Calidad DrugGraph
├── Funcionalidad
│   ├── Corrección de datos de interacción
│   └── Completitud de rutas biológicas
├── Rendimiento
│   ├── Latencia de listado de fármacos
│   ├── Latencia de grafo Neo4j
│   └── Latencia de análisis GDS
├── Disponibilidad
│   ├── Degradación elegante ante fallos de APIs externas
│   └── Independencia entre módulos
└── Seguridad
    ├── Autenticación en todos los endpoints de datos
    └── Aislamiento del sandbox
```

---

## 10.2 Escenarios de Calidad

### Escenario Q1: Corrección de interacciones

| Campo | Valor |
|-------|-------|
| **Fuente** | Usuario investigador |
| **Estímulo** | Abre el perfil del fármaco Ibuprofeno (DB01050) |
| **Respuesta esperada** | Los targets listados en la pestaña "Interacciones" coinciden exactamente con los registrados en el dataset de DrugBank cargado en Neo4j |
| **Medida** | 100% de coincidencia en un conjunto de validación de 10 fármacos conocidos |
| **Prioridad** | Alta |

### Escenario Q2: Latencia de listado

| Campo | Valor |
|-------|-------|
| **Fuente** | Usuario navegando la base de datos |
| **Estímulo** | Solicita la primera página de fármacos (filtro por tipo) |
| **Respuesta esperada** | La respuesta llega en menos de 2 segundos |
| **Condición** | MongoDB con ≤ 10 000 documentos en la colección `drugs` |
| **Prioridad** | Media |

### Escenario Q3: Degradación de STRING

| Campo | Valor |
|-------|-------|
| **Fuente** | Sistema (STRING API no disponible) |
| **Estímulo** | `GET /api/drugs/DB01050/pathways/?include=string,kegg` mientras `string-db.org` no responde |
| **Respuesta esperada** | HTTP 200 con `"indirect": null` y nota informativa en `"notes"`; la sección KEGG se carga correctamente |
| **Medida** | El frontend muestra el error solo en la sub-pestaña "Efecto indirecto", el resto funciona |
| **Prioridad** | Media |

### Escenario Q4: Seguridad de endpoints

| Campo | Valor |
|-------|-------|
| **Fuente** | Cliente no autenticado |
| **Estímulo** | `GET /api/drugs/` sin cabecera Authorization |
| **Respuesta esperada** | HTTP 401 con mensaje de error; ningún dato devuelto |
| **Medida** | Todos los endpoints excepto `/api/auth/register/` y `/api/auth/login/` devuelven 401 sin token |
| **Prioridad** | Alta |

### Escenario Q5: GDS no instalado

| Campo | Valor |
|-------|-------|
| **Fuente** | Administrador que arrancó Neo4j sin el plugin GDS |
| **Estímulo** | `GET /api/drugs/gds/centrality/` |
| **Respuesta esperada** | HTTP 503 con mensaje "Neo4j GDS no disponible"; resto del sistema operativo |
| **Medida** | Los endpoints de listado y grafo siguen respondiendo correctamente |
| **Prioridad** | Media |

### Escenario Q6: Limpieza del sandbox

| Campo | Valor |
|-------|-------|
| **Fuente** | Nodo `:SandboxDrug` creado hace más de 30 minutos sin limpieza manual |
| **Respuesta esperada** | El nodo es eliminado por `cleanup_old_sandbox_nodes()` antes de cumplir 31 minutos |
| **Medida** | El conteo de nodos `:SandboxDrug` no crece indefinidamente; se estabiliza |
| **Prioridad** | Baja |
