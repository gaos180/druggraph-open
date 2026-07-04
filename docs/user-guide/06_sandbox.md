# 06 — Laboratorio Virtual (Sandbox)

El Sandbox permite analizar un **compuesto químico hipotético** y compararlo con fármacos reales sin añadirlo a la base de datos permanentemente. El nodo temporal se elimina automáticamente al finalizar el análisis (o después de 30 minutos si usas `persist=true`).

Accede desde el Dashboard → **Laboratorio Virtual** o navega a `/sandbox`.

---

## Flujo de trabajo

```
1. Ingresar SMILES del compuesto
2. (Opcional) Importar targets desde SwissTargetPrediction o buscarlos manualmente
3. Hacer clic en "Analizar Compuesto"
4. Revisar propiedades fisicoquímicas y similitud con fármacos reales
5. (Opcional) Cargar rutas metabólicas y enriquecimiento GO de los targets
6. Navegar a los fármacos similares para mayor contexto
7. Exportar los resultados en CSV, JSON o HTML
```

---

## Paso 1: Ingresar el Compuesto

En el campo **SMILES**, introduce la representación SMILES del compuesto:

| Compuesto | SMILES |
|-----------|--------|
| Aspirina | `CC(=O)Oc1ccccc1C(=O)O` |
| Paracetamol | `CC(=O)Nc1ccc(O)cc1` |
| Ibuprofeno | `CC(C)Cc1ccc(cc1)C(C)C(=O)O` |
| Cafeína | `CN1C=NC2=C1C(=O)N(C(=O)N2C)C` |

Los botones de ejemplo debajo del campo rellenan el SMILES automáticamente para que puedas explorar sin escribirlo a mano.

---

## Paso 2: Importar Targets (SwissTargetPrediction)

La funcionalidad más potente del sandbox es la integración con **SwissTargetPrediction**, que predice automáticamente sobre qué proteínas podría actuar tu compuesto.

### Opción A — Importar CSV (recomendado)

