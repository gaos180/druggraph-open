# 12 — Glosario

## Términos del Dominio

| Término | Definición |
|---------|-----------|
| **DrugBank** | Base de datos bioinformática que combina información química, farmacológica y bioquímica sobre fármacos y sus targets proteicos. DrugGraph usa el dataset de DrugBank como fuente de datos. |
| **CTD (Comparative Toxicogenomics Database)** | Base de datos de toxicogenómica (ctdbase.org) con interacciones químico-gen curadas de literatura. DrugGraph carga el archivo `CTD_chem_gene_ixns.csv.gz` (filtrado a humano + genes presentes en Neo4j) en MongoDB (colección `ctd_gene_interactions`) para enriquecer el sandbox: para cada gen diana indica qué químicos lo afectan y cómo. |
| **InteractionActions (CTD)** | Campo estructurado de CTD que describe el tipo de interacción químico-gen como `acción^objeto`, p.ej. `increases^expression`, `decreases^activity`, `affects^binding`. Varias acciones se separan por `\|`. |
| **STRING (red local)** | Además del cliente API, DrugGraph carga la red PPI humana de STRING en bloque (`9606.protein.links`, score ≥ 700) en Neo4j como `(:Gene)-[:STRING_ASSOC {score}]->(:Gene)` para poder propagar efectos en cadena sin depender de la API. |
| **Propagación / efecto en cadena** | Difusión de la perturbación de un fármaco desde sus dianas por la red PPI, para estimar qué genes aguas abajo se ven alcanzados. En DrugGraph se calcula con **Personalized PageRank** (GDS) sembrado en los targets. Da magnitud (no dirigida, sin signo); el signo activación/inhibición requeriría fuentes dirigidas (KEGG KGML, Reactome, CTD). |
| **Personalized PageRank** | Variante de PageRank con nodos semilla (`sourceNodes`): el "salto aleatorio" reinicia en las semillas en vez de en cualquier nodo, midiendo cercanía/alcance respecto a ellas. Base del modo de propagación por **difusión** (magnitud). |
| **KGML** | KEGG Markup Language: representación XML de una ruta KEGG. Sus `<relation>` codifican interacciones dirigidas entre genes con `<subtype>` (`activation`, `inhibition`, `expression`, `repression`…). DrugGraph las convierte en aristas `:REGULATES` con signo. |
| **REGULATES (red dirigida con signo)** | Aristas `(:Gene)-[:REGULATES {sign:+1/-1}]->(:Gene)` derivadas de KGML: +1 activación/expresión, −1 inhibición/represión. Sustrato del modo de cascada **dirigido**, que propaga el sentido (↑ activado / ↓ inhibido) aguas abajo. |
| **Cascada dirigida (propagación con signo)** | Difusión en K pasos sobre `:REGULATES`: el efecto de cada nodo se transmite a sus sucesores multiplicado por el signo de la arista y atenuado por salto. Predice si cada gen downstream queda activado o inhibido, asumiendo que el fármaco inhibe sus dianas. |
| **Fármaco (Drug)** | Compuesto químico con actividad biológica. En DrugGraph corresponde a un documento MongoDB y un nodo `:Drug` en Neo4j, identificado por `drugbank_id` (ej. `DB01050`). |
| **Target** | Proteína (generalmente enzima, receptor o transportador) con la que un fármaco interactúa para producir su efecto. Nodo `:Target` en Neo4j. |
| **Polipéptido (Polypeptide)** | Secuencia de aminoácidos que define una proteína target. Nodo `:Polypeptide` en Neo4j; contiene `gene_name`, `uniprot_id`, `sequence`. |
| **Categoría (Category)** | Clasificación farmacológica de un fármaco (ej. "Antiinflamatorios", "Inhibidores de COX"). Nodo `:Category` en Neo4j. |
| **Interacción Drug-Drug (DDI)** | Relación entre dos fármacos que indica que un fármaco afecta al otro. Arista `:INTERACTS_WITH` en Neo4j. Verificable a través del DDI Checker (`/tools/ddi`). |
| **DEG** | Differentially Expressed Gene. Gen cuya expresión cambia significativamente entre dos condiciones experimentales (tratado vs. control). Se caracteriza por su log₂ Fold-Change y p-valor. |
| **log₂FC (log₂ Fold-Change)** | Logaritmo en base 2 del cociente de expresión entre condición tratada y control. Valores positivos indican up-regulation; negativos, down-regulation. Un umbral típico es \|log₂FC\| ≥ 1 (equivale a 2× de cambio). |
| **FDR (False Discovery Rate)** | Tasa de falsos positivos esperada entre los resultados significativos. Se controla ajustando los p-valores (ej. Benjamini-Hochberg). En DrugGraph se usa como alternativa al p-valor crudo para clasificar genes DEG. |
| **ORA (Over-Representation Analysis)** | Análisis estadístico que evalúa si una lista de genes está sobre-representada en un conjunto funcional (término GO, pathway KEGG). DrugGraph usa g:Profiler para ORA. |
| **g:Profiler** | Plataforma web y API para análisis de enriquecimiento funcional. DrugGraph llama a su endpoint `gost/profile/` para calcular GO, KEGG y REAC sobre genes DEG o targets de fármacos. Acepta métodos de corrección: `g_SCS`, `bonferroni`, `analytical`. |
| **Volcano Plot** | Gráfico de dispersión con log₂FC en eje X y -log₁₀(p-valor) en eje Y. Permite identificar visualmente genes significativos y diferencialmente expresados. Los puntos rojos (up) o azules (down) superan los umbrales; los naranja son además targets del fármaco. |
| **Anti-target** | Proteína cuya activación o inhibición por un fármaco produce efectos adversos no deseados. Ejemplos: KCNH2 (cardiotoxicidad por QT prolongado), DRD2 (efectos extrapiramidales). DrugGraph evalúa 27 anti-targets con niveles alto/medio/bajo. |
| **Off-target** | Proteína con la que un fármaco interactúa sin que sea su diana terapéutica prevista. Puede ser la causa de efectos secundarios. En DrugGraph se predicen usando el algoritmo Adamic-Adar sobre el grafo Neo4j. |
| **Adamic-Adar** | Algoritmo de predicción de enlaces. Asigna una puntuación a cada par de nodos no conectados basándose en el número de vecinos comunes (con penalización logarítmica por nodos de alto grado). DrugGraph lo usa para predecir off-targets en Neo4j. |
| **CYP (Citocromo P450)** | Superfamilia de enzimas hepáticas responsables del metabolismo de la mayoría de los fármacos. Las isoformas principales (CYP3A4, CYP2D6, CYP2C9, CYP2C19, CYP1A2, CYP2B6) son críticas para identificar posibles interacciones farmacocinéticas. |
| **SMILES** | Simplified Molecular Input Line Entry System. Notación textual para describir la estructura química de una molécula (ej. `CC(=O)Oc1ccccc1C(=O)O` para ácido acetilsalicílico). |
| **Fingerprint molecular** | Representación binaria o vectorial de la estructura química de una molécula. DrugGraph usa Morgan/ECFP4 (RDKit) para calcular similitud Tanimoto. |
| **Tanimoto (similitud)** | Coeficiente de similitud entre dos fingerprints moleculares. Rango [0,1]; 1 = idénticos. Usado en el sandbox para encontrar fármacos estructuralmente similares. |
| **PPI** | Protein-Protein Interaction. Interacción física o funcional entre proteínas. STRING provee redes PPI para calcular el efecto indirecto de un fármaco. |
| **Efecto directo** | Proteínas que el fármaco toca directamente (sus targets registrados en DrugBank). |
| **Efecto indirecto** | Proteínas que interactúan con los targets directos del fármaco a través de la red PPI (STRING). El fármaco las afecta indirectamente. |
| **Ruta biológica (Pathway)** | Conjunto de reacciones moleculares que llevan a un efecto celular. KEGG provee un mapa de rutas donde se localizan los genes/proteínas. |
| **UniProt** | Base de datos de secuencias y funciones de proteínas. Cada proteína tiene un accession único (ej. `P00734`). Usado para mapear targets a KEGG. |
| **KEGG gene id** | Identificador de gen en KEGG (ej. `hsa:2147`). El prefijo indica el organismo (`hsa` = *Homo sapiens*). |
| **Reactome** | Base de datos de rutas biológicas curadas manualmente. DrugGraph la incluye como fuente de enriquecimiento vía STRING (categoría `RCTM`). |
| **WikiPathways** | Base de datos de rutas biológicas de edición colaborativa (similar a Wikipedia). Disponible como fuente de enriquecimiento vía STRING (categoría `WikiPathways`). |
| **GO Enrichment Analysis** | Análisis estadístico que evalúa si un conjunto de genes está sobre-representado en términos de Gene Ontology. A diferencia de la mera anotación funcional, el enriquecimiento calcula un p-valor y FDR comparando contra un fondo genómico. En DrugGraph se realiza vía STRING (endpoint `enrichment`) para el sandbox de pathways. |
| **FDR (en enriquecimiento STRING)** | Tasa de falsos positivos corregida (Benjamini-Hochberg) retornada por el endpoint `enrichment` de STRING. Valores `fdr=None` indican que se usó el endpoint incorrecto (`functional_annotation`); el endpoint correcto siempre devuelve FDR numérico. |
| **DDI Checker** | Herramienta de DrugGraph (`/tools/ddi`) que consulta la arista `:INTERACTS_WITH` en Neo4j para verificar interacciones entre dos fármacos (modo par) o listar todas las DDIs de un fármaco (modo lista). Exporta resultados en CSV. |
| **Lazy-load (carga diferida)** | Estrategia de UX que pospone una operación costosa hasta que el usuario la solicita explícitamente. En DrugGraph se aplica a las rutas sandbox: el análisis principal es rápido (< 15 s) y las rutas metabólicas se cargan en un segundo paso opcional (30–90 s). |
| **organism = 'Humans'** | Valor del campo `organism` en los nodos `:Target` de Neo4j para proteínas humanas, tal como fue importado desde DrugBank. No usar `'Homo sapiens'`; las queries Cypher deben filtrar con `t.organism = 'Humans' OR t.organism CONTAINS 'Homo sapiens'` para máxima cobertura. |

