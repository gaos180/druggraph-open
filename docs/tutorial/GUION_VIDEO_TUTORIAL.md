# Guion de Vídeo Tutorial — DrugGraph

> **Formato:** screencast (grabación de pantalla) + narración en off.
> **Idioma:** español neutro.
> **Duración total estimada:** ~32 minutos.
> **Público objetivo:** investigadores/as en farmacología, estudiantes de bioquímica/bioinformática, y equipos de descubrimiento de fármacos que quieran explorar relaciones fármaco–diana sin escribir código.

En este documento, cada segmento está enmarcado en una **historia de uso** (una persona con un objetivo real). Cada escena indica:

- **EN PANTALLA** → las acciones concretas que hace quien graba (clics, texto que se escribe, dónde va el ratón).
- **NARRACIÓN** → el texto exacto, palabra por palabra, que dice el presentador.

Los DrugBank ID y SMILES usados como ejemplo existen en la base de datos del proyecto (ver *Notas de producción* al final).

---

## Tabla de contenidos (timestamps aproximados)

| Timestamp | Segmento | Funcionalidad |
|-----------|----------|---------------|
| 00:00 | **Escena 1** — Introducción | Gancho y presentación |
| 01:15 | **Escena 2** — «Crear la cuenta del laboratorio» | Registro / Login |
| 03:00 | **Escena 3** — «El panel de control» | Dashboard y estadísticas |
| 04:15 | **Escena 4** — «Encontrar un fármaco» | Búsqueda y listado |
| 06:15 | **Escena 5** — «La ficha completa» | Detalle del fármaco (todas las secciones) |
| 09:30 | **Escena 6** — «¿Sobre qué actúa?» | Grafo de interacciones (Cytoscape) |
| 11:30 | **Escena 7** — «Del blanco a la biología» | Pathways (STRING + KEGG) |
| 13:30 | **Escena 8** — «Mi molécula experimental» | Sandbox: similitud molecular |
| 17:00 | **Escena 9** — «El efecto en cadena» | Cascada de efectos (difusión y dirigida) |
| 19:30 | **Escena 10** — «Evidencia química curada» | Enriquecimiento CTD |
| 20:45 | **Escena 11** — «Solo tengo una secuencia» | BLAST |
| 23:00 | **Escena 12** — «Leer la red completa» | Análisis GDS (centralidad, comunidades, predicción) |
| 26:00 | **Escena 13** — «Un viejo fármaco, un uso nuevo» | Reposicionamiento |
| 27:45 | **Escena 14** — «¿Es seguro?» | Toxicidad y off-targets |
| 29:15 | **Escena 15** — «De un experimento a un candidato» | Análisis DEG + reversión LINCS |
| 30:45 | **Escena 16** — «¿Se pueden combinar?» | Verificador DDI + riesgo PK/PD + proximidad |
| 32:00 | **Escena 17** — «Que la IA lo explique» | Reportería IA con Gemini |
| 33:15 | **Escena 18** — Cierre | Recapitulación y despedida |

---

## Escena 1 — Introducción

**Duración estimada:** 1 min 15 s

**EN PANTALLA:**
- Plano del logo/landing de DrugGraph (`/`, la `LandingPage`).
- Transición rápida (montaje de 3–4 segundos) que muestra por encima: el grafo de Cytoscape girando, una tabla de fármacos, y un informe de IA abriéndose en un modal.
- Volver a la landing en reposo.

**NARRACIÓN:**
> «Imagina que pudieras tomar cualquier fármaco, ver exactamente sobre qué proteínas actúa, seguir el rastro de sus efectos a través de la biología de la célula, comparar tu propia molécula experimental contra miles de compuestos conocidos… y que una inteligencia artificial te redactara el informe. Todo eso, sin escribir una sola línea de código.
>
> Esto es **DrugGraph**: una plataforma que conecta tres mundos de datos —las fichas farmacológicas de DrugBank, el grafo de interacciones moleculares en Neo4j, y APIs científicas como STRING, KEGG y ChEMBL— en una sola interfaz.
>
> En los próximos minutos vamos a recorrerla de la mano de investigadores con problemas reales. Verás cómo buscar y explorar fármacos, analizar redes moleculares, evaluar toxicidad, proponer nuevos usos para medicamentos existentes, y mucho más. Empecemos.»

---

## Escena 2 — «Crear la cuenta del laboratorio»

**Persona:** *Dr. Andrés Rivas, coordinador de un laboratorio de farmacología, abre DrugGraph por primera vez para su equipo.*

**Duración estimada:** 1 min 45 s

**EN PANTALLA:**
- En la landing, clic en el botón de acceso / «Iniciar sesión». Aparece `/login`.
- Clic en el enlace inferior «¿No tienes cuenta? Regístrate» → navega a `/register`.
- En el formulario de registro, escribir:
  - Nombre: `Andrés Rivas`
  - Email: `andres@lab-farma.edu`
  - Contraseña: `demo1234`
  - Confirmar contraseña: `demo1234`
- Clic en **«Registrarse»**. La app inicia sesión y redirige a `/dashboard`.
- Cerrar sesión desde la barra de navegación para mostrar el flujo de login.
- Volver a `/login`, escribir email `andres@lab-farma.edu` y contraseña `demo1234`, clic en **«Iniciar sesión»**.

**NARRACIÓN:**
> «Andrés coordina un laboratorio y quiere que su equipo empiece a usar DrugGraph. Lo primero es crear una cuenta.
>
> En la pantalla de acceso pulsa "Regístrate". El formulario pide nombre, un correo institucional y una contraseña de al menos seis caracteres. Las cuentas viven en MongoDB, y la sesión se gestiona con un token JWT, así que todo el trabajo que hagamos —los informes que generemos, por ejemplo— quedará asociado a este usuario.
>
> Al registrarse, la plataforma ya lo deja dentro, en el panel de control. Si más tarde vuelve, solo necesita su correo y contraseña para iniciar sesión.
>
> Un detalle práctico: DrugGraph avisa cuando la sesión está a punto de expirar, con una notificación en la esquina, para que nunca pierdas el trabajo en curso.»

