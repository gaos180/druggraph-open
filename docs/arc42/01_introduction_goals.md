# 01 — Introducción y Objetivos

## 1.1 Descripción del Sistema

**DrugGraph** es una plataforma académica de información farmacológica que integra tres fuentes de datos heterogéneas para permitir la exploración de fármacos, sus dianas moleculares y sus interacciones:

- **MongoDB** almacena los documentos completos de fármacos en formato DrugBank (JSON anidado rico).
- **Neo4j** almacena el grafo de interacciones moleculares (`Drug → Target`, `Drug → Category`, `Drug ↔ Drug`).
- **APIs externas** (STRING, KEGG) aportan redes PPI y rutas biológicas bajo demanda.

El sistema expone una API REST (Django) consumida por una SPA (React + TypeScript).

---

## 1.2 Objetivos de Negocio / Académicos

| # | Objetivo | Métrica de éxito |
|---|----------|-----------------|
| O1 | Permitir búsqueda de fármacos por nombre, SMILES, tipo y grupo de aprobación | Resultados correctos en < 2 s |
| O2 | Visualizar la red de interacción fármaco-diana de un compuesto concreto | Grafo renderizado desde Neo4j en < 3 s |
| O3 | Analizar propiedades topológicas de la red completa (centralidad, comunidades) | Cálculo GDS completado en < 30 s |
| O4 | Comparar un compuesto nuevo contra fármacos reales (sandbox) | Similitud Tanimoto + Jaccard retornada en < 5 s |
| O5 | Buscar dianas por homología de secuencia (BLAST) | Resultados de blastp en < 60 s |
| O6 | Mostrar efecto directo e indirecto (STRING PPI) y rutas biológicas (KEGG) | Sección cargada con datos reales |
| O7 | Cruzar genes diferencialmente expresados (DEG) con targets de un fármaco y calcular enriquecimiento GO/KEGG | Análisis completo + g:Profiler en < 20 s |
| O8 | Identificar candidatos a reposicionamiento por similitud de perfil de dianas (Jaccard) | Top 50 candidatos con GO perfil en < 10 s |
| O9 | Evaluar riesgo de toxicidad de un fármaco: anti-targets, CYPs, off-targets predichos y cluster estructural | Informe de riesgo con score 0-10 en < 15 s |
| O10 | Verificar interacciones fármaco-fármaco (DDI) registradas en Neo4j | Resultado en < 1 s para par concreto; lista completa en < 3 s |
| O11 | Enriquecer análisis sandbox con rutas KEGG, GO y PPI de los targets de fármacos similares | Respuesta con FDR real de STRING enrichment en < 90 s |
| O12 | Permitir exportación de resultados en múltiples formatos (CSV, JSON, PNG, HTML) | Descarga inmediata desde cualquier sección de la plataforma |
| O13 | Explorar el catálogo de dianas moleculares con datos UniProt, localización subcelular y red de dianas relacionadas | Perfil de diana cargado en < 3 s |

---

## 1.3 Metas de Calidad

Las tres metas más importantes, en orden de prioridad:

| Prioridad | Atributo de calidad | Escenario clave |
|-----------|--------------------|-----------------| 
| 1 | **Corrección** | Las interacciones fármaco-diana mostradas coinciden exactamente con los datos de DrugBank en Neo4j |
| 2 | **Disponibilidad parcial** | Si Neo4j GDS no está instalado, los endpoints retornan HTTP 503 con mensaje claro; el resto del sistema sigue operativo |
| 3 | **Seguridad** | Ningún endpoint de datos es accesible sin JWT válido; el sandbox no persiste nodos más allá de 30 min |

---

## 1.4 Stakeholders

| Rol | Interés principal | Secciones arc42 relevantes |
|-----|------------------|--------------------------|
| Estudiante / investigador | Explorar datos farmacológicos sin conocer Cypher ni Python | 06 (runtime), Guía de usuario |
| Desarrollador del proyecto | Entender qué componente hace qué para extender el sistema | 05 (bloques), 09 (ADRs) |
| Administrador del sistema | Desplegar y mantener los contenedores y las bases de datos | 07 (despliegue) |
| Evaluador académico | Verificar decisiones de diseño y uso correcto de bases de datos no relacionales | 04 (estrategia), 09 (ADRs) |
