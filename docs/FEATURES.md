# DrugGraph — Inventario de funciones

Listado de las funcionalidades de la plataforma, descritas de cara al usuario y con
las piezas de UI de cada pantalla. Pensado como insumo para diseño UI/UX (rediseño con
temática de "cuaderno científico", uso de modales, etc.).

> **Mantenimiento:** cuando se añada una función nueva a la plataforma, agregar aquí su
> fila/sección (qué hace, entradas del usuario, qué muestra) para mantener el inventario
> al día. Ruta, pantalla y endpoints en `docs/arc42/05_building_blocks.md`.

---

## 1. Autenticación y cuenta
| Función | Qué hace | Entradas del usuario | Qué muestra |
|---|---|---|---|
| **Login** (`/login`) | Inicia sesión | Email + contraseña | Formulario; errores de credenciales |
| **Registro** (`/register`) | Crea cuenta nueva | Nombre, email, contraseña | Formulario; validación |
| **Perfil** (`/profile`) | Ver/editar datos propios | Nombre, cambio de contraseña | Datos de cuenta, formulario de edición |

## 2. Dashboard (`/dashboard`)
- **Hub de acceso**: tarjetas hacia cada funcionalidad (con icono, título, descripción y "tag" de estado).
- **Estadísticas globales**: contadores grandes (nº fármacos, dianas, interacciones) y barras horizontales (distribución por tipo/grupo). Datos de `/api/drugs/stats/`.

## 3. Catálogo de fármacos
| Función | Qué hace | Entradas | Qué muestra |
|---|---|---|---|
| **Lista de fármacos** (`/drugs`) | Busca y filtra el catálogo | Texto de búsqueda (nombre/SMILES/sinónimo), filtros por tipo/grupo/aprobación | Lista paginada con scroll infinito; chips de filtro |
| **Detalle de fármaco** (`/drugs/:id`) | Ficha completa de un fármaco | — (navegación) | **Pestañas**: Química, Clínica, Genómica, Mercado, Dianas, **Grafo de interacciones** (Cytoscape), **Rutas** (KEGG/STRING/GO con sub-pestañas) |

## 4. Dianas (proteínas objetivo)
| Función | Qué hace | Entradas | Qué muestra |
|---|---|---|---|
| **Navegador de dianas** (`/targets`) | Explora proteínas objetivo | Búsqueda, filtro "solo humanas" | Lista con gen, organismo, nº fármacos |
| **Detalle de diana** (`/targets/:id`) | Perfil de una proteína | — | **Pestañas**: Info DrugBank, **UniProt** (+ SwissBioPics, imagen de localización celular), **Red** (grafo Cytoscape de fármacos), **Rutas & PPI** (KEGG + vecinos STRING expandibles) |

## 5. Laboratorio Virtual / Sandbox (`/sandbox`)
La pantalla más rica. Permite analizar un compuesto **sin tocar la base compartida**.
- **Entrada**: cadena SMILES + nombre + targets candidatos (autocompletado) o importados desde SwissTargetPrediction.
- **Resultados de similitud**: propiedades fisicoquímicas (peso, LogP, TPSA…), ranking combinado de fármacos similares (estructural Tanimoto + comportamiento Jaccard), con barras de score.
- **Rutas y red molecular** (carga diferida): rutas KEGG, GO (BP/MF/CC), Reactome, WikiPathways, vecinos STRING (PPI), interacciones químico-gen (CTD).
- **Cascada de efectos** (grafo Cytoscape): modo **dirigido** (activación ↑ / inhibición ↓, flechas verdes/rojas) y modo **difusión**.
- **Exportaciones**: CSV/JSON de cada sección + **informe HTML imprimible**.

## 6. BLAST — búsqueda por secuencia (`/blast`)
- **Entrada**: secuencia de aminoácidos (FASTA).
- **Qué hace**: encuentra proteínas homólogas por similitud de secuencia.
- **Muestra**: tarjetas de "hits" con alineamiento, identidad/cobertura, e-value y los fármacos que afectan a cada proteína.

## 7. Análisis de Red — GDS (`/network`)
**Pestañas**, requiere plugin GDS de Neo4j (si no, aviso 503):
- **Centralidad**: ranking de dianas-hub / fármacos multi-diana (barras de score).
- **Comunidades**: módulos fármaco-diana (Louvain), con **grafo Cytoscape** coloreado por comunidad.
- **Predicción de enlaces**: sugerencias de nuevos vínculos fármaco→diana (repurposing). Exporta CSV.

## 8. Herramientas analíticas (`/tools`, con barra lateral)
| Herramienta | Qué hace | Entradas | Qué muestra |
|---|---|---|---|
| **DEG Analysis** (`/tools/deg`) | Cruza genes de expresión diferencial con las dianas de un fármaco | CSV de genes (log2FC, p-valor), umbrales, fármaco | **Volcano plot**, tabla de solapamiento, enriquecimiento GO (g:Profiler) |
| **Reposicionamiento** (`/tools/repurposing`) | Candidatos a nuevo uso por similitud de dianas | Fármaco | Tabla Jaccard, genes compartidos, perfil GO |
| **Toxicidad** (`/tools/toxicity`) | Perfil de riesgo y off-targets | Fármaco | **Medidor de riesgo** (0–10), alertas por anti-targets (hERG, CYPs…), off-targets predichos, cluster estructural |
| **Verificador DDI** (`/tools/ddi`) | Interacciones fármaco-fármaco | Par de fármacos o lista | Resultado de interacción (modo par y modo lista) |

## 9. Ayuda (`/help`)
- Documentación de usuario navegable: barra lateral de secciones + contenido (guías paso a paso, referencia de API, primitivas tipo "cuaderno": bloques de código, notas, tablas, pasos numerados).

## 10. Administración (`/admin`, solo admin)
- Gestión de cuentas: crear, editar rol, restablecer contraseña, eliminar usuarios.

---

## Patrones de UI que se repiten (clave para el rediseño)
- **Grafos interactivos** (Cytoscape) en: detalle de fármaco, detalle de diana, sandbox (cascada), análisis de red.
- **Sistemas de pestañas** en: detalle de fármaco, detalle de diana, análisis de red, herramientas.
- **Tablas con exportación** (CSV/JSON/HTML) en sandbox, herramientas, análisis de red.
- **Formularios + carga diferida** (botón "cargar análisis") en sandbox y herramientas.
- **Badges/chips de estado** (tipo, grupo, nivel de riesgo, método usado).
- **Estados especiales**: cargando, error 503 (GDS/red no disponible), "no cargado todavía".

## Candidatos naturales a modal
- Importar dianas desde SwissTargetPrediction (sandbox).
- Vista ampliada de un grafo Cytoscape (fullscreen).
- Detalle de un "hit" BLAST o de un vecino PPI/CTD.
- Confirmaciones de admin (eliminar usuario, reset contraseña).
- Selector/buscador de fármaco para las herramientas (DEG/repurposing/toxicidad).
- Ayuda contextual (definiciones de Tanimoto, Jaccard, GDS, etc.) — encaja con la temática de "cuaderno científico" (notas al margen / fichas).
