# 11 — Evaluación de Toxicidad y Off-targets

**Ruta:** `/tools/toxicity`

La herramienta de toxicidad evalúa el **perfil de riesgo** de un fármaco a partir de tres fuentes complementarias:

1. **Anti-targets directos** — dianas registradas en Neo4j cuya activación o inhibición se asocia a efectos adversos conocidos.
2. **Off-targets predichos** — proteínas no registradas pero con alta probabilidad de interacción según la red de vecindad (Adamic-Adar sobre el grafo Neo4j).
3. **Cluster estructural** — fármacos con estructura similar (Jaccard de fingerprints ≥ 0.15) que comparten dianas de riesgo.

---

## ¿Cuándo usarla?

- Quieres evaluar rápidamente el **perfil de seguridad** de un fármaco conocido.
- Estás diseñando un nuevo compuesto y quieres compararlo con fármacos de estructura similar para anticipar efectos adversos.
- Necesitas identificar si el fármaco interactúa con **CYPs** (enzimas de metabolismo) que pueden generar interacciones farmacológicas.

---

## Cómo usar la herramienta

1. Navega a **Herramientas → Toxicidad** (`/tools/toxicity`).
2. Ingresa el **DrugBank ID** del fármaco (ej. `DB00945` para Aspirina).
3. Haz clic en **Evaluar**.
4. Espera el resultado (la consulta Adamic-Adar en Neo4j puede tardar 8–15 segundos).

---

## Medidor de riesgo

El **Risk Score** es un entero de 0 a 10 calculado sumando el peso de cada anti-target encontrado:

| Anti-target | Peso | Ejemplo |
|-------------|------|---------|
| Alto riesgo | +3 | KCNH2 (hERG), SCN5A (QT prolongado), MAOA |
| Riesgo medio | +2 | DRD2, SLC6A4, CYPs (3A4, 2D6, 2C9, 2C19), AR, ESR1 |
| Riesgo bajo | +1 | HRH1, CYP1A2, ESR2, ABCB1, NR3C1 |

El score se **trunca a 10** aunque la suma supere ese valor.

| Score | Nivel | Significado |
|-------|-------|-------------|
| 0 | `sin_datos` | Sin targets registrados o ningún anti-target detectado |
| 1–2 | `bajo` | Perfil de riesgo favorable |
| 3–5 | `moderado` | Precaución; revisar contexto clínico |
| 6–8 | `alto` | Riesgo significativo; requiere evaluación experta |
| 9–10 | `muy_alto` | Múltiples anti-targets de alto peso |

---

## Pestañas de resultado

### Alertas
Lista de anti-targets detectados, agrupados por nivel de riesgo. Cada alerta muestra:

- **Nivel** (`ALTO` / `MEDIO` / `BAJO`) con icono y color
- **Categoría de riesgo** (ej. "Cardiotoxicidad", "Interacción farmacológica CYP", "Efecto endocrino")
- **Gen** — símbolo HGNC (ej. `KCNH2`)
- **Proteína** — nombre del target
- **UniProt** — enlace al accession
- **Relación** — tipo de interacción con el fármaco (`INHIBITS`, `INDUCES`, `SUBSTRATE`, etc.)
- **Mensaje** — explicación clínica del riesgo

Haz clic en cualquier alerta para **expandirla** y ver todos los detalles.

### CYPs
Tabla de interacciones con citocromos P450 (enzimas del metabolismo hepático). Una interacción con CYPs no es necesariamente tóxica, pero indica posibles **interacciones farmacocinéticas**:

- Si el fármaco es **inhibidor** de un CYP, puede elevar los niveles plasmáticos de otros fármacos metabolizados por esa enzima.
- Si es **inductor**, puede reducir la eficacia de otros compuestos.
- Si es **sustrato**, otros inhibidores de ese CYP pueden elevar sus propios niveles.