---

## Escena 3 — «El panel de control»

**Persona:** *Andrés, ya dentro, quiere entender de un vistazo qué contiene la plataforma.*

**Duración estimada:** 1 min 15 s

**EN PANTALLA:**
- Vista del `DashboardPage`. Recorrer con el ratón la sección **«Estadísticas de la base de datos»**: las tarjetas grandes (fármacos en MongoDB, nodos `:Drug` en Neo4j, proteínas diana, categorías, registros DDI).
- Señalar los tres paneles inferiores: distribución por grupo (approved, investigational…), relación Drug→Target, y top de fármacos por número de dianas.
- Bajar a la rejilla de tarjetas de navegación (Análisis de Red, Base de Datos de Fármacos, Laboratorio Virtual, Búsqueda por Secuencia, Navegador de Dianas, Comparador de Dianas, Herramientas Analíticas, Ayuda).

**NARRACIÓN:**
> «Este es el panel principal. Antes de tocar nada, DrugGraph nos muestra la magnitud de sus datos: cuántos fármacos hay cargados en MongoDB, cuántos nodos de fármaco y de proteína diana viven en el grafo de Neo4j, cuántas categorías, y cuántas interacciones fármaco-fármaco registradas.
>
> Los gráficos de barras nos dicen, por ejemplo, cuántos fármacos están aprobados frente a los que están en investigación, y qué fármacos actúan sobre más dianas. Es una radiografía instantánea de la base de datos.
>
> Y debajo, las tarjetas de acceso rápido: cada una es una herramienta que vamos a explorar. Empecemos por la más básica y a la vez más usada: encontrar un fármaco.»

---

## Escena 4 — «Encontrar un fármaco»

**Persona:** *Camila, estudiante de bioquímica, tiene que preparar una ficha sobre la aspirina para un seminario.*

**Duración estimada:** 2 min

**EN PANTALLA:**
- Clic en la tarjeta **«Base de Datos de Fármacos»** → `/drugs`.
- En el buscador (placeholder «Nombre, sinónimo o SMILES…»), escribir `aspirin`. Mostrar cómo aparecen resultados a medida que se escribe (type-ahead).
- Mostrar la lista de resultados con nombre, DrugBank ID, tipo y grupos.
- Usar el desplegable **«Todos los tipos»** → seleccionar `small molecule`.
- Usar el desplegable **«Todos los grupos»** → seleccionar `approved`.
- Escribir en el campo **«Filtrar por diana/gen…»** algo como `COX` o `PTGS1` para mostrar el filtro por diana.
- Usar los botones de paginación (siguiente/anterior).
- Clic en el botón para exportar la búsqueda a CSV.
- Finalmente, clic en el resultado **Aspirin** para abrir su ficha.

**NARRACIÓN:**
> «Camila necesita la ficha de la aspirina. Entra a la base de datos de fármacos y empieza a escribir "aspirin" en el buscador. Fíjate en que los resultados aparecen mientras escribe: por debajo, DrugGraph primero prueba un índice de texto exacto en MongoDB, que responde en milisegundos, y si no hay coincidencia exacta cae a una búsqueda por subcadena, sinónimos y prefijos. Por eso funciona tan bien como autocompletado.
>
> Puede afinar con los filtros: mostrar solo moléculas pequeñas, solo fármacos aprobados, o incluso filtrar por la diana o el gen sobre el que actúan, por ejemplo la ciclooxigenasa. La lista se pagina de forma eficiente, sin contar todos los documentos, y en cualquier momento puede exportar los resultados a CSV para su informe.
>
> Cuando encuentra la aspirina, hace clic sobre ella… y entramos en la ficha completa.»

---

## Escena 5 — «La ficha completa»

**Persona:** *Camila explora todas las pestañas de la ficha de la aspirina.*

**Duración estimada:** 3 min 15 s

**EN PANTALLA:**
- Estamos en `/drugs/DB00945` (Aspirin). Mostrar la cabecera con nombre, DrugBank ID, grupos.
- Recorrer las pestañas superiores una por una, deteniéndose unos segundos en cada una:
  1. **Farmacología** (general): descripción, mecanismo de acción, farmacodinamia, absorción, metabolismo, vida media, eliminación, aclaramiento, volumen de distribución.
  2. **Química**: fórmula, peso molecular, SMILES, InChI.
  3. **Clínica**: indicaciones, toxicidad, precauciones.
  4. **Dianas y Enzimas**: lista de proteínas diana, enzimas, transportadores.
  5. **Red Molecular** (se detalla en la Escena 6 — solo mencionarla aquí).
  6. **Rutas y Efectos** (se detalla en la Escena 7 — solo mencionarla aquí).
  7. **Bioactividad**: datos de ChEMBL/PubChem (potencias, ensayos).
  8. **Genómica**: información farmacogenómica.
  9. **Costos y Mercado**: precios, productos, patentes.
  10. **Sinónimos y Refs**: nombres internacionales y referencias bibliográficas.

