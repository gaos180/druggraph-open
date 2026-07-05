# Revisión de biología de sistemas / medicina de redes — DrugGraph Open

> Documento de análisis conceptual (solo lectura). Revisa la **validez biológica** del
> sustrato open-data para medicina de redes y la **solidez de cada método** ya
> implementado, con recomendaciones accionables. Todas las afirmaciones cuantitativas
> están respaldadas por sondeos reales a MongoDB `druggraph_open` y Neo4j (ver §6).
>
> Autor: agente de biología de sistemas · Fecha: 2026-07-04

> **Nota de verificación (orquestador, 2026-07-04):** la afirmación de que las aristas
> `(:Drug)-[:TARGETS]->(:Target)` tienen la acción en NULL es **incorrecta**: se debió a
> consultar la propiedad `r.action` (singular, inexistente) en vez de `r.actions` (lista).
> Verificado en la BD real: **4.477 de las 16.947 aristas `TARGETS` sí llevan `r.actions`
> poblado** (INHIBITOR/AGONIST/…), coherente con las 4.776 entradas con acción en Mongo.
> Por tanto NO hay pérdida del signo en la ingesta (step03 sí propaga `r.actions`). La
> recomendación #2 (usar la acción como signo de semilla en `propagate_signed`) sigue
> siendo válida y de bajo esfuerzo, pero el dato ya está disponible en el grafo.

---

## 0. Resumen ejecutivo

DrugGraph Open construye su capa de medicina de redes sobre un sustrato **open-source
razonable pero heterogéneo** (DrugCentral/ChEMBL para drug–target, STITCH para CPI,
STRING para el interactoma, KEGG/OmniPath para regulación con signo). Los métodos
implementados (`proximity_service`, `propagation_service`, `gds_service`, y las tools de
repurposing/toxicity/DEG/signature-reversion) siguen referencias correctas de la
literatura (Guney-Barabási 2016, Personalized PageRank, connectivity map), pero
**varios cometen simplificaciones que comprometen la interpretabilidad estadística**.

Los tres problemas de mayor impacto detectados son:

1. **Proximidad `d_c` sin modelo nulo.** `closest_proximity()` calcula la distancia media
   más corta entre módulos (métrica correcta de Guney), pero **no corrige por grado con
   randomización** (z-score/p-valor). Sin ese control, `d_c` no es interpretable: módulos
   ricos en hubs obtienen `d_c` baja de forma trivial. Es el control central de la
   referencia y hoy falta. **(alto impacto, esfuerzo medio)**

2. **La dirección/signo del efecto fármaco→diana se descarta.** El documento Mongo tiene
   el `actions` real de cada diana (INHIBITOR / AGONIST / ANTAGONIST / …, 4 719 entradas)
   y `act_type`/`act_value`, pero la arista Neo4j `(:Drug)-[:TARGETS]->(:Target)` tiene
   **`action = NULL` en las 16 947 aristas**. En consecuencia `propagate_signed()` asume
   ciegamente que *el fármaco inhibe todas sus dianas* (`seed_sign = -1`), ignorando
   agonistas/activadores. El dato existe; solo hay que propagarlo a la arista. **(alto
   impacto, esfuerzo bajo)**

3. **No hay umbral de potencia ni ponderación por confianza de arista.** El 50 % de los
   fármacos (2 500/4 995) no tiene ninguna diana, y entre los que sí, `act_value` va desde
   pChEMBL 1.2 (unión ~63 mM, biológicamente irrelevante) hasta 13. Todas cuentan igual
   como "diana real". Igual pasa con STRING (`combined_score` no se usa en proximidad) y
   STITCH (mezcla evidencia experimental, predicha y text-mining). **(alto impacto,
   esfuerzo bajo–medio)**

El resto del documento detalla el sustrato (§1), método por método (§2), recomendaciones
priorizadas (§3), riesgos de interpretación para el usuario (§4) y los sondeos que
fundamentan todo (§6).

---

## 1. Validez biológica del sustrato open-data

