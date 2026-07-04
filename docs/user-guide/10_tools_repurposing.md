# 10 — Reposicionamiento de Fármacos

**Ruta:** `/tools/repurposing`

La herramienta de reposicionamiento busca fármacos con un **perfil de dianas moleculares similar** al del fármaco consultado. La similitud se calcula mediante el coeficiente de Jaccard sobre los conjuntos de genes target. Un Jaccard alto sugiere que ambos fármacos comparten mecanismo de acción y podrían ser candidatos a las mismas indicaciones terapéuticas.

---

## ¿Cuándo usarla?

- Quieres identificar **fármacos aprobados** que podrían reutilizarse para una nueva indicación.
- Tienes un fármaco de interés y buscas **análogos funcionales** (mismo mecanismo, diferente estructura).
- Quieres explorar si existe algún fármaco conocido que comparta dianas con tu compuesto de investigación.

---

## Cómo usar la herramienta

1. Navega a **Herramientas → Reposicionamiento** (`/tools/repurposing`).
2. Ingresa el **DrugBank ID** del fármaco de referencia en el campo de búsqueda (ej. `DB00945` para Aspirina).
3. Ajusta el **umbral Jaccard mínimo** si deseas filtrar candidatos con mayor similitud (por defecto `0.10`).
4. Haz clic en **Buscar candidatos**.
5. Espera el resultado (el cálculo consulta Neo4j para todos los fármacos de la base de datos).

---

## Parámetros

| Parámetro | Descripción | Rango / Default |
|-----------|-------------|----------------|
| **DrugBank ID** | Fármaco de referencia cuyo perfil de dianas se comparará | — (obligatorio) |
| **Jaccard mínimo** | Solo se muestran candidatos con Jaccard ≥ este valor | `[0.0 – 1.0]` / `0.10` |

> El sistema devuelve hasta **50 candidatos** ordenados de mayor a menor similitud.

---

## Interpretación del coeficiente de Jaccard

```
Jaccard(A, B) = |genes(A) ∩ genes(B)| / |genes(A) ∪ genes(B)|
```

| Jaccard | Interpretación |
|---------|----------------|
| `≥ 0.5` | Similitud alta — perfil de dianas muy parecido; candidato fuerte |
| `0.2 – 0.5` | Similitud moderada — comparten dianas relevantes; vale explorar |
| `< 0.2` | Similitud baja — solo coincidencias parciales |

La barra de Jaccard en la tabla usa código de color: **verde** (≥ 0.5), **ámbar** (0.2–0.5), **azul claro** (< 0.2).

---

## Pestañas de resultado

### Candidatos
Tabla con todos los fármacos candidatos que superan el umbral Jaccard. Columnas:

| Columna | Descripción |
|---------|-------------|
| Fármaco | Nombre y DrugBank ID del candidato |
| Jaccard | Similitud de perfil de dianas (barra visual) |
| Genes compartidos | Número de genes en la intersección |
| Targets A / B | Total de targets del fármaco A (referencia) y B (candidato) |

Haz clic en cualquier fila para **expandir los genes compartidos** como chips de colores. Cada chip muestra el símbolo HGNC del gen.

**Exportar CSV** — descarga la tabla completa de candidatos con todos los campos numéricos.

### GO perfil del fármaco referencia
Gráfico de enriquecimiento GO/KEGG calculado sobre **todos los targets del fármaco de referencia** (no solo el cruce). Permite entender en qué procesos biológicos está activo el fármaco consultado.

---

## Ejemplo: Reposicionamiento de Aspirina

1. Ingresa `DB00945` y haz clic en **Buscar candidatos**.
2. Los primeros candidatos serán Salicylic acid, Naproxen, Ibuprofen y otros AINEs con Jaccard ≈ 0.3–0.8.
3. Expande la fila de Naproxen para ver que comparten PTGS1, PTGS2 y otros targets de COX.
4. Cambia el umbral a `0.30` para filtrar solo los candidatos con alta similitud.
5. Revisa la pestaña **GO perfil** para ver que Aspirina activa rutas de respuesta inflamatoria y síntesis de prostaglandinas.

---

## Notas y limitaciones

- El cálculo compara a nivel de **gen** (símbolo HGNC), no de proteína. Si dos fármacos actúan sobre isoformas diferentes del mismo gen, se cuenta como una coincidencia.
- Fármacos sin targets registrados en Neo4j aparecen con Jaccard = 0 y son filtrados automáticamente.
- La herramienta no considera la **dirección** de la interacción (inhibidor vs. inductor); un fármaco inhibidor y uno inductor del mismo gen aparecerán como similares.
- El enriquecimiento GO del perfil usa [g:Profiler](https://biit.cs.ut.ee/gprofiler/) — requiere conexión a internet en el servidor.