**NARRACIÓN:**
> «La ficha de un fármaco en DrugGraph está organizada en pestañas, cada una centrada en una faceta distinta del compuesto. Toda esta información proviene del documento completo de DrugBank almacenado en MongoDB.
>
> En "Farmacología" tenemos lo esencial: descripción, mecanismo de acción, farmacodinamia y toda la farmacocinética —absorción, metabolismo, vida media, aclaramiento—. Para la aspirina, aquí veríamos su papel como inhibidor de la ciclooxigenasa.
>
> La pestaña "Química" nos da la identidad molecular: la fórmula, el peso, el SMILES y el InChI, que son las huellas estructurales que luego usaremos en el laboratorio virtual.
>
> En "Clínica" están las indicaciones y las advertencias de seguridad; en "Dianas y Enzimas", el listado de proteínas sobre las que actúa y las enzimas que lo metabolizan.
>
> Las pestañas "Bioactividad", "Genómica" y "Costos y Mercado" enriquecen el retrato: datos de potencia de ensayos reales traídos de ChEMBL y PubChem, información farmacogenómica, y el lado comercial del fármaco. Y al final, sinónimos internacionales y referencias.
>
> Pero hay dos pestañas que merecen su propia historia, porque son las que convierten una ficha en un mapa: la Red Molecular y las Rutas y Efectos.»

---

## Escena 6 — «¿Sobre qué actúa?»

**Persona:** *Camila quiere ver, de forma visual, todas las proteínas que toca la aspirina.*

**Duración estimada:** 2 min

**EN PANTALLA:**
- Clic en la pestaña **«Red Molecular»** de la ficha (componente `GraphInteractionsSection`).
- Aparece el grafo de Cytoscape con el fármaco en el centro y sus dianas alrededor.
- Señalar la leyenda de colores (fármaco, target, tipos de relación) y filtrar por tipo de relación (target / enzyme / transporter / carrier).
- Usar el buscador de dianas dentro del grafo: escribir `PTGS` para resaltar/filtrar.
- Interactuar con el grafo: arrastrar un nodo, hacer zoom, clic en una diana para ver su tarjeta (`TargetCard`) con UniProt, gen, organismo y acciones.
- Mostrar la función de comparar/superponer con otro fármaco si está disponible (buscar un segundo fármaco).

**NARRACIÓN:**
> «Aquí es donde MongoDB cede el testigo a Neo4j. La pestaña "Red Molecular" consulta el grafo de interacciones y dibuja, con Cytoscape, a la aspirina en el centro rodeada de todas sus proteínas diana.
>
> Los colores distinguen el fármaco de sus dianas, y las aristas nos dicen el tipo de relación: si la proteína es una diana terapéutica, una enzima que lo metaboliza, un transportador o un portador. Podemos filtrar por esos tipos, o buscar una diana concreta —por ejemplo la ciclooxigenasa, PTGS— y resaltarla.
>
> El grafo es interactivo: arrastramos nodos, hacemos zoom, y al pulsar sobre una diana se abre su ficha, con su identificador UniProt, el gen, el organismo y la acción que el fármaco ejerce sobre ella. Incluso podemos superponer un segundo fármaco para ver, de un vistazo, qué dianas comparten. Esto es fundamental para entender por qué dos medicamentos podrían tener efectos parecidos.»

---

## Escena 7 — «Del blanco a la biología»

**Persona:** *Dr. Andrés vuelve para entender no solo las dianas de la aspirina, sino las rutas biológicas que afecta.*

**Duración estimada:** 2 min

**EN PANTALLA:**
- En la ficha de la aspirina, clic en la pestaña **«Rutas y Efectos»** (`PathwaysSection`).
- Mostrar el aviso «Consultando targets, STRING y KEGG… (puede tardar unos segundos)».
- Al cargar, recorrer las tres partes:
  1. **Efecto directo**: los targets del fármaco.
  2. Sub-pestaña **«🔗 Efecto indirecto (STRING)»**: lista de vecinos PPI de esos targets; mostrar la imagen de red oficial de STRING (`network_image_url`).
  3. Sub-pestaña **«🗺️ Rutas (KEGG)»**: vías biológicas de KEGG donde caen los targets, con enlaces a kegg.jp.
- Señalar los targets sin mapeo KEGG al final.

**NARRACIÓN:**
> «Andrés quiere ir un paso más allá de las dianas directas. La pestaña "Rutas y Efectos" combina en vivo tres fuentes: los targets del grafo, la red de interacciones proteína-proteína de STRING, y las vías biológicas de KEGG. Como consulta APIs externas en tiempo real, puede tardar unos segundos.
>
> Primero vemos el efecto directo: sobre qué proteínas actúa la aspirina. Luego, el efecto indirecto: STRING nos devuelve las proteínas que interactúan físicamente con esas dianas, es decir, el vecindario molecular que también se ve afectado aunque el fármaco no las toque directamente. Incluso podemos ver la imagen oficial de la red de STRING.
>
> Y finalmente, las rutas de KEGG: las vías metabólicas y de señalización donde participan estos targets, cada una enlazada a su mapa en kegg.jp. Así, de un solo fármaco, pasamos a entender el proceso biológico completo que está tocando.»

---

## Escena 8 — «Mi molécula experimental»

**Persona:** *María, química medicinal, ha diseñado un compuesto nuevo y quiere saber a qué se parece y sobre qué podría actuar antes de sintetizarlo.*

**Duración estimada:** 3 min 30 s

**EN PANTALLA:**
- Desde el dashboard, clic en **«Laboratorio Virtual»** → `/sandbox` (`SandboxPage`).
- En el campo **«Estructura SMILES»**, pegar el SMILES de la aspirina como demostración: `CC(=O)Oc1ccccc1C(=O)O` (o usar un botón de ejemplo).
- Escribir un nombre en el campo opcional: `Mi compuesto experimental`.
- (Opcional) Mostrar el panel de **SwissTargetPrediction** para importar dianas candidatas, o buscar manualmente una proteína en el buscador («Buscar proteína, gen o UniProt ID…»).
- Clic en **«🔬 Analizar Compuesto»**.
- Al cargar los resultados, recorrer:
  - Las tarjetas de **similitud estructural** (Tanimoto sobre fingerprints Morgan/ECFP4) y de **similitud de comportamiento** (Jaccard de proteínas compartidas): los fármacos más parecidos de la red.
  - El grafo de similitud generado.
  - El panel de **similitud por embedding (ChemBERTa)** (`EmbeddingSimilarityPanel`), mencionando que es una segunda vía de comparación por representación aprendida.