### 1.1 ¿Es DrugCentral + STITCH + STRING un buen interactoma / drug–target?

**Sí como aproximación, con caveats importantes.** Es el mismo diseño que usan
plataformas de network medicine publicadas, pero cada capa aporta un sesgo distinto:

| Capa | Fuente | Qué aporta | Caveat principal |
|------|--------|-----------|------------------|
| Drug→Target | DrugCentral (`act_table_full`) + ChEMBL | Dianas con bioactividad medida | Umbrales de potencia laxos; mezcla de tipos de ensayo (§1.2) |
| Chemical–Protein (CPI) | STITCH v5 (`:STITCH_TARGET`) | Dianas soportadas adicionales | `combined_score` mezcla evidencia **experimental + predicha + text-mining** → hay que ponderar por confianza |
| Interactoma PPI | STRING bulk (`:STRING_ASSOC {score}`) | Red para difusión y proximidad | Asociación funcional ≠ interacción física; incompleto y sesgado a proteínas muy estudiadas |
| Regulación con signo | KEGG KGML / OmniPath (`:REGULATES {sign}`) | Dirección + activación/inhibición | Cobertura escasa, sesgada a pathways canónicos bien curados |

**"Diana real" es un concepto graduado, no binario.** En DrugGraph Open la arista
`:TARGETS` se materializa a partir de `act_table_full` sin un corte de potencia estricto:
el `act_value` mediano es **pChEMBL 6.21 (~620 nM)**, pero el mínimo observado es **1.2
(~63 mM)** — es decir, se incluyen uniones tan débiles que no son farmacológicamente
significativas. Además `act_type` mezcla constantes de **afinidad de unión** (Ki 5 987,
Kd 3 936) con **potencia funcional** (IC50 4 656, EC50 756) e incluso **Km** (21), que
mide afinidad de sustrato enzimático y *no* implica que el fármaco module la proteína.
Tratar todas por igual infla el módulo de dianas de cada fármaco.

### 1.2 STITCH y la necesidad de ponderar por confianza

STITCH combina, en un único `combined_score` (0–1000), canales tan dispares como
experimentos, predicción por co-ocurrencia y minería de texto. El pipeline (`step05_stitch_cpi.py`)
filtra a `combined_score ≥ 700`, lo cual es un corte razonable de "alta confianza", pero:

- Un score de 700 por **text-mining** es epistemológicamente distinto de 700 experimental.
- La arista `:STITCH_TARGET` conserva `score` y `ensp`, pero los métodos aguas abajo
  (repurposing, toxicity) tratan `:TARGETS` y `:STITCH_TARGET` como intercambiables sin
  pesar por el score.
- La resolución ENSP→UniProt es **indirecta** (vía `:Target` existente por `gene_name`);
  las dianas STITCH sin `:Target` previo se descartan salvo `--create-missing` — sesgo
  hacia dianas ya conocidas.

### 1.3 Cobertura, incompletitud y sesgo del interactoma

- **Cobertura drug–target:** 2 500 de 4 995 fármacos (**50.05 %**) no tienen ninguna
  `:TARGETS`. Todo análisis de red (proximidad, propagación, repurposing) es **inaplicable
  a la mitad del catálogo** y debe comunicarlo explícitamente al usuario.
- **Sesgo de estudio:** las 1 842 dianas son todas *Homo sapiens* (bien — el filtro de
  organismo es limpio), pero el interactoma STRING está sesgado hacia proteínas muy
  estudiadas; los hubs (p.ej. TP53, CYP3A4) aparecen en muchos módulos y **distorsionan
  toda métrica basada en caminos cortos** si no se corrige por grado.
- **Incompletitud:** STRING y KEGG cubren una fracción del interactoma real; la ausencia
  de un camino corto NO implica ausencia de relación biológica (falsos negativos).

### 1.4 Diferencia frente a DrugBank (curación manual)