---

## Términos Técnicos

| Término | Definición |
|---------|-----------|
| **Cypher** | Lenguaje de query declarativo de Neo4j para grafos. Similar a SQL pero diseñado para patrones de grafo. |
| **GDS** | Graph Data Science plugin de Neo4j. Añade procedimientos para algoritmos de grafo (PageRank, Louvain, link prediction). |
| **Louvain** | Algoritmo de detección de comunidades en grafos. Agrupa nodos maximizando la modularidad. Usado en `gds/communities/`. |
| **PageRank** | Algoritmo que asigna importancia a un nodo según cuántos nodos importantes apuntan a él. Usado en `gds/centrality/`. |
| **Betweenness centrality** | Mide cuántos caminos mínimos entre pares de nodos pasan por un nodo dado. Identifica "puentes" en el grafo. |
| **Link prediction** | Predicción de aristas que probablemente existan pero no están registradas. GDS usa similitud de vecindad (Common Neighbors, Adamic-Adar). |
| **BLAST** | Basic Local Alignment Search Tool. Busca regiones de similitud entre secuencias biológicas. `blastp` compara secuencias de proteínas. |
| **JWT** | JSON Web Token. Token compacto y firmado que encapsula claims de identidad. DrugGraph usa HS256. |
| **SimpleUser** | Objeto Python ligero (`@dataclass`) en `users/authentication.py` que representa al usuario autenticado. No es un modelo Django ORM. |
| **Singleton** | Patrón de diseño que garantiza una única instancia de una clase. Usado para las conexiones a MongoDB y Neo4j. |
| **DRF** | Django REST Framework. Biblioteca que extiende Django con herramientas para construir APIs REST (serializers, viewsets, autenticación). |
| **Axios** | Cliente HTTP basado en Promises para JavaScript/TypeScript. Usado en el frontend con interceptores para JWT y manejo de 401. |
| **Cytoscape.js** | Biblioteca JavaScript para visualización y análisis de grafos en el navegador. Usada en `CytoscapeGraph.tsx`. |
| **RAF** | requestAnimationFrame. API del navegador para animaciones. El loop de layout de Cytoscape.js usa RAF; debe detenerse antes de destruir la instancia. |
| **ECFP4 / Morgan FP** | Extended Connectivity FingerPrint de radio 4. Variante de fingerprint molecular de 2048 bits generada por RDKit. Usado en sandbox (Tanimoto), toxicidad (cluster estructural) y reposicionamiento (Jaccard de fingerprints). |
| **TTL** | Time To Live. Tiempo máximo de vida de una entrada en caché. STRING: 6 h, KEGG: 24 h. |
| **N+1 pagination** | Estrategia de paginación que pide `N+1` documentos para detectar si hay página siguiente sin ejecutar un `count`. |
| **Bolt** | Protocolo binario eficiente de Neo4j para comunicación cliente-servidor. Puerto por defecto: 7687. |
