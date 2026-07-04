# 11 — Riesgos y Deuda Técnica

## 11.1 Riesgos Identificados

### R1: JWT almacenado en localStorage (XSS)

| Campo | Valor |
|-------|-------|
| **Probabilidad** | Media (depende de la seguridad del código React) |
| **Impacto** | Alto (robo de sesión) |
| **Mitigación actual** | React escapa automáticamente el HTML; no se usa `dangerouslySetInnerHTML` |
| **Mitigación recomendada** | Migrar a HttpOnly cookie para producción; agregar Content-Security-Policy |

### R2: Caché en memoria no compartida entre workers

| Campo | Valor |
|-------|-------|
| **Probabilidad** | Alta si se despliega con Gunicorn multi-worker |
| **Impacto** | Medio (múltiples llamadas a STRING/KEGG por el mismo dato en distintos workers) |
| **Mitigación actual** | Entorno académico de un solo proceso |
| **Mitigación recomendada** | Redis como caché compartida |

### R3: blastp no disponible en el PATH

| Campo | Valor |
|-------|-------|
| **Probabilidad** | Alta en instalaciones nuevas |
| **Impacto** | Medio (endpoint BLAST no funciona) |
| **Mitigación actual** | El endpoint retorna 503 con mensaje descriptivo |
| **Mitigación recomendada** | Incluir ncbi-blast+ en el Dockerfile o documentarlo como prerequisito explícito |

### R4: Nodos :SandboxDrug huérfanos

| Campo | Valor |
|-------|-------|
| **Probabilidad** | Media (el usuario puede cerrar el navegador sin hacer DELETE) |
| **Impacto** | Bajo (ocupan espacio en Neo4j) |
| **Mitigación actual** | `cleanup_old_sandbox_nodes()` elimina nodos >30 min |
| **Mitigación recomendada** | Llamar `cleanup_old_sandbox_nodes()` desde un job periódico (cron o Celery beat) |

### R5: Sincronización MongoDB ↔ Neo4j

| Campo | Valor |
|-------|-------|
| **Probabilidad** | Baja en contexto académico con datos estáticos |
| **Impacto** | Alto (inconsistencia entre detalle del fármaco en MongoDB y grafo en Neo4j) |
| **Mitigación actual** | Los datos se cargaron una vez; no hay mecanismo de actualización incremental |
| **Mitigación recomendada** | Script de re-carga con upsert que actualice ambas bases de datos |

---

## 11.2 Deuda Técnica

| ID | Deuda | Impacto si no se paga | Esfuerzo estimado |
|----|-------|----------------------|------------------|
| DT1 | Sin tests de integración para los servicios de MongoDB y Neo4j | Los tests unitarios no detectan regresiones en queries Cypher o proyecciones Mongo | Alto |
| DT2 | `JWT_SECRET` hardcodeado en `settings.py` como fallback | Si alguien olvida configurar la variable de entorno en producción, el sistema usa la clave pública | Bajo |
| DT3 | Paginación de fármacos sin índice de cursor en MongoDB | Con colecciones grandes, la paginación por `_id` puede ser lenta si no hay índice | Bajo |
| DT4 | `populate_fingerprints.py` debe ejecutarse manualmente | El sandbox estructural no funciona hasta que se corran los fingerprints; no hay verificación en arranque | Bajo |
| DT5 | `seed_admin.py` crea el admin con contraseña fija | Si se olvida cambiar la contraseña, el admin `admin@druggraph.dev / admin1234` es accesible | Bajo |
| DT6 | Sin límite de tamaño en la secuencia BLAST enviada | Un usuario malicioso podría enviar secuencias enormes que consuman mucha CPU/RAM en blastp | Medio |
| DT7 | CytoscapeGraph no tiene límite de nodos | Grafos muy grandes (>500 nodos) pueden freezar el navegador | Medio |
