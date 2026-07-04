# 09 — Decisiones de Arquitectura (ADRs)

## ADR-001: MongoDB como store principal de documentos de fármacos

**Estado**: Aceptado  
**Fecha**: 2026

**Contexto**:  
Los datos de DrugBank son documentos JSON profundamente anidados. Cada fármaco tiene arrays de targets, categorías, interacciones, mecanismos de acción, etc. (>50 campos potenciales).

**Decisión**:  
Almacenar los documentos completos de DrugBank en MongoDB, sin ningún mapeo a tablas relacionales.

**Consecuencias**:
- (+) Las queries de detalle recuperan un solo documento; sin joins.
- (+) El esquema DrugBank puede evolucionar sin migraciones.
- (-) No hay integridad referencial entre colecciones.
- (-) Las queries de agregación complejas son menos intuitivas que SQL.

---

## ADR-002: Neo4j para el grafo de interacciones

**Estado**: Aceptado  
**Fecha**: 2026

**Contexto**:  
Las relaciones Drug→Target, Drug→Category, Drug↔Drug forman un grafo. Los algoritmos de centralidad y detección de comunidades son nativas de bases de datos de grafos.

**Decisión**:  
Duplicar las entidades clave (Drug, Target, Category) en Neo4j y mantener las relaciones como aristas tipadas.

**Consecuencias**:
- (+) Cypher expresa traversals de grafo de forma natural.
- (+) GDS plugin habilita PageRank, Louvain, link prediction sin código adicional.
- (-) Duplicación de datos: un fármaco existe en MongoDB (completo) y en Neo4j (propiedades clave).
- (-) Requiere sincronización manual si los datos cambian.

---

## ADR-003: Django sin ORM

**Estado**: Aceptado  
**Fecha**: 2026

**Contexto**:  
Django fue elegido como framework web por su ecosistema (DRF, middleware, gestión de URLs). Sin embargo, el ORM genera tablas relacionales incompatibles con el diseño de datos.

**Decisión**:  
Usar Django+DRF únicamente para routing, middleware y autenticación. No usar `makemigrations` ni `migrate`. `users/models.py` y `drugs/models.py` son stubs vacíos.

**Consecuencias**:
- (+) Se mantiene el ecosistema Django (DRF, admin, manejo de settings).
- (-) No se puede usar el admin de Django para gestionar datos.
- (-) Los tests no pueden usar fixtures del ORM; deben mockear las conexiones o usar bases de datos reales.

---

## ADR-004: JWT con clase de autenticación personalizada

**Estado**: Aceptado  
**Fecha**: 2026

**Contexto**:  
`django.contrib.auth` espera modelos ORM para los usuarios. Las cuentas se almacenan en MongoDB.

**Decisión**:  
Implementar `MongoJWTAuthentication(BaseAuthentication)` que lee el token Bearer, lo decodifica con `PyJWT`, carga el usuario desde MongoDB, y retorna un `SimpleUser` (dataclass ligera).

**Consecuencias**:
- (+) No hay tabla de usuarios SQLite; las cuentas viven en MongoDB junto con el resto de los datos.
- (-) No se puede usar `@login_required` de Django ni `IsAuthenticated` nativo sin adaptación.

---

## ADR-005: Cytoscape.js con `animate: false`

**Estado**: Aceptado  
**Fecha**: 2026

**Contexto**:  
El wrapper `CytoscapeGraph.tsx` presentaba el error "can't access property 'notify', renderer is null" al desmontar el componente React. La causa raíz era que el layout con `animate: true` abre un loop `requestAnimationFrame` que dispara después de que `cy.destroy()` nulifique el renderer.

**Decisión**:  
Forzar `animate: false` en todas las llamadas a `cy.layout().run()`. Agregar un `layoutRef` para detener el layout (`layoutRef.current?.stop()`) antes de destruir la instancia de Cytoscape.

**Consecuencias**:
- (+) Elimina el crash en desmontaje; el componente es seguro en React strict mode.
- (-) Las transiciones de layout no son animadas (las posiciones aparecen instantáneamente).

---

## ADR-006: Proyecciones GDS con nombres UUID

**Estado**: Aceptado  
**Fecha**: 2026

**Contexto**:  
Las proyecciones de grafo en Neo4j GDS son globales al servidor. Si dos requests concurrentes intentan crear una proyección con el mismo nombre, una falla con error de nombre duplicado.

