# 09 — Análisis de Expresión Diferencial (DEG)

**Ruta:** `/tools/deg`

La herramienta DEG cruza una lista de genes diferencialmente expresados (obtenida de un experimento transcriptómico) con los targets moleculares registrados de un fármaco, y calcula enriquecimiento funcional GO/KEGG sobre los genes del cruce.

---

## ¿Cuándo usarla?

- Tienes resultados de RNA-seq o microarray (genes con log2FC y p-valor).
- Quieres saber si el fármaco de interés **afecta directamente** alguno de esos genes diferencialmente expresados.
- Quieres ver qué **procesos biológicos** (Gene Ontology, KEGG) aparecen sobrerepresentados en el cruce.

---

## Formato del archivo de entrada

La herramienta acepta archivos **CSV o TSV** con o sin cabecera.

### Modo cuantitativo (recomendado)

Incluye columnas de expresión. Los nombres se detectan automáticamente (insensible a mayúsculas):

| Columna | Nombres aceptados | Descripción |
|---------|------------------|-------------|
| Gen | `gene`, `symbol`, `genename`, `id` | Símbolo HGNC (ej. `PTGS2`) |
| log2FC | `log2fc`, `logfc`, `lfc`, `log2foldchange` | log₂ del fold-change |
| p-valor | `pvalue`, `pval`, `p_value`, `p.value` | p-valor sin corregir |
| FDR | `padj`, `fdr`, `adj`, `bh` | p-valor ajustado (Benjamini-Hochberg u otro) |

Ejemplo:
```csv
gene,log2fc,pvalue,padj
PTGS1,-1.8,0.001,0.005
PTGS2,-2.3,0.0001,0.001
TP53,1.1,0.04,0.090
TNF,2.1,0.002,0.008
GAPDH,0.05,0.82,0.950
```

### Modo lista simple

Si el archivo solo contiene símbolos de genes (sin valores numéricos), la herramienta hace la intersección pero no genera el Volcano Plot.

```txt
PTGS1
PTGS2
TP53
TNF
```

---

## Parámetros de configuración

| Parámetro | Descripción | Valor por defecto |
|-----------|-------------|-------------------|
| **DrugBank ID** | Identificador del fármaco a analizar (ej. `DB00945`) | — (obligatorio) |
| **Umbral \|log₂FC\|** | Genes con \|log₂FC\| ≥ umbral se consideran diferencialmente expresados | `1.0` |
| **Umbral p-valor / FDR** | Corte de significancia estadística | `0.05` |
| **Estadístico** | `p-valor crudo` usa la columna `pvalue`; `FDR (padj)` usa la columna `padj` | `p-valor crudo` |
| **Organismo** | Organismo para el enriquecimiento GO/KEGG (g:Profiler) | `Homo sapiens` |
| **Método de corrección múltiple** | Método para g:Profiler: FDR B-H, Bonferroni, g:SCS, FDR B-Y | `FDR B-H` |
| **Fuentes GO** | Selección múltiple: GO:BP, GO:MF, GO:CC, KEGG, REAC | `GO:BP GO:MF GO:CC KEGG` |

---

## Pestañas de resultado

### Volcano Plot
Gráfico SVG interactivo. Cada punto es un gen del archivo de entrada:
- **Rojo** — significativo y up-regulated (log₂FC > umbral, p < umbral)
- **Azul** — significativo y down-regulated (log₂FC < -umbral, p < umbral)
- **Naranja con etiqueta** — gen que además es target del fármaco
- **Gris** — no significativo

Las líneas punteadas verticales y horizontal indican los umbrales configurados.

### Intersección
Tabla de genes que son simultáneamente significativos en el experimento **y** targets del fármaco en DrugGraph. Columnas:

| Campo | Descripción |
|-------|-------------|
| Símbolo | Nombre HGNC del gen |
| log₂FC | Fold-change logarítmico |
| p-valor | p-valor del experimento |
| FDR | p-valor ajustado |
| Dirección | ↑ Up-regulated / ↓ Down-regulated |
| Target ID | Identificador DrugBank del target (ej. `BE0000262`) |
| UniProt | Accession UniProt de la proteína |
| Relación | Tipo de interacción con el fármaco (`INHIBITS`, `INDUCES`, etc.) |

Desde esta pestaña se puede **exportar CSV** con todos los genes del cruce.

### GO Enrichment
Gráfico de barras horizontal con los términos GO/KEGG enriquecidos en los genes significativos del cruce. Controles:
- **Fuente** — filtra por GO:BP, GO:MF, GO:CC, KEGG, REAC o muestra todos
- **Ordenar por** — FDR (p-valor ajustado) o tamaño de intersección

> Si hay menos de 3 genes en el cruce el enriquecimiento no se calcula (muestra nota explicativa).

### Todos los genes
Tabla completa de todos los genes del archivo, ordenados por significancia. Los targets del fármaco aparecen resaltados en amarillo.

---

## Ejemplo de flujo de trabajo

1. Descarga datos de expresión diferencial desde GEO (ej. GSE73498).
2. Prepara un CSV con columnas `gene,log2fc,pvalue,padj`.
3. En DrugGraph, navega a **Herramientas → Análisis DEG**.
4. Carga el archivo CSV.
5. Ingresa el DrugBank ID del fármaco de interés (ej. `DB00945` para Aspirina).
6. Ajusta los umbrales según el experimento.
7. Haz clic en **Analizar**.
8. Revisa la pestaña **Intersección** para ver qué targets fueron perturbados.
9. Revisa **GO Enrichment** para identificar procesos biológicos afectados.
10. Exporta el CSV del cruce para reportar en el manuscrito.

---

## Notas y limitaciones

- La comparación gen-target es **case-insensitive** y compara el símbolo HGNC del archivo contra `gene_name` del target en Neo4j.
- Si un gen tiene múltiples targets (diferentes proteínas con el mismo símbolo) aparece una fila por cada target.
- El enriquecimiento GO usa [g:Profiler](https://biit.cs.ut.ee/gprofiler/) — requiere conexión a internet en el servidor.
- Solo se incluyen términos con FDR < 0.05 en el gráfico de barras.
