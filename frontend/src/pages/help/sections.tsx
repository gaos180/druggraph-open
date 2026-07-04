import React from 'react';
import { Section, H2, H3, P, Code, CodeBlock, Note, Table, Step, UIBtn } from './primitives';

export const SECTIONS: Section[] = [
  {
    id: 'start',
    icon: '🚀',
    title: 'Inicio rápido',
    content: (
      <>
        <H2>Inicio rápido</H2>
        <P>DrugGraph es una plataforma de información farmacológica que combina tres bases de datos simultáneamente: <strong style={{ color: '#1e293b' }}>MongoDB</strong> (documentos de fármacos), <strong style={{ color: '#1e293b' }}>Neo4j</strong> (grafo de interacciones moleculares) y APIs externas (STRING, KEGG, SwissTargetPrediction).</P>

        <H3>Acceder a la plataforma</H3>
        <Step n={1} title="Abrir el navegador">
          Navega a <Code>http://localhost:3000</Code>. Serás redirigido a la pantalla de login.
        </Step>
        <Step n={2} title="Crear una cuenta">
          Haz clic en <strong style={{ color: '#0369a1' }}>¿No tienes cuenta? Crea una aquí</strong> en la parte inferior del formulario de login.
        </Step>
        <Step n={3} title="Rellenar el formulario de registro">
          Introduce tu nombre completo, email y una contraseña de al menos 6 caracteres. Haz clic en <strong style={{ color: '#0369a1' }}>Registrarse</strong>.
        </Step>
        <Step n={4} title="Explorar el Dashboard">
          Tras el registro (o login) aterrizarás en el <strong style={{ color: '#0369a1' }}>Dashboard</strong>, que tiene accesos directos a todas las funcionalidades.
        </Step>

        <Note type="tip">
          Cuenta de prueba preconfigurada: <Code>admin@druggraph.dev</Code> / <Code>admin1234</Code>
        </Note>

        <H3>Navegación principal</H3>
        <Table
          headers={['Sección', 'Ruta', 'Qué hace']}
          rows={[
            ['💊 Fármacos', '/drugs', 'Busca, filtra y exporta los más de 16 000 fármacos de DrugBank'],
            ['🎯 Dianas', '/targets', 'Explora las proteínas diana en la red con datos de UniProt'],
            ['🧫 Laboratorio Virtual', '/sandbox', 'Analiza un compuesto hipotético con SMILES — similitud estructural, comportamental, rutas y GO'],
            ['🔬 Búsqueda BLAST', '/blast', 'Busca dianas por homología de secuencia de aminoácidos'],
            ['🕸️ Análisis de Red', '/network', 'Centralidad, comunidades y predicción de enlaces (GDS)'],
            ['🔧 Herramientas', '/tools', 'DEG, Reposicionamiento, Toxicidad, DDI Checker'],
            ['❓ Ayuda', '/help', 'Esta página'],
          ]}
        />

        <H3>Aviso de sesión</H3>
        <P>La sesión JWT expira en 24 horas. Cuando queden menos de 5 minutos aparecerá un aviso en la esquina inferior derecha. Al expirar, la app redirige automáticamente al login.</P>
      </>
    ),
  },

  {
    id: 'drugs',
    icon: '💊',
    title: 'Explorar fármacos',
    content: (
      <>
        <H2>Explorar fármacos</H2>
        <P>La página de fármacos (<Code>/drugs</Code>) permite buscar, filtrar y exportar los más de 16 000 compuestos importados desde DrugBank.</P>

        <H3>Buscar</H3>
        <P>El campo de búsqueda detecta automáticamente qué tipo de término introduces:</P>
        <Table
          headers={['Tipo de búsqueda', 'Ejemplo', 'Cómo funciona']}
          rows={[
            ['Nombre', 'Ibuprofen', 'Búsqueda insensible a mayúsculas en nombre y sinónimos'],
            ['DrugBank ID', 'DB01050', 'Búsqueda por prefijo exacto'],
            ['CAS', '15687-27-1', 'Número CAS exacto'],
            ['SMILES', 'CC(C)Cc1ccc(cc1)', 'Busca en la estructura química calculada'],
          ]}
        />
        <Note type="info">
          La búsqueda ocurre en tiempo real con debounce de 400 ms. Escribe al menos 2 caracteres.
        </Note>

        <H3>Búsqueda por diana</H3>
        <P>Activa el interruptor <UIBtn>🎯 Buscar por diana</UIBtn> para buscar todos los fármacos que actúan sobre una proteína específica. Escribe el nombre del gen (ej. <Code>PTGS2</Code>), UniProt ID o nombre de proteína en el campo secundario y aplica la búsqueda.</P>

        <H3>Filtros</H3>
        <P>Usa los desplegables de la barra de controles para combinar filtros:</P>
        <Table
          headers={['Filtro', 'Opciones']}
          rows={[
            ['Tipo', 'small molecule, biotech'],
            ['Grupo', 'approved, investigational, experimental, withdrawn, nutraceutical, illicit, vet_approved'],
          ]}
        />

        <H3>Exportar resultados</H3>
        <P>El botón <UIBtn color="#15803d">⬇ CSV</UIBtn> descarga la lista actual de resultados (no solo la página visible, sino todos los que caben en la respuesta del filtro activo). El archivo incluye:</P>
        <Table
          headers={['Modo', 'Columnas exportadas']}
          rows={[
            ['Normal', 'nombre, DrugBank ID, tipo, grupos'],
            ['Búsqueda por diana', 'nombre, ID, dianas coincidentes'],
          ]}
        />

        <H3>Perfil de fármaco</H3>
        <P>Haz clic en cualquier fármaco para ver su perfil completo. Las pestañas organizan la información:</P>
        <Table
          headers={['Pestaña', 'Contenido']}
          rows={[
            ['Química', 'SMILES, fórmula molecular, peso, propiedades fisicoquímicas'],
            ['Targets / Genomics', 'Genes, proteínas diana, SNPs'],
            ['Clínica', 'Indicaciones, mecanismo de acción, interacciones, dosificación'],
            ['Mercado', 'Productos comerciales, precios, fabricantes'],
            ['Grafo de interacciones', 'Red Neo4j: targets, categorías, interacciones fármaco-fármaco'],
            ['Rutas biológicas', 'Targets → STRING → KEGG (rutas metabólicas)'],
          ]}
        />
        <P>El botón <UIBtn color="#15803d">⬇ JSON</UIBtn> junto al nombre del fármaco descarga el documento completo de MongoDB como JSON.</P>
      </>
    ),
  },

  {
    id: 'targets',
    icon: '🎯',
    title: 'Dianas moleculares',
    content: (
      <>
        <H2>Dianas moleculares</H2>
        <P>La página <Code>/targets</Code> permite explorar las proteínas diana presentes en la red DrugGraph, con información de UniProt, genes y fármacos asociados.</P>

        <H3>Buscar dianas</H3>
        <P>Introduce en el campo de búsqueda el nombre de proteína, símbolo génico o UniProt ID (ej. <Code>PTGS2</Code>, <Code>P35354</Code>, <Code>Cyclooxygenase</Code>). La búsqueda tiene debounce de 350 ms.</P>

        <H3>Filtro por organismo</H3>
        <P>Activa la casilla <UIBtn>Solo humanos</UIBtn> para filtrar únicamente las proteínas con organismo <Code>Humans</Code> en DrugBank. Útil para reducir ruido en análisis clínicos.</P>

        <H3>Perfil de diana</H3>
        <P>Haz clic en cualquier fila para abrir el perfil completo (<Code>/targets/:id</Code>). Contiene:</P>
        <Table
          headers={['Sección', 'Contenido']}
          rows={[
            ['Identificadores', 'DrugBank target ID, UniProt ID, nombre del gen, organismo'],
            ['Descripción', 'Función de la proteína según DrugBank/UniProt'],
            ['Fármacos', 'Lista de fármacos que actúan sobre esta diana con su acción (inhibitor, inducer, agonist…)'],
            ['Secuencia', 'Secuencia de aminoácidos (si está disponible) con opción de copiar'],
            ['Estructura SwissBioPics', 'Imagen de localización subcelular (si hay UniProt ID válido)'],
          ]}
        />

        <Note type="info">
          Desde el perfil de diana puedes navegar directamente al perfil de cualquiera de sus fármacos asociados haciendo clic en el ID de fármaco.
        </Note>
      </>
    ),
  },

  {
    id: 'graph',
    icon: '🕸️',
    title: 'Grafo de interacciones',
    content: (
      <>
        <H2>Grafo de interacciones</H2>
        <P>Disponible en la pestaña <strong style={{ color: '#0369a1' }}>Grafo de interacciones</strong> del perfil de cualquier fármaco. Muestra la red de relaciones del fármaco en Neo4j.</P>

        <H3>Nodos y aristas</H3>
        <Table
          headers={['Elemento', 'Color', 'Significado']}
          rows={[
            ['Fármaco central', 'Azul cian', 'El fármaco seleccionado'],
            ['Targets', 'Verde', 'Proteínas diana directas'],
            ['Categorías', 'Violeta', 'Clasificaciones farmacológicas (ATC, etc.)'],
            ['Fármacos interactuantes', 'Naranja', 'Fármacos con interacciones conocidas'],
            ['Aristas Target', 'Cian claro', 'Relación TARGETS (con rol: inhibitor, inducer...)'],
            ['Aristas Categoría', 'Violeta claro', 'Relación BELONGS_TO'],
            ['Aristas DDI', 'Naranja claro', 'Interacción fármaco-fármaco (DDI)'],
          ]}
        />

        <H3>Interacción con el grafo</H3>
        <Table
          headers={['Acción', 'Efecto']}
          rows={[
            ['Clic en nodo', 'Muestra etiqueta con información del nodo'],
            ['Arrastrar nodo', 'Reposicionar en el espacio'],
            ['Scroll / Pellizco', 'Zoom in/out'],
            ['Arrastrar fondo', 'Paneo del canvas'],
            ['Doble clic en fármaco', 'Navega al perfil de ese fármaco'],
          ]}
        />

        <H3>Exportar como imagen PNG</H3>
        <P>El botón <UIBtn>⬇ PNG</UIBtn> en la esquina superior derecha del grafo descarga una captura de alta resolución (escala ×2) del grafo completo sobre fondo oscuro. Disponible en todas las vistas con grafo Cytoscape: perfil de fármaco, rutas biológicas y análisis de red.</P>

        <H3>Panel de estadísticas</H3>
        <P>Debajo del grafo aparece un resumen: número de targets, categorías e interacciones fármaco-fármaco para ese compuesto.</P>
      </>
    ),
  },

  {
    id: 'pathways',
    icon: '🧬',
    title: 'Rutas biológicas',
    content: (
      <>
        <H2>Rutas biológicas</H2>
        <P>La pestaña <strong style={{ color: '#0369a1' }}>Rutas biológicas</strong> del perfil de fármaco muestra el contexto sistémico del compuesto combinando tres fuentes:</P>

        <H3>Fuentes de datos</H3>
        <Table
          headers={['Fuente', 'Qué aporta']}
          rows={[
            ['Neo4j', 'Targets directos del fármaco (con UniProt ID y nombre de gen)'],
            ['STRING DB', 'Vecinos proteicos de los targets directos (red de interacción proteína-proteína)'],
            ['KEGG REST', 'Rutas metabólicas/de señalización que contienen esos genes'],
          ]}
        />

        <H3>Visualización</H3>
        <P>El grafo de rutas muestra nodos de tipo <strong style={{ color: '#0369a1' }}>Ruta</strong> conectados a los <strong style={{ color: '#15803d' }}>genes</strong> que participan en ellas. El tamaño de cada nodo de ruta es proporcional al número de targets del fármaco presentes en ella.</P>

        <Note type="info">
          El análisis se limita a los primeros 25 targets para no sobrecargar las APIs externas. Si el fármaco tiene más, se incluye una nota explicativa.
        </Note>

        <H3>Ejemplo de interpretación</H3>
        <P>Si el Ibuprofeno (DB01050) aparece en la ruta <Code>hsa00590 — Arachidonic acid metabolism</Code> con 8 targets, significa que 8 de sus proteínas diana directas (o sus vecinos STRING) participan en esa ruta metabólica.</P>
      </>
    ),
  },

  {
    id: 'sandbox',
    icon: '🧫',
    title: 'Laboratorio Virtual',
    content: (
      <>
        <H2>Laboratorio Virtual (Sandbox)</H2>
        <P>El Sandbox permite analizar un compuesto hipotético y compararlo con fármacos reales sin modificar la base de datos. Accede desde <Code>/sandbox</Code>.</P>

        <H3>Paso 1 — Ingresar el SMILES</H3>
        <P>Introduce la cadena SMILES de tu compuesto. Puedes usar los botones de ejemplo para cargar compuestos conocidos:</P>
        <Table
          headers={['Compuesto', 'SMILES']}
          rows={[
            ['Aspirina', 'CC(=O)Oc1ccccc1C(=O)O'],
            ['Ibuprofeno', 'CC(C)Cc1ccc(cc1)C(C)C(=O)O'],
            ['Paracetamol', 'CC(=O)Nc1ccc(O)cc1'],
            ['Cafeína', 'CN1C=NC2=C1C(=O)N(C(=O)N2C)C'],
          ]}
        />

        <H3>Paso 2 — Importar targets con SwissTargetPrediction</H3>
        <P>Para mejorar la comparación de comportamiento, puedes importar predicciones de targets desde SwissTargetPrediction. Haz clic en el botón <UIBtn color="#0284c7">🔮 SwissTargetPrediction</UIBtn>.</P>

        <Step n={1} title="Modo CSV (recomendado)">
          Ve a <Code>swisstargetprediction.ch</Code>, introduce el mismo SMILES, descarga el CSV y súbelo aquí con el botón <UIBtn>📂 Seleccionar CSV</UIBtn>.
        </Step>
        <Step n={2} title="Modo API en línea">
          Selecciona <UIBtn>🌐 API en línea</UIBtn>, elige el organismo y haz clic en <UIBtn>🔮 Predecir</UIBtn>. Requiere conexión a internet.
        </Step>
        <Step n={3} title="Seleccionar e importar">
          El panel muestra los targets predichos con barras de probabilidad. Los que existen en DrugGraph aparecen con el badge <span style={{ color: '#15803d', fontWeight: 600 }}>En DrugGraph</span>. Usa el filtro de probabilidad mínima y haz clic en <UIBtn>✓ Importar N targets</UIBtn>.
        </Step>

        <H3>Código de colores de probabilidad (SwissTargetPrediction)</H3>
        <Table
          headers={['Color', 'Rango', 'Significado']}
          rows={[
            [<span style={{ color: '#15803d' }}>Verde</span>, '≥ 70%', 'Alta confianza'],
            [<span style={{ color: '#92400e' }}>Amarillo</span>, '40–69%', 'Confianza media'],
            [<span style={{ color: '#9a3412' }}>Naranja</span>, '20–39%', 'Confianza baja'],
            [<span style={{ color: '#64748b' }}>Gris</span>, '< 20%', 'Muy baja confianza'],
          ]}
        />

        <H3>Paso 3 — Analizar e interpretar similitudes</H3>
        <P>Haz clic en <UIBtn color="#7c3aed">🔬 Analizar Compuesto</UIBtn>. Los resultados muestran la tabla <strong style={{ color: '#1e293b' }}>Fármacos más similares</strong> con tres métricas:</P>
        <Table
          headers={['Barra', 'Descripción']}
          rows={[
            ['🧬 Estructural (azul)', 'Similitud Tanimoto de fingerprints ECFP4 entre los fingerprints Morgan precalculados (0–100%)'],
            ['🎯 Comportamiento (violeta)', 'Jaccard de targets compartidos o GDS Node Similarity (0–100%)'],
            ['⭐ Combinado (verde)', 'Promedio ponderado de las dos anteriores'],
          ]}
        />

        <Note type="warning">
          La similitud estructural requiere que <Code>RDKit</Code> esté instalado y que se hayan precalculado los fingerprints con <Code>python populate_fingerprints.py</Code>.
        </Note>

        <H3>Paso 4 — Rutas Metabólicas y Procesos GO</H3>
        <P>Tras el análisis, aparece la sección <strong style={{ color: '#1e293b' }}>Rutas Metabólicas y Procesos GO</strong>. Haz clic en <UIBtn color="#0ea5e9">🗺️ Cargar Rutas y Enriquecimiento</UIBtn> para lanzar el análisis (puede tardar 30–90 s por el rate-limiting de las APIs externas).</P>

        <P>Este análisis combina los targets de los fármacos similares encontrados (hasta 10 fármacos, hasta 30 targets) y consulta:</P>
        <Table
          headers={['Fuente', 'Qué devuelve']}
          rows={[
            ['KEGG REST', 'Rutas metabólicas directas de los targets (lista con nº de targets por ruta)'],
            ['STRING Enrichment', 'Términos GO (Proceso Biológico, Función Molecular, Componente Celular), KEGG enriquecido, Reactome y WikiPathways con FDR corregido'],
            ['STRING PPI', 'Proteínas vecinas indirectas de los targets con sus scores de interacción'],
            ['CTD', 'Interacciones químico-gen curadas de literatura: qué químicos afectan a cada gen diana y cómo (↑/↓ expresión, actividad…)'],
          ]}
        />

        <P>Cada subsección tiene sus propias pestañas y se puede colapsar. Los términos GO están ordenados por FDR ascendente (más significativo primero).</P>

        <Note type="info">
          El análisis incluye solo targets humanos (<Code>organism = Humans</Code>). Los targets de otros organismos se omiten automáticamente.
        </Note>

        <H3>Visualización de red molecular</H3>
        <P>Encima de las tablas se dibuja un <strong style={{ color: '#1e293b' }}>grafo interactivo</strong> (Cytoscape) con dos vistas conmutables que contextualizan el efecto del compuesto:</P>
        <Table
          headers={['Vista', 'Qué muestra']}
          rows={[
            [<UIBtn>🎯 Efecto (directo/indirecto)</UIBtn>, 'El compuesto (violeta) en el centro, unido por línea continua a las proteínas que afecta directamente (azul) y por línea punteada a los vecinos PPI de STRING que posiblemente afecta de forma indirecta (ámbar)'],
            [<UIBtn>🗺️ Rutas asociadas</UIBtn>, 'Cada ruta KEGG (verde) conectada a las proteínas diana que participan en ella; el tamaño del nodo crece con el nº de targets implicados'],
          ]}
        />
        <P>Un panel de resumen indica de un vistazo cuántas proteínas <strong style={{ color: '#0369a1' }}>afecta</strong> (targets directos), cuántas <strong style={{ color: '#78350f' }}>posiblemente afecta</strong> (vecinos PPI), cuántas rutas KEGG están asociadas y cuál es el proceso biológico (GO) predominante. El botón <UIBtn color="#475569">⬇ PNG</UIBtn> de la esquina del grafo descarga la imagen en alta resolución.</P>

        <H3>Cascada de efectos (propagación)</H3>
        <P>Propaga la perturbación del compuesto desde sus dianas por la red molecular para ver el efecto <strong style={{ color: '#1e293b' }}>aguas abajo</strong>. Dos modos:</P>
        <Table
          headers={['Modo', 'Red', 'Qué muestra']}
          rows={[
            [<UIBtn color="#6d28d9">🧭 Dirigida (signo)</UIBtn>, 'KEGG (dirigida, con signo)', 'Si cada gen downstream queda activado ↑ (verde) o inhibido ↓ (rojo), asumiendo que el compuesto inhibe sus dianas'],
            [<UIBtn color="#0369a1">🌊 Difusión (magnitud)</UIBtn>, 'STRING (no dirigida)', 'Qué tan fuerte llega el efecto a cada gen (Personalized PageRank), sin signo'],
          ]}
        />
        <P>Los marcados <strong style={{ color: '#15803d' }}>diana DG</strong> son dianas conocidas en DrugGraph que la cascada alcanza — candidatos a efecto secundario o co-modulación.</P>
        <Note type="info">
          Para un inhibidor de EGFR, el modo dirigido predice MAPK1/MAPK3/SRC/HIF1A <strong style={{ color: '#fb7185' }}>inhibidos ↓</strong> (apagado de la vía MAPK). Es generación de hipótesis mecanísticas, no verdad absoluta. Requiere el plugin GDS + <Code>load_string_network.py</Code> (difusión) y <Code>load_kegg_regulatory.py</Code> (dirigido).
        </Note>

        <H3>Exportaciones del Sandbox</H3>
        <P>Junto al encabezado <strong style={{ color: '#1e293b' }}>Resultados Combinados</strong> aparecen tres botones:</P>
        <Table
          headers={['Botón', 'Formato', 'Contenido']}
          rows={[
            [<UIBtn color="#15803d">⬇ CSV</UIBtn>, 'CSV', 'Tabla de similitudes: nombre, DrugBank ID, score estructural, comportamental y combinado'],
            [<UIBtn color="#0284c7">⬇ JSON</UIBtn>, 'JSON', 'Respuesta completa del análisis incluyendo propiedades fisicoquímicas y todos los scores'],
            [<UIBtn color="#6d28d9">📄 Reporte</UIBtn>, 'HTML', 'Informe imprimible con propiedades del compuesto, tabla de similitudes y —si se cargaron las rutas— el contexto de red, rutas KEGG, GO, Reactome y WikiPathways'],
          ]}
        />
        <P>En las subsecciones de Rutas y GO, cada tabla tiene sus propios botones <UIBtn color="#15803d">⬇ CSV</UIBtn> y <UIBtn color="#0284c7">⬇ JSON</UIBtn> para exportar individualmente KEGG, GO, PPI, etc. El botón <UIBtn color="#0284c7">⬇ JSON completo</UIBtn> descarga todos los datos de rutas en un solo archivo.</P>
      </>
    ),
  },

  {
    id: 'tools',
    icon: '🔧',
    title: 'Herramientas analíticas',
    content: (
      <>
        <H2>Herramientas analíticas</H2>
        <P>La sección <Code>/tools</Code> agrupa cuatro herramientas de análisis avanzado que cruzan datos de la plataforma con información externa.</P>

        <H3>📊 Análisis DEG (Genes Diferencialmente Expresados)</H3>
        <P>Ruta: <Code>/tools/deg</Code></P>
        <P>Introduce un DrugBank ID y pega una lista de genes diferencialmente expresados (uno por línea o separados por comas). La herramienta:</P>
        <Table
          headers={['Paso', 'Qué hace']}
          rows={[
            ['Cruce', 'Compara los genes DEG con las dianas del fármaco en Neo4j'],
            ['Enriquecimiento GO', 'Consulta STRING para obtener términos GO enriquecidos en el set de genes comunes'],
            ['Visualización', 'Volcano plot interactivo y tabla de genes solapantes'],
            ['Exportación', 'CSV con genes solapantes, JSON con enriquecimiento GO completo'],
          ]}
        />

        <H3>🔄 Reposicionamiento de Fármacos</H3>
        <P>Ruta: <Code>/tools/repurposing</Code></P>
        <P>Introduce un DrugBank ID. La herramienta busca fármacos con perfiles de dianas similares usando el grafo Neo4j:</P>
        <Table
          headers={['Métrica', 'Descripción']}
          rows={[
            ['Jaccard de targets', 'Proporción de dianas compartidas sobre la unión de las dos listas'],
            ['Targets compartidos', 'Lista de genes comunes entre ambos fármacos'],
            ['Indicaciones', 'Indicaciones terapéuticas del fármaco candidato (si están en DrugBank)'],
          ]}
        />
        <Note type="tip">
          Útil para descubrir usos terapéuticos no conocidos. Un Jaccard alto ({'>'} 0.3) con un fármaco aprobado para otra indicación sugiere un candidato de reposicionamiento.
        </Note>

        <H3>⚠️ Evaluación de Toxicidad</H3>
        <P>Ruta: <Code>/tools/toxicity</Code></P>
        <P>Introduce un DrugBank ID. Evalúa tres dimensiones de riesgo toxicológico:</P>
        <Table
          headers={['Dimensión', 'Descripción']}
          rows={[
            ['Anti-targets', 'Coincidencia con dianas de riesgo conocidas: hERG (cardiotoxicidad), CYPs (metabolismo), receptores dopaminérgicos'],
            ['Off-targets predichos', 'Dianas a las que el fármaco se une en Neo4j fuera de su indicación principal'],
            ['Clúster estructural', 'Fármacos estructuralmente similares (Tanimoto) con alertas de toxicidad conocidas'],
          ]}
        />
        <P>El resultado incluye un <strong style={{ color: '#1e293b' }}>Risk Meter</strong> (0–10) con nivel de riesgo (bajo / moderado / alto / muy alto) y alertas individuales por anti-target. Exportable en CSV y JSON.</P>

        <H3>💊 DDI Checker (Interacciones Fármaco-Fármaco)</H3>
        <P>Ruta: <Code>/tools/ddi</Code></P>
        <P>Consulta las interacciones fármaco-fármaco registradas en el grafo Neo4j. Dos modos:</P>
        <Table
          headers={['Modo', 'Cómo usar']}
          rows={[
            ['Verificar par A ↔ B', 'Introduce dos DrugBank IDs (ej. DB01050 y DC1234) para comprobar si existe interacción conocida entre ellos y leer su descripción'],
            ['Todas las DDIs de un fármaco', 'Introduce un solo ID para listar todos los fármacos con los que interactúa. Buscable y exportable como CSV'],
          ]}
        />
        <Note type="warning">
          Las DDIs provienen de DrugBank y reflejan las interacciones documentadas hasta la fecha de importación de los datos. No sustituye una revisión farmacológica profesional.
        </Note>
      </>
    ),
  },

  {
    id: 'blast',
    icon: '🔬',
    title: 'Búsqueda BLAST',
    content: (
      <>
        <H2>Búsqueda por Secuencia (BLAST)</H2>
        <P>La búsqueda BLAST (<Code>/blast</Code>) permite encontrar proteínas diana homólogas a una secuencia de aminoácidos proporcionada. Devuelve las proteínas más similares y los fármacos que las afectan.</P>

        <H3>Cómo usar</H3>
        <Step n={1} title="Pegar la secuencia">
          Introduce una secuencia de aminoácidos en formato de una sola letra (ej. <Code>MNIFEMLRIDEGLRLK...</Code>). La longitud mínima recomendada es de 20 aminoácidos.
        </Step>
        <Step n={2} title="Ajustar parámetros (opcional)">
          <Table
            headers={['Parámetro', 'Descripción', 'Default']}
            rows={[
              ['E-value', 'Umbral de significancia estadística', '0.001'],
              ['Máx. hits', 'Número máximo de resultados', '10'],
            ]}
          />
        </Step>
        <Step n={3} title="Interpretar los resultados">
          Cada hit muestra: nombre de la proteína diana, gen, identidad (%), E-value, score de alineación y los fármacos que actúan sobre esa diana en DrugGraph.
        </Step>

        <H3>Interpretar la identidad</H3>
        <Table
          headers={['Identidad', 'Significado']}
          rows={[
            ['95–100%', 'Coincidencia casi perfecta — muy probablemente la misma proteína'],
            ['70–94%', 'Homólogo cercano — misma familia de proteínas'],
            ['40–69%', 'Homólogo moderado — función similar posible'],
            ['< 40%', 'Homología distante — interpretar con cautela'],
          ]}
        />

        <Note type="info">
          El índice BLAST debe haberse construido previamente con <Code>python build_blast_db.py</Code>. Si no está disponible, los endpoints devuelven <Code>503</Code>.
        </Note>

        <H3>Ejemplo de uso</H3>
        <P>Si tienes la secuencia de una proteína de interés y quieres saber qué fármacos aprobados la inhiben, pégala en el campo y ejecuta la búsqueda. Los resultados te darán directamente los DrugBank IDs relevantes.</P>
      </>
    ),
  },

  {
    id: 'network',
    icon: '🕸️',
    title: 'Análisis de Red (GDS)',
    content: (
      <>
        <H2>Análisis de Red (GDS)</H2>
        <P>La página de Análisis de Red (<Code>/network</Code>) aplica algoritmos de grafos sobre la red global de interacciones fármaco-diana usando Neo4j GDS (Graph Data Science).</P>

        <Note type="warning">
          Requiere el plugin <strong>Neo4j GDS</strong> instalado en el servidor. Sin él los endpoints devuelven <Code>503 Service Unavailable</Code>.
        </Note>

        <H3>Centralidad</H3>
        <P>Identifica los fármacos o dianas más "importantes" en la red:</P>
        <Table
          headers={['Algoritmo', 'Qué mide']}
          rows={[
            ['PageRank', 'Influencia global de un nodo basada en sus vecinos'],
            ['Betweenness', 'Cuántos caminos cortos pasan por ese nodo (nodos "puente")'],
            ['Degree', 'Número de conexiones directas del nodo'],
          ]}
        />

        <H3>Comunidades (Louvain)</H3>
        <P>Agrupa fármacos y dianas en <strong style={{ color: '#0369a1' }}>comunidades</strong> según la densidad de sus conexiones. Los fármacos de la misma comunidad comparten más targets entre sí que con los de otras comunidades, sugiriendo mecanismos de acción similares.</P>
        <P>La visualización Cytoscape.js colorea cada comunidad con un color distinto. El botón <UIBtn>⬇ PNG</UIBtn> descarga el grafo de comunidades como imagen.</P>

        <H3>Predicción de enlaces</H3>
        <P>Usa el algoritmo <strong>Adamic-Adar</strong> para predecir nuevas interacciones fármaco-diana que aún no están en la base de datos:</P>
        <Table
          headers={['Modo', 'Descripción']}
          rows={[
            ['Por fármaco', 'Introduce un DrugBank ID y obtén las dianas que probablemente interactuarán con él'],
            ['Global', 'Predicciones de mayor puntuación en toda la red (puede ser lento)'],
          ]}
        />
        <Note type="info">
          El score Adamic-Adar es mayor cuanto más vecinos comunes comparten dos nodos. Un score de 0 no significa necesariamente que no haya interacción, sino que la red no tiene suficiente información de vecinos comunes para predecirla.
        </Note>

        <H3>Exportación</H3>
        <P>Tanto el análisis de centralidad como el de comunidades y predicción de enlaces permiten exportar sus resultados en <UIBtn color="#15803d">CSV</UIBtn> y <UIBtn color="#0284c7">JSON</UIBtn> desde los botones de la cabecera de cada sección.</P>
      </>
    ),
  },

  {
    id: 'export',
    icon: '⬇️',
    title: 'Guía de exportación',
    content: (
      <>
        <H2>Guía de exportación</H2>
        <P>DrugGraph permite exportar datos en múltiples formatos desde todas las secciones principales. Aquí tienes un mapa completo de las opciones disponibles.</P>

        <H3>Resumen por página</H3>
        <Table
          headers={['Página', 'Qué se puede exportar', 'Formatos']}
          rows={[
            ['/drugs', 'Lista de resultados del filtro activo', 'CSV'],
            ['/drugs/:id', 'Documento completo del fármaco (MongoDB)', 'JSON'],
            ['/drugs/:id → Grafo', 'Imagen del grafo de interacciones', 'PNG'],
            ['/drugs/:id → Rutas', 'Imagen del grafo de rutas biológicas', 'PNG'],
            ['/sandbox', 'Tabla de similitudes estructurales/comportamentales', 'CSV, JSON, HTML'],
            ['/sandbox → Rutas', 'KEGG, GO (BP/MF/CC), Reactome, WikiPathways, PPI', 'CSV individual, JSON completo'],
            ['/network → Centralidad', 'Ranking de fármacos/dianas por centralidad', 'CSV, JSON'],
            ['/network → Comunidades', 'Asignación de comunidades + grafo visual', 'CSV, JSON, PNG'],
            ['/network → Predicción', 'Interacciones predichas para un fármaco', 'CSV, JSON'],
            ['/tools/toxicity', 'Informe de riesgo toxicológico', 'CSV, JSON'],
            ['/tools/ddi', 'Lista de DDIs de un fármaco', 'CSV'],
            ['/tools/deg', 'Genes solapantes y enriquecimiento GO', 'CSV, JSON'],
          ]}
        />

        <H3>Formatos disponibles</H3>
        <Table
          headers={['Formato', 'Cuándo usarlo']}
          rows={[
            ['CSV', 'Importar en Excel, R, Python (pandas). Ideal para tablas planas.'],
            ['JSON', 'Integración con scripts, APIs o análisis programáticos. Preserva la estructura completa.'],
            ['PNG', 'Incluir grafos en presentaciones o informes. Alta resolución (×2).'],
            ['HTML', 'Informe imprimible listo para PDF. Incluye estilos y tabla formateada.'],
          ]}
        />

        <H3>Cómo generar un reporte HTML del Sandbox</H3>
        <Step n={1} title="Analiza tu compuesto">
          Introduce el SMILES y haz clic en <UIBtn color="#7c3aed">🔬 Analizar</UIBtn>. Espera a que aparezcan los resultados.
        </Step>
        <Step n={2} title="Carga las rutas (opcional)">
          Haz clic en <UIBtn color="#0ea5e9">🗺️ Cargar Rutas y Enriquecimiento</UIBtn> para incluir los datos GO y KEGG en el reporte.
        </Step>
        <Step n={3} title="Genera el reporte">
          Haz clic en <UIBtn color="#6d28d9">📄 Reporte</UIBtn>. Se abre una nueva pestaña con el informe HTML. Usa <Code>Ctrl+P</Code> → Guardar como PDF para archivarlo.
        </Step>

        <Note type="tip">
          Los archivos exportados siguen la convención de nombre <Code>druggraph_[tipo]_[nombre]_[fecha].ext</Code> para facilitar su organización.
        </Note>
      </>
    ),
  },

  {
    id: 'api',
    icon: '⚡',
    title: 'Referencia de API',
    content: (
      <>
        <H2>Referencia de API REST</H2>
        <P>Base URL: <Code>http://localhost:8000/api</Code>. Todos los endpoints (excepto login y registro) requieren el header <Code>Authorization: Bearer {'<token>'}</Code>.</P>

        <H3>Autenticación</H3>
        <CodeBlock lang="HTTP">
{`POST /api/auth/login/
Content-Type: application/json

{ "email": "admin@druggraph.dev", "password": "admin1234" }

→ { "token": "<jwt>", "user": { "id", "email", "name", "is_admin" } }`}
        </CodeBlock>

        <H3>Fármacos</H3>
        <CodeBlock lang="HTTP">
{`GET /api/drugs/?search=ibuprofen&drug_type=small+molecule&group=approved&page=1
GET /api/drugs/filters/
GET /api/drugs/DB01050/
GET /drugs/DB01050/graph/          ← sin prefijo /api/`}
        </CodeBlock>

        <H3>Dianas</H3>
        <CodeBlock lang="HTTP">
{`GET /api/drugs/targets/?search=PTGS&organism=Humans&page=1
GET /api/drugs/targets/BE0000757/  ← detalle de diana por drugbank_target_id`}
        </CodeBlock>

        <H3>Sandbox</H3>
        <CodeBlock lang="HTTP">
{`# Analizar un compuesto
POST /api/drugs/sandbox/analyze/
{
  "smiles": "CC(=O)Oc1ccccc1C(=O)O",
  "name": "Aspirina",
  "target_ids": ["BE0000262"]
}

# Buscar targets para autocompletar
GET /api/drugs/sandbox/targets/?search=PTGS

# Importar CSV de SwissTargetPrediction
POST /api/drugs/sandbox/swiss-targets/    ← multipart/form-data, campo "file"

# Predecir via API de SwissTargetPrediction
GET /api/drugs/sandbox/swiss-targets/?smiles=CC(=O)Oc1ccccc1C(=O)O&organism=Homo+sapiens

# Análisis de rutas, GO y PPI (lento: 30–90 s)
POST /api/drugs/sandbox/pathways/
{
  "target_ids": ["BE0000262", "BE0000757"],   ← targets directos (opcional)
  "drug_ids":   ["DB01050", "DB09213"]        ← fármacos similares (opcional)
}

# Limpiar nodo sandbox persistido
DELETE /api/drugs/sandbox/<sandbox_id>/`}
        </CodeBlock>

        <H3>Rutas biológicas (perfil de fármaco)</H3>
        <CodeBlock lang="HTTP">
{`GET /api/drugs/DB01050/pathways/`}
        </CodeBlock>

        <H3>BLAST</H3>
        <CodeBlock lang="HTTP">
{`POST /api/drugs/blast/search/
{ "sequence": "MNIFEMLRIDE...", "evalue": 0.001, "max_hits": 10 }`}
        </CodeBlock>

        <H3>GDS</H3>
        <CodeBlock lang="HTTP">
{`GET /api/drugs/gds/centrality/?top_n=20&algorithm=pagerank
GET /api/drugs/gds/communities/
GET /api/drugs/gds/predict/DB01050/
GET /api/drugs/gds/predict-global/`}
        </CodeBlock>

        <H3>Herramientas</H3>
        <CodeBlock lang="HTTP">
{`# Toxicidad
GET /api/drugs/tools/toxicity/?drug_id=DB01050

# Reposicionamiento
GET /api/drugs/tools/repurposing/?drug_id=DB01050&top_n=10

# DDI — par o individual
GET /api/drugs/tools/ddi/?drug_a=DB01050&drug_b=DC1234
GET /api/drugs/tools/ddi/?drug_a=DB01050

# Análisis DEG
POST /api/drugs/tools/deg/
{ "drug_id": "DB01050", "genes": ["PTGS1", "PTGS2", "CYP2C9"] }`}
        </CodeBlock>

        <H3>Códigos de estado HTTP</H3>
        <Table
          headers={['Código', 'Descripción']}
          rows={[
            ['200', 'Éxito'],
            ['201', 'Creado (registro)'],
            ['400', 'Parámetros incorrectos o faltantes'],
            ['401', 'No autenticado — incluir token JWT en Authorization header'],
            ['404', 'Recurso no encontrado'],
            ['500', 'Error interno del servidor'],
            ['502', 'Error en API externa (SwissTargetPrediction, STRING, KEGG)'],
            ['503', 'Servicio no disponible (GDS no instalado, RDKit ausente, BLAST no indexado)'],
          ]}
        />

        <H3>Límites conocidos</H3>
        <Table
          headers={['Endpoint', 'Límite']}
          rows={[
            ['sandbox/pathways/', 'Máx. 30 targets, 10 drug_ids por llamada'],
            ['drugs/:id/pathways/', 'Máx. 25 targets por fármaco'],
            ['blast/search/', 'Requiere BLAST+ instalado y base de datos preconstruida'],
            ['gds/*', 'Requiere plugin Neo4j GDS'],
          ]}
        />
      </>
    ),
  },
];

// ── Componente principal ───────────────────────────────────────────────────────