**Decisión**:  
Cada llamada a GDS genera un nombre de proyección único con UUID (`f"druggraph_{uuid.uuid4().hex}"`). La proyección se elimina siempre en el bloque `finally`.

**Consecuencias**:
- (+) Seguro bajo concurrencia; múltiples requests pueden ejecutar GDS simultáneamente.
- (-) Overhead de crear/eliminar proyecciones en cada request (aceptable dado el volumen académico).

---

## ADR-007: STRING `enrichment` en lugar de `functional_annotation`

**Estado**: Aceptado  
**Fecha**: 2026

**Contexto**:  
`config/string_service.py` necesitaba calcular enriquecimiento funcional (GO, KEGG, Reactome, WikiPathways) con p-valores corregidos. El endpoint `functional_annotation` de STRING parecía el candidato natural, pero tras pruebas se detectó que devuelve `fdr=None` para todos los términos: no realiza enriquecimiento estadístico, solo anota qué genes pertenecen a cada término.

**Decisión**:  
Usar el endpoint `enrichment` de STRING, que calcula enriquecimiento contra un fondo genómico completo y retorna FDR reales (Benjamini-Hochberg). Las categorías de respuesta son: `Process` (GO:BP), `Function` (GO:MF), `Component` (GO:CC), `KEGG`, `RCTM` (Reactome), `WikiPathways`. Además, `enrichment` retorna `inputGenes` como lista Python (no como string separado por comas).

**Consecuencias**:
- (+) Los FDR retornados son estadísticamente válidos; permiten filtrar términos significativos.
- (+) La respuesta es directamente parseable sin dividir strings.
- (-) El endpoint `enrichment` requiere al menos 2 proteínas en la lista de entrada; con menos, STRING retorna error.
- (-) Mayor latencia que `functional_annotation` (cálculo estadístico en servidor STRING).

---

## ADR-008: Hook `usePageTitle` para títulos dinámicos

**Estado**: Aceptado  
**Fecha**: 2026

**Contexto**:  
Las páginas de la SPA no actualizaban `document.title`, lo que dificultaba la navegación por pestañas del navegador y el SEO básico.

**Decisión**:  
Implementar el hook `hooks/usePageTitle.ts` que recibe un `string` y llama a `document.title = title` en un efecto. El formato es `"Nombre de página — DrugGraph"`. Para páginas con datos dinámicos (`DrugDetailPage`, `TargetDetailPage`), el hook se llama tras la carga del recurso con el nombre real del fármaco o diana.

**Consecuencias**:
- (+) Todas las páginas tienen títulos descriptivos sin lógica duplicada.
- (+) El hook es un `useEffect` de una línea: cero complejidad.
- (-) En páginas con carga asíncrona, el título muestra `"Cargando... — DrugGraph"` durante la petición antes de actualizarse al nombre definitivo.

---

## ADR-009: Carga diferida (lazy-load) de rutas sandbox

**Estado**: Aceptado  
**Fecha**: 2026

**Contexto**:  
El análisis de rutas metabólicas y enriquecimiento funcional del sandbox (`POST /api/drugs/sandbox/pathways/`) puede tardar entre 30 y 90 segundos debido al rate-limiting de las APIs externas (STRING, KEGG). Incluirlo en la respuesta inicial de `sandbox/analyze/` bloquearía la UI durante ese tiempo.

**Decisión**:  
Implementar carga diferida en `SandboxPage.tsx`: tras recibir los resultados del análisis estructural/comportamental, se muestra un botón **"Cargar rutas metabólicas"**. Al hacer clic, el frontend llama a `POST /api/drugs/sandbox/pathways/` pasando los `target_ids` y `drug_ids` del análisis previo. La UI muestra un spinner de progreso durante la espera.

**Consecuencias**:
- (+) El análisis principal (similitud Tanimoto + Jaccard) sigue siendo rápido (< 15 s).
- (+) Los usuarios que no necesitan las rutas no pagan el coste de la llamada a STRING/KEGG.
- (-) La información de rutas requiere un segundo clic explícito; no aparece automáticamente.
- (-) El endpoint de pathways acepta un máximo de 30 targets y 10 drug_ids; listas más grandes se truncan con nota en la respuesta.