CYPs cubiertos: CYP3A4, CYP2D6, CYP2C9, CYP2C19, CYP1A2, CYP2B6.

### Off-targets predichos
Proteínas con las que el fármaco podría interactuar pero que **no están registradas** en DrugBank. La predicción usa el algoritmo **Adamic-Adar** sobre el grafo Neo4j: dos nodos tienen alta probabilidad de conectarse si comparten muchos vecinos en común.

Columnas:

| Campo | Descripción |
|-------|-------------|
| Proteína | Nombre y símbolo HGNC |
| UniProt | Accession de la proteína |
| Score AA | Score Adamic-Adar (mayor = más probable) |
| Vecinos comunes | Número de targets compartidos que generan la predicción |
| ¿Anti-target? | Si la proteína está en la lista de anti-targets, se resalta con su nivel de riesgo |

> Se muestran los 25 off-targets con mayor score. Usa el botón **Ver más** para expandir todos.

### Cluster estructural
Fármacos con estructura química similar al fármaco consultado (Jaccard de fingerprints moleculares Morgan/ECFP4 ≥ 0.15). Útil para:

- Anticipar si fármacos similares comparten efectos adversos conocidos.
- Explorar si el compuesto pertenece a una clase farmacológica con riesgos documentados.

Columnas: DrugBank ID, Nombre, Jaccard (barra visual), Targets compartidos.

---

## Anti-targets cubiertos

| Gen | Nivel | Categoría |
|-----|-------|-----------|
| KCNH2 | Alto | Cardiotoxicidad (QT) |
| SCN5A | Alto | Cardiotoxicidad (QT) |
| MAOA | Alto | Síndrome serotoninérgico |
| DRD2 | Medio | Efectos extrapiramidales |
| SLC6A4 | Medio | Síndrome serotoninérgico |
| MAOB | Medio | Síndrome serotoninérgico |
| CHRM1, CHRM2, CHRM3 | Medio | Efectos anticolinérgicos |
| PTGS1 | Medio | Gastrotoxicidad (úlcera) |
| CYP3A4, CYP2D6, CYP2C9, CYP2C19 | Medio | Interacción farmacocinética CYP |
| NR1I2, AR, ESR1, PPARG | Medio | Efectos hormonales / endocrinos |
| DRD3, HRH1 | Bajo | Efectos sobre SNC leves |
| CYP1A2, CYP2B6 | Bajo | Interacción farmacocinética CYP menor |
| ESR2, PPARA | Bajo | Efectos hormonales menores |
| ABCB1 | Bajo | Transporte activo — interacción farmacocinética |
| ADRA1A | Bajo | Efectos cardiovasculares menores |
| NR3C1 | Bajo | Efecto glucocorticoide leve |

---

## Ejemplo: Toxicidad de Ibuprofeno (DB01050)

1. Ingresa `DB01050` y haz clic en **Evaluar**.
2. En **Alertas** verás PTGS1 (medio — gastrotoxicidad) como anti-target directo.
3. En **CYPs** verás interacción con CYP2C9 (sustrato).
4. En **Off-targets predichos** aparecerán proteínas de la familia prostaglandina/ciclooxigenasa con alto score Adamic-Adar.
5. El **Cluster estructural** mostrará Naproxen, Ketoprofeno y otros AINEs con Jaccard ≈ 0.2–0.4.

---

## Notas y limitaciones

- El análisis es **informativo y exploratorio**, no un sustituto de evaluaciones preclínicas o clínicas.
- Los anti-targets detectados son solo los que tienen **interacción registrada en DrugBank**; un fármaco sin ningún target registrado obtendrá score 0 aunque tenga riesgos reales.
- La predicción de off-targets no garantiza interacción real; es una estimación basada en la topología del grafo.
- El cluster estructural requiere que los fingerprints hayan sido precalculados (`populate_fingerprints.py`). Si no hay fingerprints, la pestaña mostrará lista vacía.