- Mencionar que el nodo `:SandboxDrug` es temporal (TTL ~30 min) y se elimina solo.

**NARRACIÓN:**
> «María es química medicinal. Ha diseñado una molécula y, antes de gastar tiempo y reactivos, quiere una intuición: ¿a qué fármacos conocidos se parece? ¿Sobre qué proteínas podría actuar?
>
> Entra al Laboratorio Virtual y pega la estructura en formato SMILES —aquí usamos la de la aspirina como ejemplo—. Le da un nombre a su compuesto. Opcionalmente puede añadir dianas conocidas a mano, o pedirle a SwissTargetPrediction que sugiera proteínas candidatas a partir de la estructura.
>
> Al pulsar "Analizar Compuesto", DrugGraph crea temporalmente un nodo en el grafo de Neo4j, calcula las huellas moleculares con RDKit, y compara la molécula contra toda la red por dos vías: la **similitud estructural**, mediante el coeficiente de Tanimoto sobre fingerprints de Morgan; y la **similitud de comportamiento**, con el índice de Jaccard sobre las proteínas que comparten.
>
> El resultado es un ranking de los fármacos más parecidos, y un grafo que lo visualiza. Además, el panel de embeddings ChemBERTa ofrece una tercera lente: una representación aprendida por un modelo de lenguaje químico, que a veces captura similitudes que la huella clásica no ve.
>
> Y algo elegante bajo el capó: ese nodo experimental es efímero. Vive unos treinta minutos y se borra solo, así que la red nunca se ensucia con compuestos de prueba.»

---

## Escena 9 — «El efecto en cadena»

**Persona:** *María quiere ir más allá de "a qué se parece" y preguntarse: si mi compuesto inhibe estas dianas, ¿qué se activa o se apaga aguas abajo?*

**Duración estimada:** 2 min 15 s

**EN PANTALLA:**
- Seguimos en la página del sandbox, con el compuesto ya analizado. Bajar a la sección **«🔗 Cascada de efectos (propagación)»**.
- Mostrar el toggle de modo con las dos opciones:
  - **Dirigida** (KEGG, con signo).
  - **Difusión** (STRING, sin signo).
- Clic en **«Dirigida»**: mostrar la cascada de N saltos, con genes marcados como `↑ activado` / `↓ inhibido`, el grafo con aristas verdes (activa) y rojas (inhibe), y los nodos coloreados por estado. Señalar los marcados como «diana DG» (dianas conocidas alcanzadas por la cascada → posibles efectos secundarios).
- Clic en **«Difusión»**: mostrar la magnitud del alcance (Personalized PageRank), con las barras de score por gen aguas abajo.
- Señalar la nota de que es una hipótesis mecanística in-silico.

**NARRACIÓN:**
> «Saber a qué se parece un compuesto está bien, pero María quiere razonar como una farmacóloga de sistemas: si mi molécula inhibe estas proteínas, ¿qué ocurre aguas abajo en la red?
>
> Para eso está la cascada de efectos, con dos modos complementarios. El modo **dirigido** usa las relaciones regulatorias con signo de KEGG: sabe qué proteína activa o inhibe a cuál. Propaga el efecto suponiendo que el fármaco inhibe sus dianas, y predice, gen por gen, si termina activado o inhibido. En el grafo, las aristas verdes son activaciones, las rojas inhibiciones, y el color del nodo es el estado final previsto. Los nodos marcados como "diana DG" son especialmente interesantes: son dianas conocidas de otros fármacos que nuestra cascada acaba tocando… candidatos a efectos secundarios.
>
> El modo **difusión** responde una pregunta distinta: no el signo, sino el alcance. Con un PageRank personalizado sobre la red de STRING, mide qué tan lejos y con qué intensidad se propaga la perturbación. Las barras nos muestran la magnitud del efecto en cada gen.
>
> Ambos son hipótesis mecanísticas in-silico, no verdades absolutas, pero son un punto de partida potentísimo para decidir qué experimentar.»

---

## Escena 10 — «Evidencia química curada»

**Persona:** *María contrasta las predicciones anteriores con evidencia experimental curada.*

**Duración estimada:** 1 min 15 s

**EN PANTALLA:**
- Dentro del análisis del sandbox, tras pulsar **«🔬 Analizar rutas y GO»**, mostrar la sección que incluye el enriquecimiento y el bloque de **CTD** (`CtdSection`): «🧪 interacciones químico-gen (CTD)» y el «Proceso biológico predominante».
- Si el dataset CTD no está cargado, señalar el mensaje «no cargado» como indicación de prerrequisito.

**NARRACIÓN:**
> «Las predicciones de red son hipótesis; conviene contrastarlas con evidencia real. Aquí entra CTD, la Comparative Toxicogenomics Database: un conjunto de interacciones químico-gen curadas manualmente a partir de la literatura.
>
> DrugGraph cruza las dianas de nuestro compuesto con estas interacciones curadas y nos muestra el proceso biológico predominante y las relaciones químico-gen documentadas. Es la diferencia entre "el modelo sugiere" y "la literatura ha observado". Si ves un aviso de que CTD no está cargado, significa que hace falta ejecutar una vez el script de carga de datos, que veremos en las notas de producción.»

---

## Escena 11 — «Solo tengo una secuencia»

**Persona:** *Dr. Luis, microbiólogo, ha secuenciado una proteína de una bacteria resistente y no sabe qué es ni qué fármacos podrían afectarla.*

**Duración estimada:** 2 min 15 s