DrugBank aportaba `action_type` curado a mano (inhibitor/agonist/…) y `known_action`
validado clínicamente. En DrugGraph Open ese campo viene de DrugCentral: **`known_action =
'yes'` solo en 3 602 de 17 450 registros de diana (20.6 %)**; el resto es `unknown`. Esto
significa que el mecanismo de acción confirmado es minoritario, y cualquier supuesto de
signo (§2.3) descansa sobre datos mayormente no validados.

---

## 2. Solidez y límites de cada método (según el código real)

### 2.1 Proximidad de red `d_c` — `config/services/proximity_service.py`

**Qué hace bien.** Implementa la *closest measure* de Guney et al. (2016): para cada gen
de A promedia la distancia de camino más corto al gen más cercano de B
(`_mean_nearest` + `_nearest_distance`, líneas 39–102), y reporta además la versión
simétrica. La referencia y la fórmula son **correctas**. Reporta cobertura y genes
alcanzables (honesto).

**Límites / faltantes (críticos):**

1. **No hay modelo nulo que preserve grado.** El artículo de Guney define la significancia
   con un **z-score** obtenido randomizando los módulos con conjuntos de genes del mismo
   grado (degree-binned). Sin ese `z(d_c)`/p-valor, la `d_c` cruda es engañosa: un módulo
   con un hub siempre estará "cerca" de todo. **Es la omisión más importante del servicio.**
2. **Ignora `combined_score` de STRING.** Usa `shortestPath((a)-[:STRING_ASSOC*..6]-(b))`
   (línea 47) — traversal **no ponderado**. STRING trae confianza por arista; una versión
   ponderada (distancia = función decreciente del score) sería más fiel.
3. **Módulos de un solo gen o desconectados.** Con un único gen la métrica se vuelve
   inestable (no hay promedio); genes inalcanzables se reportan como `distance = None`
   pero no penalizan el `d_c` (solo bajan la cobertura), lo que puede sesgar `d_c` hacia
   valores bajos si solo los pares cercanos son alcanzables. Conviene exigir cobertura
   mínima y nº mínimo de genes por módulo.
4. **`MAX_DEPTH = 6`** acota bien el coste, pero introduce censura: pares realmente
   distantes se reportan como inalcanzables en lugar de "distancia grande", lo que
   distorsiona la media.

### 2.2 Propagación por difusión (Personalized PageRank) — `propagate()`

**Qué hace bien.** Usa `gds.pageRank.stream` con `sourceNodes` = genes semilla
(Personalized PageRank correcto), proyección **UNDIRECTED** (apropiado para PPI) y
`relationshipWeightProperty = 'score'` (**sí pondera por confianza STRING** — bien). Poda
resultados y limpia la proyección en `finally`.

**Interpretación y supuestos.** El resultado es la **magnitud** de difusión (visitación
estacionaria): "qué tan fuertemente llega la perturbación de las dianas a cada nodo por la
red PPI". **No tiene signo ni dirección** (el propio docstring lo advierte). Supone que la
proximidad en STRING equivale a propagación funcional del efecto — pero STRING mezcla
asociación física, funcional y de co-expresión, así que "propagación" conflaciona tipos de
evidencia.

**Parámetros.** `dampingFactor = 0.6` ⇒ probabilidad de reinicio ≈ 0.4 (relativamente
alta), lo que **localiza** el efecto cerca de las semillas — decisión conservadora y
razonable, pero conviene documentarla y permitir sensibilidad. `maxIterations = 30` puede
no converger del todo en redes grandes, aunque para ranking suele bastar. No se
normalizan los scores entre fármacos, así que **no son comparables entre consultas** (solo
el ranking interno).

### 2.3 Propagación con signo — `propagate_signed()` (red `:REGULATES` KEGG/OmniPath)

**Qué hace.** Difusión lineal en K pasos sobre la red dirigida con signo: el efecto de un
nodo se transmite a sus sucesores multiplicado por `sign` de la arista y atenuado por
`decay` (líneas 141–155). Los efectos se **suman** en `reach`, el signo final es el del
acumulado.

