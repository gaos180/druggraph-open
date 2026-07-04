# Guía de Usuario — DrugGraph

Esta guía explica, paso a paso y en lenguaje sencillo, cómo usar cada funcionalidad de
**DrugGraph**. No hace falta saber programar: todo se opera desde el navegador web.

DrugGraph es una plataforma para **explorar fármacos y sus interacciones moleculares**.
Combina un catálogo de fármacos, un grafo de dianas e interacciones, y un conjunto de
herramientas de análisis (similitud molecular, rutas biológicas, toxicidad,
reposicionamiento, etc.), con la opción de generar informes automáticos con inteligencia
artificial.

> **Nota importante:** todos los resultados son *in silico* (calculados por computadora a
> partir de bases de datos y modelos). Son una ayuda para la exploración y la generación de
> hipótesis, **no** un dictamen clínico ni un sustituto de la evidencia experimental.

---

## Índice

1. [Primeros pasos: registro, inicio de sesión y perfil](#1-primeros-pasos)
2. [Panel principal (Dashboard)](#2-panel-principal-dashboard)
3. [Buscar y explorar fármacos](#3-buscar-y-explorar-farmacos)
4. [Ficha de un fármaco: las secciones](#4-ficha-de-un-farmaco)
5. [Grafo de interacciones](#5-grafo-de-interacciones)
6. [Rutas biológicas (Pathways)](#6-rutas-biologicas-pathways)
7. [Laboratorio virtual (Sandbox)](#7-laboratorio-virtual-sandbox)
8. [BLAST: búsqueda por secuencia](#8-blast-busqueda-por-secuencia)
9. [Análisis de red global (GDS)](#9-analisis-de-red-global-gds)
10. [Navegador de dianas](#10-navegador-de-dianas)
11. [Herramientas analíticas](#11-herramientas-analiticas)
12. [Reportería con IA (Gemini)](#12-reporteria-con-ia-gemini)
13. [Administración de usuarios](#13-administracion-de-usuarios)
14. [Prerrequisitos de cada funcionalidad](#14-prerrequisitos-de-cada-funcionalidad)

---

## 1. Primeros pasos

### Registro
1. Abre `http://localhost:3000` y entra a **Crear cuenta** (`/register`).
2. Completa nombre, correo y contraseña.
3. Al registrarte, la sesión se inicia automáticamente.

### Inicio de sesión
- Entra a **Iniciar sesión** (`/login`) con tu correo y contraseña.
- La sesión se mantiene con un token que **caduca a las 24 horas**; cuando esté por vencer
  verás un aviso. Si expira, se te pedirá volver a iniciar sesión.

### Perfil (`/profile`)
- Consulta y edita tu nombre.
- Cambia tu contraseña (introduciendo la actual y la nueva).
- Cierra sesión desde el menú de la aplicación.

---

## 2. Panel principal (Dashboard)

Tras iniciar sesión llegas al **Dashboard** (`/dashboard`), que funciona como centro de
navegación:

- **Tarjetas de acceso** a cada funcionalidad (fármacos, dianas, sandbox, BLAST, red,
  herramientas), cada una con su descripción.
- **Estadísticas globales**: número de fármacos, dianas e interacciones, y la distribución
  por tipo/grupo terapéutico.

---

## 3. Buscar y explorar fármacos

Entra a **Fármacos** (`/drugs`).

- **Barra de búsqueda**: escribe un nombre, un sinónimo o parte de él. La búsqueda responde
  mientras escribes (tipo *type-ahead*). También reconoce palabras completas de forma más
  rápida y precisa.
- **Filtros**: acota por **tipo** de fármaco (por ejemplo, molécula pequeña o biotech) y por
  **grupo** (aprobado, experimental, etc.).
- **Lista con scroll infinito**: a medida que bajas se cargan más resultados.
- Haz clic en cualquier fármaco para abrir su **ficha detallada**.

---

## 4. Ficha de un fármaco

La ficha (`/drugs/:id`) organiza toda la información en pestañas:

| Pestaña | Qué contiene |
|---------|--------------|
| **Química** | Estructura, fórmula, peso molecular, SMILES/InChI y propiedades fisicoquímicas. |
| **Clínica** | Indicaciones, farmacología, mecanismo de acción, toxicidad y precauciones. |
| **Genómica** | Información farmacogenómica y dianas a nivel de gen. |
| **Mercado** | Datos comerciales: fabricantes, presentaciones, precios y patentes. |
| **Dianas** | Proteínas objetivo del fármaco (con su gen y organismo). |
| **Grafo de interacciones** | Visualización interactiva de la red del fármaco (ver [sección 5](#5-grafo-de-interacciones)). |
| **Rutas (Pathways)** | Rutas biológicas afectadas (ver [sección 6](#6-rutas-biologicas-pathways)). |
| **Bioactividad** | Actividad experimental medida (ChEMBL/PubChem), si hay conexión a internet. |

---

## 5. Grafo de interacciones

Dentro de la ficha del fármaco, la pestaña **Grafo de interacciones** muestra una red
interactiva (Cytoscape) con:

- **Fármaco → Diana**: las proteínas que ataca.
- **Fármaco → Categoría**: sus categorías terapéuticas.
- **Fármaco ↔ Fármaco**: otros fármacos con los que interactúa.

Los nodos están **coloreados por tipo**. Puedes hacer **zoom**, **desplazar** (pan) y hacer
**clic** sobre un nodo para ver su detalle. Es la forma visual de entender el entorno
molecular de un fármaco.

---

## 6. Rutas biológicas (Pathways)

La pestaña **Rutas** parte de las dianas del fármaco y muestra:

1. **Efecto directo**: las proteínas diana del fármaco.
2. **Vecinos PPI (STRING)**: proteínas que interactúan físicamente con esas dianas
   (efecto indirecto).
3. **Enriquecimiento funcional**: rutas y funciones sobre-representadas (GO, KEGG, Reactome,
   WikiPathways) con su valor **FDR** (cuán significativo es).

Requiere conexión a internet (consulta las APIs públicas de STRING y KEGG; no necesita clave).

---

## 7. Laboratorio virtual (Sandbox)

El **Sandbox** (`/sandbox`) es la pantalla más potente. Permite analizar un **compuesto
nuevo** (que no está en la base) **sin modificar los datos compartidos**: se crea un nodo
temporal que se borra solo (a los 30 minutos).

### Cómo se usa
1. Ingresa la **cadena SMILES** del compuesto y un **nombre**.
2. Opcionalmente añade **dianas candidatas** (con autocompletado) o impórtalas desde una
   predicción de dianas.
3. Ejecuta el análisis.

### Qué obtienes
- **Propiedades fisicoquímicas**: peso molecular, LogP, TPSA, etc. (calculadas con RDKit).
- **Fármacos similares por estructura (Tanimoto)**: ranking de los fármacos de la base más
  parecidos, usando huellas moleculares Morgan/ECFP4, con opción de **consenso
  multi-huella**.
- **Similitud por embedding (ChemBERTa)** *(opcional)*: similitud "aprendida" por un modelo
  de lenguaje molecular, complementaria a Tanimoto.
- **Fármacos similares por comportamiento (Jaccard)**: parecido según las proteínas diana
  que comparten.
- **Rutas y red molecular** (carga diferida): rutas KEGG, términos GO, Reactome,
  WikiPathways, vecinos STRING (PPI) e **interacciones químico-gen curadas (CTD)**.
- **Bioactividad experimental** (ChEMBL/PubChem) del compuesto, si existe.
- **Cascada de efectos** (grafo): predice cómo se propaga el efecto del compuesto por la red:
  - **Modo difusión**: magnitud del efecto sobre genes cercanos (PageRank personalizado
    sobre la red STRING).
  - **Modo dirigido/firmado**: predice **activación (↑)** o **inhibición (↓)** de cada gen
    aguas abajo (flechas verdes/rojas), usando relaciones regulatorias con dirección y signo.
- **Exportaciones**: cada sección se puede descargar en CSV/JSON, y hay un **informe HTML
  imprimible**.

> Cada sub-análisis puede alimentar la [reportería IA](#12-reporteria-con-ia-gemini).

---

## 8. BLAST: búsqueda por secuencia

En **BLAST** (`/blast`) buscas proteínas diana **parecidas a una secuencia** que tú aportas.

1. Pega una **secuencia de aminoácidos** (formato FASTA).
2. Ejecuta la búsqueda.
3. Obtienes **tarjetas de resultados (hits)** con: alineamiento, porcentaje de identidad y
   cobertura, *e-value*, y **los fármacos que actúan** sobre cada proteína encontrada.

Útil para saber a qué dianas conocidas se parece una proteína nueva y qué fármacos podrían
afectarla.

---

## 9. Análisis de red global (GDS)

En **Análisis de red** (`/network`) exploras el grafo completo de fármacos y dianas con
algoritmos de grafos (Neo4j GDS):

- **Centralidad (PageRank)**: qué nodos son más "influyentes" en la red.
- **Comunidades (Louvain)**: agrupa fármacos/dianas en módulos relacionados.
- **Predicción de enlaces**: sugiere interacciones probables aún no registradas (para un
  fármaco concreto o de forma global).
- **Visualización** del grafo global con Cytoscape.

> Requiere el plugin **GDS** instalado en Neo4j. Si no está, la pantalla muestra un aviso
> (error 503) en lugar de resultados.

---

## 10. Navegador de dianas

En **Dianas** (`/targets`) exploras las proteínas objetivo:

- **Lista** con gen, organismo y número de fármacos que las atacan; con búsqueda y filtro
  "solo humanas".
- **Detalle de una diana** (`/targets/:id`) en pestañas: información de DrugBank, perfil
  **UniProt** (con imagen de localización subcelular de SwissBioPics), **red** de fármacos
  (grafo) y **rutas & PPI** (KEGG + vecinos STRING).
- **Comparador de dianas** (`/targets/compare`): compara dos proteínas por similitud de ruta
  (PathSim), vecinos comunes y rutas compartidas.

---

## 11. Herramientas analíticas

Se agrupan bajo **Herramientas** (`/tools`). Todas trabajan sobre un fármaco o entrada que
tú eliges.

### Verificador de interacciones (DDI) — `/tools/ddi`
- **DDI documentada**: interacciones ya descritas entre dos fármacos.
- **Riesgo predicho (PK/PD)**: estima el riesgo de interacción **sin modelos de ML**, según
  enzimas CYP450 compartidas (farmacocinética), dianas comunes y proximidad de sus módulos
  en la red (farmacodinámica).

### Análisis DEG (expresión diferencial) — `/tools/deg`
- Subes/introduces una lista de genes con sus valores de expresión.
- La herramienta clasifica los genes en **al alza / a la baja / significativos**, los cruza
  con las dianas de un fármaco y calcula el **enriquecimiento GO** (g:Profiler) de la
  intersección.
- Se conecta de forma natural con la **reversión de firma** (abajo).

### Reposicionamiento — `/tools/repurposing`
- Para un fármaco, encuentra **candidatos a nuevos usos** por similitud de su red de dianas
  (índice de Jaccard), junto con el perfil GO del fármaco consultado.

### Toxicidad — `/tools/toxicity`
- Para un fármaco, evalúa el riesgo combinando: **anti-targets** clínicamente relevantes
  (hERG/KCNH2, SCN5A, CYPs, etc.), **off-targets predichos** por topología de la red
  (Adamic-Adar), un **cluster estructural** de fármacos similares y una **puntuación de
  riesgo agregada (0–10)**.

### Proximidad de red *(medicina de redes)*
- Calcula la **distancia `d_c`** entre los módulos de dianas de **dos fármacos** en el
  interactoma STRING. Cuanto menor es la distancia, más cercanos están funcionalmente.

### Evidencia diana → enfermedad
- Para un fármaco, lista **enfermedades asociadas** a su módulo de dianas con un score
  integrado de **Open Targets** (hipótesis para reposicionamiento).

### Reversión de firma transcriptómica
- A partir de genes **al alza** y **a la baja**, busca fármacos que **reviertan** (o imiten)
  esa firma usando **LINCS L1000**, con un score de conectividad. Ideal como continuación del
  análisis DEG.

---

## 12. Reportería con IA (Gemini)

Casi todos los análisis (sandbox, reposicionamiento, toxicidad, DEG, DDI) incluyen un panel
para **generar un informe automático** con Google Gemini:

1. Elige el **estilo**: *científico* (detallado, técnico) o *ejecutivo* (resumen para
   decisión).
2. Pulsa **Generar informe**.
3. El informe se muestra en un modal; puedes **copiarlo** o **descargarlo** en Markdown.
4. Cada informe se **guarda en tu historial** personal para volver a consultarlo.

**Salvaguardas:** los prompts obligan al modelo a usar **solo los datos del análisis** (no
inventa genes, rutas ni números), a marcar la incertidumbre y a incluir la advertencia de que
el resultado es *in silico*.

> Requiere que el administrador haya configurado una **`GEMINI_API_KEY`**. Sin ella, la
> generación de informes devuelve un error 503 y el resto de la plataforma sigue funcionando
> con normalidad.

---

## 13. Administración de usuarios

Disponible **solo para administradores** (`/admin`):

- Listar, ver y gestionar cuentas de usuario.
- Restablecer la contraseña de un usuario.

El usuario administrador inicial se crea con el script de *seed* (`admin@druggraph.dev`).

---

## 14. Prerrequisitos de cada funcionalidad

Algunas funciones necesitan que el administrador cargue datos o instale componentes una sola
vez. Si un prerrequisito falta, esa sección aparece vacía o con un aviso, pero **el resto de
la plataforma sigue funcionando**.

| Funcionalidad | Necesita | ¿Internet? |
|---------------|----------|:---------:|
| Catálogo, búsqueda y ficha de fármacos | Datos de DrugBank cargados en MongoDB | No |
| Grafo de interacciones | Grafo poblado en Neo4j | No |
| Rutas (Pathways) | — | **Sí** (STRING, KEGG) |
| Bioactividad experimental | — | **Sí** (ChEMBL, PubChem) |
| Sandbox — similitud estructural | Script `populate_fingerprints.py` ejecutado | No |
| Sandbox — similitud por embedding (ChemBERTa) | `torch`+`transformers` + `populate_chemberta_embeddings.py` | No |
| Sandbox — sección CTD | Script `load_ctd_interactions.py` ejecutado | No |
| Sandbox — cascada (difusión) | Plugin GDS de Neo4j + `load_string_network.py` | No |
| Sandbox — cascada (dirigida/firmada) | `load_kegg_regulatory.py` (opcional: `load_omnipath_regulatory.py`) | No |
| BLAST | `ncbi-blast+` instalado + índice construido (`build_blast_db.py`) | No |
| Análisis de red (GDS): comunidades, predicción global | Plugin **GDS** de Neo4j (si falta → aviso 503) | No |
| Navegador de dianas (UniProt/SwissBioPics) | Dianas pobladas (`populate_targets.py`, `populate_uniprot.py`) | **Sí** para algunas imágenes |
| Proximidad de red | Red STRING cargada en Neo4j (`load_string_network.py`) | No |
| Evidencia diana→enfermedad | — | **Sí** (Open Targets) |
| Reversión de firma (LINCS) | — | **Sí** (LINCS L1000CDS2) |
| DEG / reposicionamiento (enriquecimiento GO) | — | **Sí** (g:Profiler) |
| Reportería IA | `GEMINI_API_KEY` configurada (si falta → 503) | **Sí** (Google Gemini) |

---

*DrugGraph — proyecto académico de Base de Datos Avanzada (2026). Resultados con fines de
investigación y exploración; no constituyen consejo clínico.*