**EN PANTALLA:**
- Desde el dashboard, clic en **«Búsqueda por Secuencia»** → `/blast` (`BlastSearchPage`).
- En el área de texto, pegar una secuencia FASTA de aminoácidos (usar la secuencia de ejemplo incluida, `>ejemplo_PBP2a_MRSA`).
- Ajustar los parámetros: **E-value** (`1e-3`), **identidad mínima**, y opcionalmente el **filtro por organismo**.
- Clic en **«Buscar»**.
- Recorrer las **tarjetas de resultados** (`HitCard`): nombre de la proteína homóloga, identificador de target, enlace a UniProt, gen, organismo, y las métricas del alineamiento (identidad %, E-value, bitscore, longitud, rango de query).
- Señalar los **chips de fármacos** que actúan sobre cada target, y hacer clic en uno para saltar a su ficha.

**NARRACIÓN:**
> «Luis tiene el problema inverso al de todos los anteriores: no parte de un fármaco, sino de una secuencia de aminoácidos de una proteína desconocida de una bacteria resistente.
>
> La herramienta de Búsqueda por Secuencia usa BLAST —el estándar de la bioinformática— contra un índice de proteínas diana pre-construido. Pega la secuencia en formato FASTA, ajusta el E-value para controlar la significancia estadística, opcionalmente filtra por organismo, y busca.
>
> DrugGraph le devuelve las proteínas homólogas ordenadas por similitud, cada una con su porcentaje de identidad, el E-value, el bitscore y el alineamiento. Pero lo verdaderamente útil está debajo de cada resultado: los fármacos que ya actúan sobre esa proteína homóloga. Con un clic, Luis salta a la ficha de un fármaco que podría ser un punto de partida contra su bacteria. Ha convertido una secuencia cruda en una hipótesis terapéutica.»

---

## Escena 12 — «Leer la red completa»

**Persona:** *Dr. Andrés quiere una visión global: ¿qué dianas son las más "promiscuas"? ¿Hay familias de fármacos? ¿Qué interacciones fármaco-diana aún no están documentadas pero la red predice?*

**Duración estimada:** 3 min

**EN PANTALLA:**
- Desde el dashboard, clic en **«Análisis de Red»** → `/network` (`NetworkAnalysisPage`).
- **Pestaña «Centralidad»** (`CentralityPanel`):
  - Alternar el tipo de nodo entre **🎯 Dianas** y **💊 Fármacos**.
  - Alternar la métrica entre **Grado** y **PageRank**.
  - Clic en **«Calcular»** y mostrar el ranking; usar el buscador para localizar una diana/fármaco concreto.
- **Pestaña «Comunidades»** (`CommunitiesPanel`):
  - Mostrar los módulos detectados por **Louvain**; buscar un fármaco dentro de las comunidades; mostrar el grafo por comunidad.
- **Pestaña «Predicción de Enlaces»** (`PredictionPanel`):
  - Buscar un fármaco por nombre o escribir un DrugBank ID directo (ej. `DB00945`).
  - Ejecutar la predicción con **Adamic-Adar**; mostrar las sugerencias de nuevas dianas con su score y el grafo; exportar a CSV.
- Mencionar que estas vistas requieren el plugin GDS de Neo4j y que devuelven 503 con mensaje claro si no está instalado.

**NARRACIÓN:**
> «Hasta ahora hemos mirado fármacos uno a uno. Andrés quiere leer la red completa, y para eso DrugGraph usa Graph Data Science, el motor de analítica de grafos de Neo4j.
>
> En "Centralidad" puede preguntar quiénes son los nodos más conectados. Una diana con grado muy alto es una proteína promiscua, sobre la que actúan muchos fármacos: una fuente potencial de efectos off-target. Un fármaco con grado alto actúa sobre muchas dianas. Puede alternar entre grado simple y PageRank, que pondera también la importancia de los vecinos.
>
> En "Comunidades", el algoritmo de Louvain detecta módulos: grupos de fármacos y dianas densamente interconectados. Suelen corresponder a familias terapéuticas o a sistemas biológicos, y es una forma preciosa de descubrir estructura oculta.
>
> Y la joya: "Predicción de Enlaces". Introduce un fármaco, y con el índice de Adamic-Adar la plataforma sugiere dianas sobre las que probablemente actúa, aunque no estén documentadas, basándose en la topología de la red. Es reposicionamiento in-silico puro, y puede exportarse a CSV.
>
> Todo esto necesita el plugin GDS de Neo4j; si no está instalado, la app lo indica con un mensaje claro en vez de romperse.»

---

## Escena 13 — «Un viejo fármaco, un uso nuevo»

**Persona:** *María quiere proponer nuevos usos para un fármaco aprobado, buscando otros con perfil de dianas similar.*

**Duración estimada:** 1 min 45 s

**EN PANTALLA:**
- Desde el dashboard, clic en **«Herramientas Analíticas»** → `/tools`, y luego en **Reposicionamiento** (`RepurposingTool`).
- En **«DrugBank ID de referencia»**, escribir `DB00945` (Aspirina). Ajustar **«Jaccard mínimo»** (ej. `0.1`).
- Clic en **«Buscar candidatos»**.
- Recorrer las tres pestañas de resultados:
  - **Candidatos**: tabla con Jaccard, nº de genes comunes, tamaños de los conjuntos de dianas; expandir una fila para ver los genes en común.
  - **GO perfil**: gráfico de enriquecimiento GO/KEGG de los targets (`GoEnrichmentChart`).
  - **Enfermedades (Open Targets)**: al pulsarla, carga enfermedades asociadas al módulo de dianas con su score (0–1) y los genes que las soportan; enlaces a platform.opentargets.org.
- Exportar los candidatos a CSV.