**Supuestos frágiles:**

1. **`seed_sign = -1` fijo = "el fármaco inhibe sus dianas".** Es el problema #2 del
   resumen: el `actions` real (INHIBITOR/AGONIST/ANTAGONIST/BLOCKER/ACTIVATOR…) existe en
   Mongo pero se ignora. Para agonistas/activadores el signo inicial debería ser +1. Hoy
   todo agonista se modela como inhibición → **el signo predicho puede estar invertido**
   para una fracción no trivial de fármacos.
2. **Combinación de signos en ciclos.** La superposición aditiva permite que efectos por
   caminos opuestos se cancelen numéricamente (`nxt[g2] += v*sgn*decay`), lo que es una
   simplificación fuerte; en redes con feedback loops el resultado depende sensiblemente de
   `max_hops` (≤4) y `decay` (0.5) — no hay garantía de convergencia, solo el corte por
   pasos y `FRONTIER_CAP = 800`.
3. **No normaliza por nº de caminos entrantes** → los hubs regulatorios acumulan magnitud
   grande artificialmente.
4. **Cobertura de `:REGULATES`.** KEGG KGML cubre solo pathways canónicos; OmniPath añade
   densidad pero sigue sesgado. Muchas semillas caerán en `seeds_missing` (sin nodo en la
   red dirigida).

### 2.4 Repurposing por Jaccard de dianas — `drugs/views/tools/repurposing.py`

Ranking por Jaccard del conjunto de genes-diana (líneas 69–86), umbral `jaccard ≥ 0.05`.
**Supuestos/sesgos:**

- **Todas las dianas pesan igual.** Compartir un hub promiscuo (CYP3A4, presente en muchos
  fármacos) infla el Jaccard tanto como compartir una diana muy específica. Debería
  ponderarse por especificidad de la diana (estilo IDF: dianas raras valen más).
- **Ignora potencia (`act_value`) y tipo de acción.** Dos fármacos que "tocan" la misma
  proteína con afinidades opuestas o 6 órdenes de magnitud de diferencia se consideran
  equivalentes.
- **Umbral 0.05 arbitrario** y sin control nulo; sesgo hacia fármacos bien anotados
  (más dianas ⇒ más oportunidades de solape).

### 2.5 Toxicidad / off-targets — `drugs/views/tools/toxicity.py`

- **Anti-targets:** diccionario curado `ANTITARGETS` (hERG/KCNH2, CYPs, DRD2, MAOA…) —
  bien fundamentado clínicamente y transparente. Correcto como sistema de alertas.
- **Off-targets predichos:** Adamic-Adar por Cypher (guilt-by-association topológico,
  líneas 116–137). Es una heurística de vecinos-de-vecinos **sin química** (no usa
  estructura/fingerprints), sesgada a dianas hub. Útil como hipótesis, no como predicción.
- **`risk_score` (0–10):** suma heurística de niveles (`_LEVEL_SCORE`), **no calibrada ni
  validada** contra un estándar de toxicidad. Es un indicador cualitativo, no una
  probabilidad.

### 2.6 Reversión de firma — `signature_reversion.py` (LINCS L1000CDS2)

Enfoque de connectivity map estándar (revertir firma up/down). Caveats propios de L1000:
solo ~978 genes *landmark* (el resto inferido), **especificidad de línea celular** (la
firma puede no aplicar al contexto del usuario), y dependencia de una API externa. El score
de conectividad es relativo, no una magnitud absoluta.

### 2.7 DEG + enriquecimiento — `deg.py` (g:Profiler ORA)

ORA correcto con corrección de test múltiple configurable (`fdr_bh` por defecto). Maneja
bien el caso de intersección pequeña (`< 3` genes ⇒ enriquece todos los DEGs, con nota).
**Caveat:** el *background* por defecto de g:Profiler es todo el genoma anotado; si el
ensayo del usuario solo midió un panel, el ORA estará sesgado (debería pasarse el universo
de genes medidos como fondo).

