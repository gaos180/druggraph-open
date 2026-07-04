# 04 — Estrategia de Solución

## 4.1 Decisiones Tecnológicas Clave

### Backend: Django sin ORM

**Decisión**: usar Django como framework HTTP pero sin activar el ORM (`INSTALLED_APPS` no incluye apps que generen migraciones; `users/models.py` y `drugs/models.py` son stubs).

**Justificación**: Los datos de DrugBank son documentos JSON profundamente anidados (fármacos con sub-objetos de interacciones, categorías, targets, mecanismos). Mapearlos a tablas relacionales requeriría decenas de tablas con joins complejos. MongoDB es el store natural para este esquema semiestructurado.

**Consecuencia**: todo el acceso a datos pasa por los singletons `get_db()` (pymongo) y `get_driver()` (neo4j); DRF se usa solo para el routing y la autenticación.

---

### Dos bases de datos especializadas

**Decisión**: MongoDB para documentos, Neo4j para el grafo.

| Necesidad | Por qué no una sola BD |
|-----------|------------------------|
| Recuperar el documento completo de un fármaco (>50 campos, arrays anidados) | Un grafo exigiría cientos de nodos/aristas por fármaco; un RDBMS necesitaría muchos joins |
| Navegar interacciones y calcular centralidad/comunidades | MongoDB no tiene primitivas de grafo; un RDBMS requeriría SQL recursivo |

Los dos stores se mantienen **sincronizados por diseño**: el mismo `drugbank_id` actúa como clave foránea lógica entre las colecciones de MongoDB y los nodos `:Drug` de Neo4j.

---

### Autenticación: JWT + clase DRF personalizada

**Decisión**: JWT firmado con HS256, verificado en `MongoJWTAuthentication`, sin la tabla `auth_user` de Django.

**Justificación**: Las cuentas de usuario se almacenan en MongoDB (`db.users`). No tiene sentido tener una segunda tabla de usuarios en SQLite/PostgreSQL solo para satisfacer a `django.contrib.auth`. La clase personalizada lee el token, decodifica el payload, y construye un `SimpleUser` (objeto ligero, no un modelo ORM).

---

### Frontend: React SPA con React Router v7

**Decisión**: SPA con rutas protegidas; el contexto de autenticación (`AuthContext`) envuelve toda la app.

**Consecuencia**: el servidor Django no sirve vistas HTML; solo expone la API REST. El frontend se despliega por separado (port 3000 en desarrollo, CDN en producción).

---

### APIs externas: caché en memoria + degradación elegante

**Decisión**: llamar a STRING y KEGG solo cuando el usuario accede a la sección de rutas; cachear resultados en memoria con TTL (STRING: 6 h, KEGG: 24 h).

**Justificación**: las APIs externas son lentas (varios segundos por request). Sin caché, la sección de rutas sería inutilizable para fármacos populares con muchos targets. La caché en memoria es suficiente para un servidor de instancia única en contexto académico.

**Degradación**: si STRING o KEGG fallan, los otros subsistemas (grafo Neo4j, sandbox, BLAST) siguen funcionando; el frontend muestra el error solo en la sección afectada.

---

## 4.2 Patrones Aplicados

| Patrón | Dónde | Descripción |
|--------|-------|-------------|
| Singleton | `config/mongo.py`, `config/neo4j_service.py` | Una conexión por proceso; se crea solo la primera vez |
| Proyecciones MongoDB | `drugs/services.py` | `LIST_PROJECTION` para listados rápidos; sin proyección para detalle completo |
| Paginación N+1 | `drugs/services.py` `list_drugs()` | Se piden `per_page+1` documentos; si llega el extra hay página siguiente (evita `count_documents` costoso) |
| Context manager | `config/neo4j_service.py` `_session()` | Garantiza cierre de sesión Neo4j aunque haya excepción |
| Nombre de proyección único | `config/gds_service.py` | Cada proyección GDS lleva UUID en el nombre; se elimina en el bloque `finally` para evitar conflictos entre requests concurrentes |