**NARRACIÓN:**
> «Reposicionar fármacos —encontrar nuevos usos para medicamentos ya aprobados— es una de las estrategias más rentables en el descubrimiento de fármacos, y María quiere una lista de candidatos.
>
> En la herramienta de Reposicionamiento introduce el DrugBank ID de la aspirina y un umbral de similitud. DrugGraph calcula el índice de Jaccard entre el conjunto de dianas de la aspirina y el de cada otro fármaco: cuantas más dianas compartan, más probable es que tengan efectos —y por tanto usos— parecidos.
>
> Obtiene una tabla de candidatos ordenada por similitud; al expandir cada fila ve exactamente qué genes comparten. La pestaña de perfil GO le muestra qué procesos biológicos y rutas KEGG están enriquecidos en esas dianas. Y la pestaña de Open Targets da el salto clínico: qué enfermedades están asociadas a ese módulo de proteínas, con un score de evidencia. Cada hipótesis diana-enfermedad es una posible nueva indicación, exportable a CSV para el informe.»

---

## Escena 14 — «¿Es seguro?»

**Persona:** *Dr. Andrés evalúa el perfil de riesgo de un fármaco antes de proponerlo para un estudio.*

**Duración estimada:** 1 min 30 s

**EN PANTALLA:**
- En `/tools`, clic en **Toxicidad** (`ToxicityTool`).
- En **«DrugBank ID»**, escribir `DB00734` (Risperidona) — o usar los ejemplos que sugiere la propia herramienta (DB00945, DB00563, DB01050, DB00734).
- Clic en **«Analizar toxicidad»**.
- Mostrar el **medidor de riesgo** (score /10 y nivel) y los contadores de alertas Alto/Medio/Bajo.
- Recorrer las pestañas:
  - **Alertas**: anti-targets conocidos (hERG, CYPs, receptores de dopamina); clic para expandir la explicación.
  - **CYPs**: interacciones con enzimas CYP450 y su implicación metabólica.
  - **Off-targets**: proteínas predichas por similitud topológica (Adamic-Adar), resaltando los anti-targets conocidos.
  - **Cluster**: fármacos estructuralmente similares (Jaccard ≥ 0.15) que podrían compartir toxicidad.
- Exportar a JSON/CSV.

**NARRACIÓN:**
> «Antes de proponer un fármaco para un estudio, Andrés quiere una lectura rápida de su seguridad. La herramienta de Toxicidad analiza —tomemos la risperidona— y devuelve un score de riesgo de cero a diez, con alertas clasificadas por severidad.
>
> Las "Alertas" señalan anti-targets conocidos: por ejemplo el canal hERG, cuya inhibición se asocia a arritmias, o receptores de dopamina. Cada una se despliega con su explicación. La pestaña "CYPs" detalla las interacciones con las enzimas del citocromo P450, que determinan el metabolismo y el riesgo de interacciones.
>
> Los "Off-targets" son proteínas sobre las que el fármaco probablemente actúa aunque no esté documentado, predichas por la topología de la red, con los anti-targets peligrosos resaltados. Y el "Cluster" muestra fármacos estructuralmente parecidos, que podrían arrastrar toxicidades similares. Todo exportable para adjuntar al dossier de seguridad.»

---

## Escena 15 — «De un experimento a un candidato»

**Persona:** *Dra. Sofía tiene resultados de un experimento de RNA-seq y quiere conectarlos con un fármaco y buscar compuestos que reviertan la firma.*

**Duración estimada:** 1 min 30 s

**EN PANTALLA:**
- En `/tools`, clic en **DEG Analysis** (`DegAnalysisTool`).
- **Cargar archivo** de genes (CSV/TSV con columnas gene, log2fc, pvalue, padj) mediante la zona de arrastre/clic.
- Escribir el **DrugBank ID** (`DB00945`), elegir **organismo** (`Homo sapiens`), ajustar **umbral |log₂FC|**, **umbral p/FDR**, el estadístico (p-valor crudo vs FDR), la corrección múltiple, y las **fuentes GO** (GO:BP, GO:MF, GO:CC, KEGG, REAC).
- Clic en **«Analizar»**.
- Recorrer las pestañas: **Volcano Plot** (`VolcanoPlot`), **Intersección** (genes DEG que son targets del fármaco), **GO** (enriquecimiento), **Genes**, y **Reversión (LINCS)**.
- En la pestaña **Reversión**, mostrar la tabla de fármacos cuyo perfil transcriptómico L1000 revierte la firma (Connectivity Map / L1000CDS2), con score, línea celular y dosis.

**NARRACIÓN:**
> «Sofía llega con datos propios: una lista de genes diferencialmente expresados de un experimento de RNA-seq. Quiere dos cosas: ver si su fármaco de interés actúa sobre esos genes, y encontrar compuestos que reviertan el patrón de enfermedad.
>
> Sube su archivo de genes —con log2 fold-change y p-valores— elige el organismo, fija los umbrales de significancia y las fuentes de enriquecimiento. Al analizar, DrugGraph dibuja un volcano plot interactivo, calcula qué genes significativos son además dianas del fármaco —la intersección— y hace el análisis de enriquecimiento GO y KEGG.
>
> Y lo más potente: la pestaña de Reversión. Construye una firma con los genes que suben y bajan, y consulta LINCS L1000, el mapa de conectividad, para encontrar fármacos cuyo perfil transcriptómico hace lo contrario a la enfermedad. Un score alto significa mejor reversión: candidatos de reposicionamiento salidos directamente de sus propios datos.»

---

## Escena 16 — «¿Se pueden combinar?»

**Persona:** *Dr. Andrés revisa la combinación de dos fármacos para un paciente polimedicado.*

**Duración estimada:** 1 min 15 s

