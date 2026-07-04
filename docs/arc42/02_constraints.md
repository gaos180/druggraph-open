# 02 — Restricciones

## 2.1 Restricciones Técnicas

| ID | Restricción | Motivo |
|----|------------|--------|
| T1 | **Sin ORM de Django** — `users/models.py` y `drugs/models.py` son stubs vacíos | El diseño requiere MongoDB como store principal; el ORM generaría esquemas relacionales incompatibles con documentos DrugBank |
| T2 | **Python ≥ 3.10** | Se usa la sintaxis `str \| None` (union types con `\|`) en las firmas de los servicios |
| T3 | **MongoDB ≥ 5.0** y **Neo4j ≥ 5.x** con GDS plugin opcional | GDS requiere al menos Community Edition de Neo4j 5.x; los endpoints GDS degradan a 503 si el plugin no está instalado |
| T4 | **Node.js ≥ 18** | Dependencias del frontend (React 18, TypeScript 5) requieren esta versión mínima |
| T5 | **`blastp` (NCBI BLAST+) instalado en el sistema** | `blast_service.py` lanza un subproceso; si no está en PATH el endpoint retorna 503 |
| T6 | **RDKit opcional** | La similitud estructural Tanimoto en el sandbox requiere RDKit; sin él la similitud molecular queda deshabilitada pero el resto del sandbox funciona |

## 2.2 Restricciones Organizativas / de Convención

| ID | Restricción | Motivo |
|----|------------|--------|
| O1 | **JWT en `localStorage`** bajo la clave `dg_token` | Implementación actual del frontend; simplifica el ciclo de vida del token en el contexto académico |
| O2 | **Sin variables de entorno en frontend** más allá de `REACT_APP_API_URL` | El frontend usa valores hardcodeados para el baseURL de Axios; en producción se parametriza con esta variable |
| O3 | **Autenticación requerida en todos los endpoints de datos** | La clase `MongoJWTAuthentication` está registrada globalmente en `REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES` |
| O4 | **Nodos `:SandboxDrug` son temporales** | El sandbox crea nodos temporales en Neo4j con TTL implícito; deben limpiarse con el endpoint DELETE o el job de limpieza |
| O5 | **APIs externas (STRING, KEGG) son de uso académico** | Sus términos de servicio requieren identificación del caller y uso no comercial; `CALLER_IDENTITY = "druggraph.app"` cumple este requisito |

## 2.3 Convenciones del Código

| Área | Convención |
|------|-----------|
| Naming | snake_case en Python; camelCase/PascalCase en TypeScript |
| Servicios | Funciones puras en `config/` y `*/services.py`; las vistas solo orquestan |
| Caché | In-memory con TTL; STRING: 6 h, KEGG: 24 h |
| Errores HTTP | 404 entidad no encontrada; 503 dependencia externa no disponible; 500 error inesperado |
| Respuestas JSON | Siempre `json_dumps_params={"ensure_ascii": False}` para nombres en Unicode |