1. Ve a [swisstargetprediction.ch](http://www.swisstargetprediction.ch).
2. Introduce el mismo SMILES de tu compuesto.
3. Selecciona el organismo (por defecto: *Homo sapiens*).
4. Descarga el resultado como **CSV** (botón de descarga de la tabla).
5. En el Sandbox de DrugGraph, haz clic en **🔮 SwissTargetPrediction**.
6. Selecciona el modo **📂 Importar CSV** y sube el archivo.

DrugGraph parseará el CSV, cruzará los targets predichos contra la base de datos Neo4j por UniProt ID o nombre de gen, y mostrará cuáles están disponibles (**"En DrugGraph"**).

### Opción B — API en línea

1. Haz clic en **🔮 SwissTargetPrediction**.
2. Selecciona el modo **🌐 API en línea**.
3. Elige el organismo en el desplegable.
4. Haz clic en **Predecir**.

El backend llamará directamente a SwissTargetPrediction. Requiere conexión a internet en el servidor. Si la API no responde, usa la Opción A.

### Interpretar el panel de predicciones

Cada fila del panel muestra:

| Campo | Descripción |
|-------|-------------|
| Barra de probabilidad | Verde ≥70%, amarillo ≥40%, naranja ≥20%, gris <20% |
| Nombre del gen | ej. `PTGS2`, `EGFR` |
| UniProt ID | Identificador en UniProt |
| Clase de target | ej. Oxidoreductase, GPCR, Kinase |
| Badge "En DrugGraph" | El target existe en la base de datos Neo4j (se puede usar en el análisis) |

**Filtros disponibles:**
- **Prob. mín.** — slider para ocultar predicciones con baja confianza.
- **Mostrar todos** — si está desmarcado, solo muestra los targets disponibles en DrugGraph.

Después de seleccionar los targets que te interesan, haz clic en **✓ Importar N targets al sandbox**. Se añaden como chips al campo de targets candidatos.

### Búsqueda manual de targets

También puedes buscar targets directamente en el campo de texto escribiendo al menos 2 caracteres del nombre de la proteína, gen o UniProt ID. El desplegable de autocompletado devuelve resultados desde Neo4j.

---

## Paso 3: Analizar

Haz clic en **🔬 Analizar Compuesto**. El sistema:

1. Valida el SMILES con RDKit.
2. Calcula propiedades fisicoquímicas (peso molecular, LogP, TPSA, etc.).
3. Crea un nodo temporal `:SandboxDrug` en Neo4j.
4. Calcula fingerprints Morgan/ECFP4 y compara con los de todos los fármacos reales.
5. Si hay targets candidatos, calcula similitud de comportamiento (Jaccard o GDS Node Similarity).
6. Devuelve un ranking combinado de fármacos similares.

> El análisis tarda entre 3–15 segundos según el tamaño de la base de datos.

---

## Interpretar los Resultados

### Tarjeta de propiedades

Muestra las reglas de Lipinski y propiedades ADME básicas del compuesto:

| Propiedad | Significado | Rango ideal (Lipinski) |
|-----------|-------------|------------------------|
| Peso Molecular | Masa en Dalton | ≤500 Da |
| LogP | Lipofilicidad | ≤5 |
| TPSA | Área superficial polar | ≤140 Å² |
| Donadores H | Grupos NH / OH | ≤5 |
| Aceptores H | Grupos N / O | ≤10 |
| Anillos aromáticos | Aromaticidad | – |

### Tarjetas de fármacos similares

| Barra | Color | Descripción |
|-------|-------|-------------|
| 🧬 Estructural | Azul | Similitud Tanimoto de fingerprints ECFP4 (0–1) |
| 🎯 Comportamiento | Violeta | Jaccard de targets compartidos o GDS Node Similarity (0–1) |
| ⭐ Combinado | Verde | Promedio ponderado de las dos anteriores |

El indicador en la esquina superior derecha muestra qué método se usó:

| Método | Descripción |
|--------|-------------|
| **GDS Node Similarity** | Comparación por grafo con todos los targets del fármaco |
| **Jaccard** | Intersección/unión de los targets candidatos |
| **Solo estructural** | No se proporcionaron targets candidatos |
| **Sin coincidencias** | No se encontró similitud suficiente |

---

## Paso 4: Rutas Metabólicas y Enriquecimiento GO (lazy-load)

Tras visualizar los resultados del análisis, aparece el botón **"Cargar rutas metabólicas"**. Esta sección es opcional y se carga bajo demanda porque puede tardar entre 30 y 90 segundos (llamadas a STRING y KEGG con rate-limiting).

### ¿Qué se calcula?

El sistema toma los targets de los fármacos similares encontrados en el análisis y consulta:

| Fuente | Datos |
|--------|-------|
| **KEGG REST** | Rutas metabólicas directas de los targets (ej. "Arachidonic acid metabolism") |
| **STRING enrichment** | Términos GO Process, GO Function, GO Component, KEGG enriquecido, Reactome, WikiPathways — todos con FDR real (Benjamini-Hochberg) |
| **STRING PPI** | Vecinos proteicos indirectos con scores de interacción |

> **Límite**: se usan como máximo 30 targets y 10 drug_ids por llamada. Si el análisis produce más, se truncan y se indica en la sección "Notas".

### Sub-secciones de resultados

#### Rutas KEGG

Tabla con las rutas en las que participan los targets. Columnas:

| Campo | Descripción |
|-------|-------------|
| ID de ruta | Identificador KEGG (ej. `hsa00590`) |
| Nombre | Nombre de la ruta (ej. "Arachidonic acid metabolism") |
| Targets | Número de targets en esa ruta |
| Genes | Símbolos HGNC de los targets involucrados |

#### Enriquecimiento GO / Reactome / WikiPathways

Tabla de términos funcionales ordenados por FDR ascendente. Columnas:

| Campo | Descripción |
|-------|-------------|
| Término | ID y descripción (ej. `GO:0006631 — Fatty acid metabolic process`) |
| Genes | Número de genes del conjunto en ese término |
| FDR | Tasa de falsos positivos corregida (valores bajos = más significativo) |
| Genes implicados | Lista de símbolos HGNC |

Tabs disponibles: **GO:BP** (proceso biológico), **GO:MF** (función molecular), **GO:CC** (componente celular), **KEGG**, **Reactome**, **WikiPathways**.

#### Red PPI

Vecinos proteicos de los targets directos, obtenidos de la red STRING. Columnas:

| Campo | Descripción |
|-------|-------------|
| Proteína vecina | Nombre y símbolo de la proteína |
| Score máximo | Confianza de la interacción (0–1; umbral mínimo: 0.4) |
| Conectada a | Targets directos con los que interactúa |

#### Interacciones químico-gen (CTD)

Proveniente de la [Comparative Toxicogenomics Database](https://ctdbase.org), esta sub-sección muestra, con **evidencia curada de literatura**, qué químicos afectan a los genes diana y de qué forma. Es una consulta rápida a MongoDB (no llama a APIs externas).

Se presenta en dos niveles:

| Nivel | Contenido |
|-------|-----------|
| **Químicos que afectan al perfil** | Tabla de los químicos que interactúan con el mayor número de genes diana (columnas: Químico, Genes diana afectados, Interacciones totales, enlace a DrugGraph si el químico es un fármaco conocido por CAS). Permite descubrir otros compuestos que afectan el mismo perfil molecular. |
| **Detalle por gen** | Por cada gen diana: nº de químicos y de interacciones, desglose de **acciones** (`↑ increases^expression`, `↓ decreases^activity`…) y sus top químicos. |

> Los datos de CTD se cargan una sola vez con `python load_ctd_interactions.py` (descarga `CTD_chem_gene_ixns.csv.gz`, filtra a humano + genes presentes en Neo4j y los agrega por gen en la colección `ctd_gene_interactions`). Si no se han cargado, la sección indica "datos no cargados".

Exportable en CSV (resumen de químicos y detalle por gen) y JSON.

### Visualización de red molecular

Encima de las tablas se renderiza un **grafo interactivo** (Cytoscape.js, el mismo componente que el Análisis de Red global) que contextualiza el efecto del compuesto. Tiene dos vistas conmutables:

| Vista | Nodos | Aristas |
|-------|-------|---------|
| **🎯 Efecto (directo/indirecto)** | Compuesto sandbox (violeta), targets directos (azul), vecinos PPI (ámbar) | Continua: el compuesto **afecta** al target. Punteada: el target **posiblemente afecta** al vecino PPI (efecto indirecto vía STRING) |
| **🗺️ Rutas asociadas** | Rutas KEGG (verde, tamaño ∝ nº de targets), proteínas diana (azul) | Gen → ruta en la que participa |

Sobre el grafo, un **panel de contexto** resume cuatro métricas de red:

- 🎯 **Proteínas que afecta** — número de targets directos.
- 🔗 **Proteínas que posiblemente afecta** — número de vecinos PPI indirectos (STRING).
- 🗺️ **Rutas KEGG asociadas** — total de rutas mapeadas.
- **Proceso biológico predominante** — el término GO:BP de menor FDR.

El grafo es arrastrable, admite zoom y clic derecho sobre un nodo (copiar, abrir en UniProt/STRING). El botón **⬇ PNG** de la esquina superior derecha exporta la imagen en alta resolución (escala ×2).

> **Interpretación**: para un inhibidor COX (targets PTGS1/PTGS2), la vista de efecto muestra el compuesto unido a las dos ciclooxigenasas y a sus ~25 vecinos PPI; la vista de rutas concentra esos targets en "Arachidonic acid metabolism", y el proceso GO predominante es "Cyclooxygenase pathway" — coherente con su mecanismo antiinflamatorio.

---

## Cascada de efectos (propagación en cadena)

Propaga la perturbación del compuesto desde sus genes diana por la red molecular, para ver el **efecto aguas abajo**. Tiene **dos modos** conmutables (cada botón lanza ese modo):

| Modo | Red | Qué responde | Salida |
|------|-----|--------------|--------|
| **🧭 Dirigida (signo)** | KEGG `:REGULATES` (dirigida, con signo) | ¿Qué genes downstream quedan **activados ↑ o inhibidos ↓**? | Sentido por gen (verde activa / rojo inhibe) + magnitud |
| **🌊 Difusión (magnitud)** | STRING `:STRING_ASSOC` (no dirigida) | ¿Hasta dónde y con qué **fuerza** llega el efecto? | Score de alcance (Personalized PageRank) |

Ambos son rápidos (~1–5 s) porque las redes están **cargadas localmente** en Neo4j (no se llama a APIs en cada salto, lo que sería inviable). Cada fila lleva un badge **diana DG** si el gen downstream es una diana conocida en DrugGraph — candidato a efecto secundario o co-modulación. Exportable en CSV.

### Modo dirigido (signo y dirección)

Construido desde los KGML de las rutas humanas de KEGG (`load_kegg_regulatory.py`), que aportan relaciones dirigidas gen→gen con signo (activación/expresión = +1, inhibición/represión = −1). La propagación difunde el signo en K saltos asumiendo que el compuesto **inhibe** sus dianas, y predice por cada gen downstream si la cadena lo **activa ↑** o lo **inhibe ↓**.

En el modo dirigido se dibuja además un **grafo de la cascada** (Cytoscape, layout jerárquico top-down) con signo y dirección:

| Elemento | Codificación |
|----------|--------------|
| Nodo morado | Diana semilla |
| Nodo verde / rojo | Gen downstream **activado ↑** / **inhibido ↓** (estado predicho) |
| Arista verde con flecha (→) | Relación de **activación** (KEGG) |
| Arista roja con barra-T (⊣) | Relación de **inhibición** (KEGG) |

Ojo: la **arista** indica el tipo de relación regulatoria; el **color del nodo** es el estado neto predicho tras propagar desde dianas inhibidas (por eso una flecha de activación verde puede llegar a un nodo rojo: si su activador queda inhibido, él también). El grafo se exporta como PNG.

> **Interpretación**: para un inhibidor de **EGFR**, la cascada dirigida predice MAPK1/MAPK3 (ERK), SRC, HIF1A **inhibidos ↓** — el apagado esperado de la vía MAPK. Para un anti-**TNF**, IL1B/IL6/NF-κB/NOS2 **inhibidos ↓**.

> **Naturaleza del cálculo**: es **generación de hipótesis** mecanísticas (como IPA/Pathway Studio), no verdad absoluta; la fiabilidad cae con cada salto. El modo difusión, en cambio, da magnitud sin signo.

Requisitos: plugin **Neo4j GDS** + `python load_string_network.py` (difusión) y `python load_kegg_regulatory.py` (dirigido). Si una red no está cargada, ese modo lo indica.

---

## Exportaciones del Sandbox

Todos los resultados del sandbox son exportables. Los botones de exportación aparecen en la esquina superior de cada sección.

### Exportaciones del análisis principal

| Formato | Contenido | Botón |
|---------|-----------|-------|
| **CSV** | Tabla de similitud (DrugBank ID, nombre, score estructural, score comportamiento, score combinado) | "Exportar CSV" |
| **JSON** | Documento completo con propiedades fisicoquímicas, listas de similitud y método usado | "Exportar JSON" |
| **HTML** | Informe imprimible con propiedades, tabla de similares y metadatos. Si previamente se cargaron las rutas, el informe incluye además el contexto de red (qué afecta / posiblemente afecta), rutas KEGG, GO:BP, GO:MF, Reactome y WikiPathways | "📄 Reporte" |

### Exportaciones de rutas (por sub-sección)

Una vez cargadas las rutas, cada sub-sección dispone de su propio botón de exportación:

| Sub-sección | CSV | JSON completo |
|-------------|-----|---------------|
| KEGG | Lista de rutas con targets | Sí (junto con todas las subsecciones) |
| GO Process / Function / Component | Términos enriquecidos con FDR | Sí |
| Reactome | Términos enriquecidos con FDR | Sí |
| WikiPathways | Términos enriquecidos con FDR | Sí |
| PPI | Lista de vecinos proteicos | Sí |

El botón **"Exportar todo (JSON)"** descarga la respuesta completa del endpoint `/api/drugs/sandbox/pathways/` en un único archivo.

### Exportar grafos Cytoscape como PNG

El grafo de red molecular del sandbox (vista de efecto y vista de rutas) dispone de un botón **⬇ PNG** en la esquina superior derecha. La imagen se exporta a resolución ×2 (doble resolución para impresión). Cada vista genera su propio archivo (`red_efecto_<compuesto>.png`, `red_rutas_<compuesto>.png`).

---

## Limpieza del Sandbox

El nodo temporal en Neo4j se elimina automáticamente al finalizar el análisis o tras 30 minutos. Para eliminarlo manualmente:

```bash
DELETE /api/drugs/sandbox/<sandbox_id>/
Authorization: Bearer <token>
```

---

## Ejemplo completo (API)

```bash
# Analizar el ibuprofeno con targets predichos por SwissTargetPrediction
curl -X POST http://localhost:8000/api/drugs/sandbox/analyze/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "smiles":     "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
    "name":       "Ibuprofeno-like",
    "target_ids": ["BE0000262", "BE0000017"]
  }'
```

```bash
# Importar predicciones de SwissTargetPrediction desde CSV
curl -X POST http://localhost:8000/api/drugs/sandbox/swiss-targets/ \
  -H "Authorization: Bearer <token>" \
  -F "file=@SwissTargetPrediction_ibuprofen.csv"

# Respuesta: { "total": 100, "matched": 91, "results": [...] }
```

```bash
# Predecir en tiempo real (llama a swisstargetprediction.ch)
curl "http://localhost:8000/api/drugs/sandbox/swiss-targets/?smiles=CC(C)Cc1ccc(cc1)C(C)C(=O)O&organism=Homo+sapiens" \
  -H "Authorization: Bearer <token>"
```

---

## Limitaciones

- **RDKit requerido** para similitud estructural (Tanimoto). Sin él, solo funciona similitud de comportamiento.
- **Fingerprints previos** requeridos: ejecuta `python populate_fingerprints.py` una vez para calcular los fingerprints de todos los fármacos en Neo4j.
- **Conexión a internet** para el modo "API en línea" de SwissTargetPrediction. Sin ella, usa la importación CSV.
- **Targets disponibles**: solo los targets con `uniprot_id` o `gene_name` en Neo4j pueden cruzarse con las predicciones de SwissTargetPrediction.