---

## 3. Recomendaciones priorizadas (impacto × esfuerzo)

| # | Recomendación | Archivo / función | Impacto | Esfuerzo |
|---|---------------|-------------------|---------|----------|
| 1 | **Añadir modelo nulo que preserve grado** a la proximidad: randomizar A y B con genes del mismo bin de grado (≈1000 permutaciones), reportar `z(d_c)` y p-valor empírico junto a `d_c`. Sin esto la métrica no es interpretable. | `proximity_service.closest_proximity` | Alto | Medio |
| 2 | **Propagar `action`/`actions` a la arista Neo4j** en la ingesta y usarlo como `seed_sign` por diana (INHIBITOR/ANTAGONIST/BLOCKER→−1; AGONIST/ACTIVATOR→+1; resto→0/neutro). El dato ya está en Mongo. | ingesta `step03_build_graph`; `propagate_signed` (param `seed_sign` → por-semilla) | Alto | Bajo |
| 3 | **Umbral de potencia y bandera de confianza en drug–target.** Marcar/filtrar dianas con `act_value` bajo (p.ej. pChEMBL < 5 = >10 µM) y separar `act_type` de unión (Ki/Kd) vs funcional (IC50/EC50) vs sustrato (Km, excluir de "inhibición"). | ingesta drug–target; `_common._get_drug_targets` | Alto | Bajo–Medio |
| 4 | **Ponderar caminos de proximidad por `combined_score` de STRING** (distancia = Σ 1/score o −log(score/1000)) en lugar de saltos crudos. | `proximity_service._nearest_distance` (Cypher `shortestPath`) | Medio | Medio |
| 5 | **Jaccard ponderado por especificidad de diana** (IDF: penalizar hubs compartidos) y opcionalmente por potencia. Añadir control nulo para el umbral. | `repurposing.py` líneas 69–86; `toxicity._structural_cluster` | Medio | Medio |
| 6 | **Ponderar `:STITCH_TARGET` por su `score`** y distinguirlo visual/analíticamente de `:TARGETS` (evidencia experimental vs. predicha/text-mining). | consultas de repurposing/toxicity | Medio | Bajo |
| 7 | **Filtro de cobertura mínima** en proximidad (nº mínimo de genes por módulo y cobertura ≥ X %) y sustituir `distance=None` por una penalización explícita en vez de excluir. | `proximity_service` | Medio | Bajo |
| 8 | **Normalizar magnitudes de propagación** (dividir por nº de caminos/grado) y exponer análisis de sensibilidad a `damping`/`decay`/`max_hops`. | `propagate`, `propagate_signed` | Bajo–Medio | Medio |
| 9 | **Permitir universo de genes de fondo** en el ORA de DEG. | `deg.py` → `run_enrichment` | Bajo | Bajo |

> El filtro de **organismo ya es correcto** (todas las dianas son *Homo sapiens*); no
> requiere acción, pero conviene documentarlo como invariante y validarlo en la ingesta de
> STITCH (los ENSP conservan prefijo de taxón 9606).

---

## 4. Riesgos de interpretación (qué NO se puede concluir)

Disclaimers que deberían acompañar a estos análisis en la UI/informes:

- **Todo es in silico e hipotético.** Proximidad baja, alta difusión, alto Jaccard o
  reversión de firma generan **hipótesis**, no evidencia de eficacia, seguridad o
  mecanismo. Requieren validación experimental.
- **La ausencia de señal no es evidencia de ausencia.** El interactoma es incompleto y el
  50 % del catálogo no tiene dianas; "sin proximidad" puede ser un falso negativo por
  cobertura, no una conclusión biológica.
