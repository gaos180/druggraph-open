# 14 — Guía de Exportación de Datos

DrugGraph permite exportar los resultados de prácticamente todas las secciones en múltiples formatos. Esta guía describe qué se puede exportar desde cada página y cómo hacerlo.

---

## Formatos disponibles

| Formato | Extensión | Descripción |
|---------|-----------|-------------|
| **CSV** | `.csv` | Tabla plana de datos, compatible con Excel, LibreOffice Calc, pandas, R |
| **JSON** | `.json` | Documento completo con toda la estructura de la respuesta de la API |
| **PNG** | `.png` | Imagen del grafo Cytoscape a resolución ×2 (doble resolución para impresión) |
| **HTML** | `.html` | Informe imprimible con estilos embebidos; abre directamente en el navegador |

---

## Exportaciones por sección

### Listado de fármacos (`/drugs`)

**Botón:** "Exportar CSV" (esquina superior derecha del listado)

Exporta los fármacos actualmente visibles según los filtros aplicados (búsqueda, tipo, grupo). No pagina automáticamente; exporta solo la página actual.

**Modos:**

| Modo | Contenido del CSV |
|------|------------------|
| Normal (sin filtro de diana) | DrugBank ID, nombre, tipo, grupos de aprobación, descripción |
| Por diana (búsqueda por gen/UniProt) | Mismos campos + columna de diana que generó el resultado |

---

### Perfil de fármaco (`/drugs/:id`)

**Botón:** "Exportar JSON" en la cabecera del perfil

Descarga el documento completo del fármaco tal como está almacenado en MongoDB. Incluye todos los campos de DrugBank: categorías, interacciones, farmacocinética, referencias, etc.

---

### Grafos Cytoscape (todas las páginas)

El botón **⬇ PNG** aparece en la esquina superior derecha de cualquier grafo Cytoscape:

| Grafo | Página |
|-------|--------|
| Red de interacción fármaco-diana | `/drugs/:id` → pestaña Red |
| Red de dianas relacionadas | `/targets/:id` |
| Red de rutas PPI sandbox | `/sandbox` → sección Pathways |
| Red de comunidades (GDS) | `/network` |
| Visualización DEG | `/tools/deg` |

La imagen exportada tiene el doble de resolución de pantalla (factor ×2), apropiada para presentaciones e informes.

---

### Sandbox — Análisis estructural/comportamental (`/sandbox`)

Tras el análisis, aparecen tres botones de exportación:

| Botón | Formato | Contenido |
|-------|---------|-----------|
| Exportar CSV | `.csv` | DrugBank ID, nombre, score estructural, score comportamiento, score combinado, método |
| Exportar JSON | `.json` | Respuesta completa: propiedades fisicoquímicas, listas de similitud, método usado, targets |
| Exportar HTML | `.html` | Informe imprimible con propiedades, tabla de similares, fecha y metadatos del análisis |

---

### Sandbox — Rutas metabólicas (`/sandbox` → sección Pathways)

Una vez cargadas las rutas, cada sub-sección tiene su propio botón de exportación CSV, además de un botón de exportación JSON global.

| Sub-sección | Exportación CSV | Columnas CSV |
|-------------|----------------|--------------|
| KEGG Pathways | Sí | `pathway_id`, `name`, `target_count`, `targets` |
| GO Process | Sí | `term`, `description`, `gene_count`, `fdr`, `genes` |
| GO Function | Sí | Igual que GO Process |
| GO Component | Sí | Igual que GO Process |
| Reactome | Sí | `term`, `description`, `gene_count`, `fdr`, `genes` |
| WikiPathways | Sí | `term`, `description`, `gene_count`, `fdr`, `genes` |
| PPI Vecinos | Sí | `protein`, `string_id`, `max_score`, `connected_to` |

**Botón "Exportar todo (JSON)"**: descarga la respuesta completa del endpoint `POST /api/drugs/sandbox/pathways/` en un único archivo JSON con todas las sub-secciones.

---

### Análisis de Red Global (`/network`)

| Panel | Formato | Contenido |
|-------|---------|-----------|
| Centralidad | CSV + JSON | DrugBank ID, nombre, score PageRank, score Betweenness |
| Comunidades | CSV + JSON | DrugBank ID, nombre, ID de comunidad, tamaño de comunidad |
| Predicción de enlaces | CSV + JSON | DrugBank ID origen, DrugBank ID destino, target, score Adamic-Adar |

Los botones **CSV** y **JSON** aparecen en la cabecera de cada panel tras calcular los resultados.

---

### Herramienta de Toxicidad (`/tools/toxicity`)

| Botón | Formato | Contenido |
|-------|---------|-----------|
| Exportar CSV | `.csv` | Todas las alertas de anti-targets + interacciones CYP + off-targets predichos |
| Exportar JSON | `.json` | Informe completo: risk_score, risk_level, alerts, cyp_interactions, predicted_offtargets, structural_cluster |

---

### DDI Checker (`/tools/ddi`)

| Botón | Formato | Contenido |
|-------|---------|-----------|
| Exportar CSV | `.csv` | `drugbank_id_a`, `name_a`, `drugbank_id_b`, `name_b`, `description` |

En modo par exporta una fila (si hay interacción). En modo lista exporta todas las DDIs encontradas.

---

### Análisis DEG (`/tools/deg`)

| Botón | Formato | Contenido |
|-------|---------|-----------|
| Exportar CSV | `.csv` | Gen, log2FC, p-valor, FDR, dirección, ¿es target?, tipo de relación |
| Exportar JSON | `.json` | Respuesta completa incluyendo genes, solapamiento con targets, enriquecimiento GO |

---

## Consejos de uso

- **Para análisis estadístico posterior**: usa siempre el formato JSON; contiene toda la información sin truncar.
- **Para presentaciones / informes**: usa PNG (grafos) o HTML (sandbox).
- **Para compartir datos con colaboradores**: el CSV es el formato más universal y legible.
- **Para reproducir el análisis**: el JSON del sandbox incluye el SMILES y los target_ids usados, lo que permite reproducir el análisis programáticamente.

---

## Exportación programática (API)

Todos los datos exportables son accesibles directamente mediante la API REST. Consulta la [Referencia de API REST](08_api_reference.md) para los endpoints exactos. Ejemplo de descarga programática de un perfil completo de fármaco:

```bash
# Descargar el documento completo de Ibuprofeno en JSON
curl "http://localhost:8000/api/drugs/DB01050/" \
  -H "Authorization: Bearer <token>" \
  -o ibuprofen.json

# Descargar rutas sandbox para un conjunto de targets
curl -X POST "http://localhost:8000/api/drugs/sandbox/pathways/" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"target_ids": ["BE0000262", "BE0000017"], "drug_ids": ["DB01050"]}' \
  -o sandbox_pathways.json
```