**EN PANTALLA:**
- En `/tools`, clic en **DDI** (`DdiCheckerPage`).
- Modo **«Verificar par A ↔ B»**: escribir `DB00945` (Aspirina) y `DB00788` (o el segundo ejemplo que ofrezca el placeholder). Clic en **«Verificar interacción»**.
- Mostrar el resultado (interacción detectada / sin interacción) con la descripción documentada.
- Pulsar **«Estimar riesgo»** en la tarjeta **«Riesgo de interacción predicho (PK/PD)»**: mostrar el score /10, el nivel, y las señales PK (CYP compartido) y PD (dianas/rutas comunes).
- Pulsar **«Calcular proximidad»** en la tarjeta **«Proximidad de red (interactoma)»**: mostrar la distancia d_c entre los módulos de dianas en STRING.
- Cambiar a modo **«Todas las DDIs de un fármaco»**: escribir `DB00945`, buscar, y mostrar la tabla filtrable y exportable a CSV.

**NARRACIÓN:**
> «Un paciente toma varios medicamentos. Andrés necesita saber si dos de ellos interactúan. En modo par, introduce los dos DrugBank ID y DrugGraph consulta las interacciones documentadas en el grafo, mostrando la descripción clínica cuando existe.
>
> Pero va más allá de lo documentado. La tarjeta de "Riesgo predicho" hace una estimación mecanística in-silico: busca señales farmacocinéticas —comparten alguna enzima CYP que competirá por el metabolismo— y farmacodinámicas —comparten dianas o rutas—. Y la "Proximidad de red" mide, con la métrica d_c de la medicina de redes, qué tan cerca están los módulos de dianas de ambos fármacos en el interactoma de STRING: cuanto más cerca, más probable que se influyan.
>
> Si en cambio quiere el panorama completo de un solo fármaco, el segundo modo lista todas sus interacciones conocidas, filtrables y exportables. Insisto: la predicción no sustituye una base clínica, pero levanta banderas que merecen atención.»

---

## Escena 17 — «Que la IA lo explique»

**Persona:** *Todas las personas anteriores quieren convertir cualquier análisis en un informe legible, sin redactarlo a mano.*

**Duración estimada:** 1 min 15 s

**EN PANTALLA:**
- En cualquiera de los análisis anteriores (por ejemplo, el resultado de Toxicidad o del Sandbox), bajar hasta el panel **«Informe con IA»** (`ReportPanel`).
- Elegir el **estilo**: **Científico** (técnico) o **Ejecutivo** (divulgativo).
- Clic en **«Generar informe»**. Mostrar el estado de carga y luego el **modal** con el informe en Markdown (`MarkdownView`).
- Señalar la cabecera del informe (estilo, modelo Gemini usado, fecha) y los botones **Copiar** y **Descargar Markdown**.
- Cerrar el modal y volver a abrirlo con **«Ver último informe»**.
- Mencionar que cada informe queda guardado en el historial del usuario.

**NARRACIÓN:**
> «Cada análisis que hemos visto termina con el mismo botón: "Informe con IA". Es la capa transversal de DrugGraph. Con un clic, envía los datos del análisis —solo los datos, recortados— al modelo Gemini de Google, que redacta una interpretación en lenguaje natural.
>
> Puedes elegir el tono: un informe científico, técnico, para un investigador; o uno ejecutivo, divulgativo, para presentar a alguien no especialista. El informe se abre en un modal, formateado, y puedes copiarlo o descargarlo en Markdown.
>
> Dos cosas importantes: el sistema está diseñado con instrucciones anti-alucinación estrictas —usa solo el JSON del análisis, no inventa genes, rutas ni cifras, y marca siempre que es una hipótesis in-silico—. Y cada informe queda guardado en tu historial personal, asociado a tu cuenta. Necesita una clave de Gemini configurada en el servidor; si no la hay, la app lo avisa con claridad.»

---

## Escena 18 — Cierre

**Duración estimada:** 1 min

**EN PANTALLA:**
- Montaje rápido que recorre las herramientas vistas (dashboard → ficha → grafo → sandbox → red → tools → informe IA).
- Volver al dashboard en reposo.
- Tarjeta final con el nombre del proyecto y, opcionalmente, el enlace al repositorio o a la página de ayuda (`/help`).

**NARRACIÓN:**
> «Y con esto cerramos el recorrido. Hemos pasado de buscar un fármaco a leer la red molecular completa; de una molécula dibujada en un papel a un ranking de candidatos; de una secuencia cruda a una hipótesis terapéutica; y de datos crudos a informes redactados por IA.
>
> DrugGraph reúne tres bases de datos —MongoDB, Neo4j y las APIs científicas— bajo una interfaz pensada para que investigadores, estudiantes y equipos de descubrimiento razonen sobre fármacos de forma visual y rigurosa.
>
> Recuerda que muchas de estas funciones son hipótesis in-silico: un punto de partida para el laboratorio, no un sustituto de la evidencia experimental. Si quieres profundizar, la sección de Ayuda tiene guías paso a paso y la referencia de la API.
>
> Gracias por acompañarnos. Nos vemos en el laboratorio.»

---

## Notas de producción

### Datos de ejemplo recomendados (existen en la base del proyecto)

| Fármaco | DrugBank ID | Uso en el vídeo |
|---------|-------------|-----------------|
| Aspirin (Aspirina) | `DB00945` | Fármaco protagonista: ficha, grafo, rutas, reposicionamiento, DEG, DDI |
| Ibuprofen (Ibuprofeno) | `DB01050` | Ejemplo de toxicidad / comparación |
| Methotrexate (Metotrexato) | `DB00563` | Ejemplo de toxicidad |
| Risperidone (Risperidona) | `DB00734` | Toxicidad (anti-targets de dopamina, buen caso de alertas) |
| Segundo fármaco para DDI | `DB00788` (u otro que el placeholder sugiera) | Verificación de par A ↔ B |