- **`d_c` sin z-score no es comparable.** Mientras no exista el modelo nulo (rec. #1), una
  `d_c` numéricamente baja NO implica cercanía significativa — puede deberse a hubs.
- **El signo de la cascada dirigida puede estar invertido** para agonistas/activadores
  mientras `seed_sign` sea fijo (rec. #2); no interpretar la dirección ↑/↓ como definitiva.
- **"Diana" es graduado.** Incluye uniones débiles (hasta ~mM) y tipos de ensayo mixtos;
  no toda `:TARGETS` implica modulación farmacológica relevante.
- **STITCH/text-mining** puede introducir asociaciones espurias; un `:STITCH_TARGET` no es
  equivalente a una diana validada experimentalmente.
- **Los scores de propagación no son probabilidades** ni comparables entre fármacos; solo
  ordenan dentro de una misma consulta.
- **La reversión de firma depende del contexto celular** de LINCS, que puede no coincidir
  con la enfermedad/tejido del usuario.

---

## 5. Conclusión

El sustrato open-data es **apto para prototipar medicina de redes** y las
implementaciones siguen las referencias correctas, pero el proyecto ganaría rigor
sustancial —con esfuerzo bajo— cerrando tres brechas: (1) significancia estadística en la
proximidad (modelo nulo por grado), (2) uso del signo/acción real ya disponible en Mongo,
y (3) ponderación por potencia y confianza de arista. Estas tres, más los disclaimers de
§4, convierten los análisis de "números sin contexto" en hipótesis defendibles.

---

## 6. Sondeos de fundamentación (datos reales)

Consultas ejecutadas en modo solo lectura sobre las BD pobladas.

**S1 — Tipos de relación y cobertura de dianas (Neo4j).**
```cypher
MATCH ()-[r]->() RETURN type(r), count(r) ORDER BY count(r) DESC;
// IN_CATEGORY 29694 · TARGETS 16947
// (STRING_ASSOC / REGULATES / STITCH_TARGET / INTERACTS_WITH se cargaban
//  concurrentemente por otros agentes durante la revisión)
MATCH (d:Drug) OPTIONAL MATCH (d)-[:TARGETS]->(t) WITH d,count(t) AS k
RETURN k, count(d);
// k=0 → 2500 fármacos (50.05% del catálogo sin dianas)
```

**S2 — La arista `:TARGETS` no lleva acción (Neo4j).**
```cypher
MATCH (d:Drug)-[r:TARGETS]->(t:Target) RETURN r.action, count(*);
// NULL, 16947   ← el signo/dirección se pierde en la arista
```

**S3 — Organismo y completitud de dianas (Neo4j).**
```cypher
MATCH (t:Target) RETURN t.organism, count(*);          // Homo sapiens, 1842 (100%)
MATCH (t:Target) RETURN count(*), count(t.gene_name), count(t.uniprot_id);
// total 1842 · con gene 1842 · con uniprot 1842
```

**S4 — El signo/acción SÍ existe en Mongo, pero mayormente sin validar.**
```python
db.drugs.aggregate([{'$unwind':'$targets'},{'$unwind':'$targets.actions'},
                    {'$group':{'_id':'$targets.actions','n':{'$sum':1}}}])
# INHIBITOR 1475 · AGONIST 898 · ANTAGONIST 802 · BLOCKER 534 ·
# POSITIVE ALLOSTERIC MODULATOR 451 · ACTIVATOR 91 · ... (4719 entradas dirigidas)
db.drugs.aggregate([{'$unwind':'$targets'},
                    {'$group':{'_id':'$targets.known_action','n':{'$sum':1}}}])
# unknown 13848 · yes 3602   → solo 20.6% de mecanismos confirmados
```

**S5 — Tipos de ensayo mezclados y potencia laxa (Mongo, `act_value` ≈ pChEMBL).**
```python
# act_type: Ki 5987 · IC50 4656 · Kd 3936 · (vacío) 2035 · EC50 756 · Km 21 · ...
#           → mezcla afinidad de unión (Ki/Kd), potencia funcional (IC50/EC50) y Km
# act_value (n=15419): min 1.2 · p25 5.43 · mediana 6.21 · p75 7.37 · max 13.0
#           → escala pChEMBL; mediana ~620 nM PERO se incluyen uniones hasta ~63 mM
```