- **SMILES de la aspirina** para el sandbox: `CC(=O)Oc1ccccc1C(=O)O` (coincide con el placeholder de la página).
- **Secuencia FASTA para BLAST:** usar la secuencia de ejemplo ya incluida en la página (`>ejemplo_PBP2a_MRSA`), o cualquier proteína diana conocida.
- **Archivo DEG:** preparar un CSV/TSV pequeño con columnas `gene, log2fc, pvalue, padj` (unas 200–500 filas) para que el volcano plot y la reversión LINCS tengan datos suficientes.
- Verificar los ID contra la base real antes de grabar (los nombres se muestran en la lista `/drugs`); si alguno no estuviera cargado, sustituir por uno equivalente presente en la lista.

### Qué tener corriendo antes de grabar

1. **Bases de datos:** `docker compose up -d` (MongoDB en 27017, Neo4j en 7474/7687).
2. **Backend:** `cd backend && source venv/bin/activate && python manage.py runserver` (puerto 8000).
   - Sembrar admin la primera vez: `python scripts/seed_admin.py` (crea `admin@druggraph.dev` / `admin1234`).
   - Asegurar índices de MongoDB: `python scripts/ensure_indexes.py`.
3. **Frontend:** `cd frontend && npm install && npm start` (puerto 3000).

### Prerrequisitos por funcionalidad (ejecutar una sola vez; sin ellos la sección muestra aviso o error controlado)

| Escena / Feature | Prerrequisito |
|------------------|---------------|
| Sandbox — similitud estructural (Tanimoto) | `rdkit` instalado + `scripts/populate_fingerprints.py` |
| Sandbox — similitud por embedding (ChemBERTa) | `pip install torch transformers` + `scripts/populate_chemberta_embeddings.py` (índice vectorial `drug_chemberta`) |
| Sandbox — enriquecimiento CTD (Escena 10) | `scripts/load_ctd_interactions.py` |
| Cascada — modo **difusión** (Escena 9) | Plugin GDS de Neo4j + `scripts/load_string_network.py` |
| Cascada — modo **dirigido/con signo** (Escena 9) | `scripts/load_kegg_regulatory.py` (opcional, más rico: `scripts/load_omnipath_regulatory.py`) |
| BLAST (Escena 11) | `ncbi-blast+` instalado + índice con `scripts/build_blast_db.py` (variables `BLAST_DB_PATH` / `BLAST_MAP_PATH`) |
| Análisis GDS — comunidades y predicción (Escena 12) | Plugin **GDS** de Neo4j instalado (si falta, la app devuelve 503 con mensaje claro) |
| Rutas/Pathways, Bioactividad, Enfermedades (Open Targets), Proximidad, Reversión LINCS | Acceso a internet (STRING, KEGG, ChEMBL/PubChem, Open Targets, LINCS L1000CDS2; sin clave). La proximidad requiere además la red STRING cargada en Neo4j |
| Reportería IA (Escena 17) | Variable `GEMINI_API_KEY` configurada en el backend (sin ella, `/api/reports/` responde 503). Modelo por defecto `gemini-2.5-flash` |

> **Recomendación:** hacer un ensayo completo (dry-run) con todos los prerrequisitos ya cargados antes de grabar, para evitar avisos de "no disponible" o esperas largas en pantalla. Las llamadas a STRING/KEGG/LINCS pueden tardar varios segundos; conviene tener respuestas cacheadas realizando cada consulta una vez antes de la toma final.

### Ritmo, resolución y estilo

- **Resolución:** grabar a **1920×1080 (1080p)** mínimo; 2560×1440 si la pantalla lo permite (la interfaz "cuaderno" luce bien con nitidez). Exportar a 1080p/30 fps.
- **Zoom del navegador:** 100–110 % para que el texto de tablas y grafos sea legible en el vídeo.
- **Ratón:** activar resaltado del cursor y de los clics; moverse despacio, sin saltos bruscos.
- **Ritmo:** dejar 1–2 segundos de "respiración" después de cada clic importante antes de narrar el resultado; no adelantar la narración a la acción en pantalla.
- **Audio:** narración limpia, sin música de fondo dominante (opcional una pista suave a bajo volumen). Guion leído con tono didáctico y calmado.
- **Cortes:** cortar los tiempos de espera largos de las APIs externas (STRING/KEGG/LINCS/Gemini) con un corte limpio o un ligero acelerado, manteniendo visible el estado de "cargando" un instante para que se entienda que es una consulta en vivo.
- **Continuidad de datos:** usar el mismo fármaco protagonista (Aspirina, `DB00945`) a lo largo de varias escenas refuerza el hilo narrativo y ayuda a la comprensión.
- **Subtítulos:** por accesibilidad, generar subtítulos en español a partir del guion (ya está redactado palabra por palabra).

---

### Resumen de cobertura del guion

Segmentos con historia de uso: **16** (escenas 2 a 17), más introducción (1) y cierre (18) = **18 escenas**.

Funcionalidades cubiertas: registro/login, dashboard con estadísticas, búsqueda y listado de fármacos (con filtros y exportación), ficha de detalle completa (Farmacología, Química, Clínica, Dianas y Enzimas, Bioactividad, Genómica, Costos y Mercado, Sinónimos/Refs), grafo de interacciones con Cytoscape, rutas y efectos (STRING + KEGG), sandbox de similitud molecular (Tanimoto, Jaccard, SwissTargetPrediction, embeddings ChemBERTa), cascada de efectos (difusión y dirigida/con signo), enriquecimiento CTD, BLAST, análisis GDS (centralidad, comunidades Louvain, predicción de enlaces), reposicionamiento (Jaccard + GO + Open Targets), toxicidad y off-targets, análisis DEG con volcano y reversión LINCS, verificador DDI con riesgo PK/PD y proximidad de red, y la reportería IA transversal con Gemini.
