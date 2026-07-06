# Reporte in silico — Maresin 1 (MaR1) con DrugGraph Open

_Generado: 2026-07-06 con las herramientas de la plataforma. Todo es predicción in silico
(hipótesis), no validación experimental._

**Maresin 1 (MaR1)** — CID PubChem 60201795 · `C22H32O4` · ácido
(4Z,7R,8E,10E,12Z,14S,16Z,19Z)-7,14-dihidroxidocosahexaenoico.
SMILES: `CC/C=C\C/C=C\C[C@@H](/C=C\C=C\C=C\[C@@H](C/C=C\CCC(=O)O)O)O`

MaR1 es un **mediador lipídico especializado pro-resolución (SPM)** derivado del DHA (omega-3),
con papel en la resolución de la inflamación. **No está en el catálogo** de DrugGraph, así que se
analizó por su SMILES y se usó su vecino estructural más cercano del catálogo como proxy para las
consultas de red. A continuación, todo lo que la plataforma puede decir de MaR1 de forma congruente.

---

## 1. Propiedades fisicoquímicas (RDKit)

| Propiedad | Valor | Lectura |
|-----------|------:|---------|
| Peso molecular | 360.5 | — |
| logP | 4.49 | Lipofílico |
| Donadores / Aceptores de H | 3 / 3 | 2 OH + carboxilo |
| TPSA | 77.8 Å² | — |
| Enlaces rotables | **14** | Muy flexible (cadena poliinsaturada) |
| QED (drug-likeness) | **0.315** | Bajo — no es "drug-like" clásico (es un lípido) |
| SA score | 4.15 | Sintetizabilidad media |
| Lipinski | 4/4 | Cumple la Regla de 5 |

**Lectura**: perfil típico de un **ácido graso hidroxilado**: cabeza polar (carboxilo + 2 hidroxilos)
y cola hidrofóbica larga y muy flexible. QED bajo y 14 enlaces rotables lo alejan del espacio
"drug-like" clásico — coherente con un mediador lipídico endógeno, no un fármaco de síntesis.

## 2. ¿A quién se parece? — Vecinos estructurales del catálogo (Tanimoto/Morgan)

| # | Similitud | Fármaco | Clase |
|---|----------:|---------|-------|
| 1 | **0.667** | **doconexent (DHA)** | Omega-3 (su precursor biosintético) |
| 2 | 0.541 | ácido eicosapentaenoico (EPA) | Omega-3 |
| 3 | 0.513 | ácido linolénico | Omega-3 |
| 4 | 0.415 | ácido gamolénico | Omega-6 |
| 5 | 0.405 | ácido linoleico | Omega-6 |
| 6 | 0.386 | icosapent etilo | Omega-3 (fármaco, hipertrigliceridemia) |
| 7–10 | 0.28–0.38 | ricinoleico, oleico, cerulenina, melinamida | Ácidos grasos |

**Lectura — muy congruente**: los 6 vecinos más cercanos son **ácidos grasos omega-3/6**, encabezados
por el **DHA (doconexent)**, que es precisamente el precursor del que deriva MaR1. La plataforma
"reconoce" correctamente a MaR1 como parte de la familia de los ácidos grasos poliinsaturados.

## 3. Espacio químico (Tier 4.1 — ChemBERTa + UMAP)

MaR1 se ubica en **(x=2.37, y=2.74), cluster 1** del mapa del catálogo — la vecindad de los lípidos
/ ácidos grasos, consistente con §2.

## 4. Pharmacóforo 3D (Tier 5.1)

| Familia de rasgo | Nº |
|------------------|---:|
| Hidrofóbico | **19** |
| Aceptor de H | 4 |
| Donador de H | 3 |
| Ionizable negativo | 1 (carboxilo) |

**Lectura**: el pharmacóforo captura la naturaleza **anfipática** de MaR1 — un enorme componente
hidrofóbico (la cola de 22 carbonos poliinsaturada, 19 rasgos) frente a un extremo polar/aniónico
(carboxilo + 2 hidroxilos donadores/aceptores). Es la firma de un ligando de **receptores de lípidos**.

## 5. ADMET (Tier 4.3) y toxicidad (Tier 4.6, Chemprop)

| Endpoint | Predicción | Lectura |
|----------|-----------|---------|
| BBBP (barrera hematoencefálica) | 0.49 | Ambiguo (~50/50) |
| ESOL (solubilidad, logS) | **−5.50** | Poco soluble (lipofílico) |
| Tox21 NR-AR (andrógenos) | 0.09 | Baja |
| Tox21 SR-p53 (genotóxico) | 0.14 | Baja |
| Chemprop SR-ARE (respuesta antioxidante) | 0.31 | Leve |
| Chemprop SR-MMP / NR-ER | 0.26 / 0.22 | Leve |

**Lectura**: baja toxicidad predicha en los 12 ensayos Tox21 (todas las probabilidades bajas),
baja solubilidad acuosa (esperable en un lípido). El flag más alto es "respuesta antioxidante"
(SR-ARE, 0.31) — curiosamente **coherente** con el rol antiinflamatorio/citoprotector de los SPM.

## 6. Docking estructural vs NDM-1 (Tier 5.3)

- Afinidad top: **−5.86 kcal/mol** (poses −5.86 a −5.51).
- **Lectura**: afinidad **débil-moderada** (mejor que la aspirina, −4.86, por más contactos de la
  cola larga, pero lejos de un inhibidor real). MaR1 **no es candidato** a inhibir NDM-1 — como se
  espera de un mediador lipídico. El protocolo NDM-1 está validado (ROC-AUC 0.775; ver
  `dataset_testing/docking/REPORT.md`), así que este "no-hit" es informativo.

## 7. Red de interacción, dianas y repurposing (proxy: DHA / doconexent, sim 0.667)

Como MaR1 no está en el grafo, se usan las consultas de red sobre su vecino más cercano, **DHA
(DC4289)**, como aproximación de su entorno biológico.

**Dianas documentadas (Neo4j)** — receptores de señalización lipídica, muy coherentes con un SPM:
- **FFAR1** (receptor de ácidos grasos libres 1)
- **OXER1** (receptor de oxoeicosanoides)
- **RXRA** (receptor X retinoide α — receptor nuclear lipídico)
- **CYP19A1** (aromatasa)

**Dianas predichas por la GNN DTI (Tier 4.2)**, hipótesis no documentadas: DNMT1 (0.67), KCNH2 (0.42),
DNMT3A (0.40), ABCC5, DHFR, KCNA5.

**Repurposing fármaco→enfermedad (Disease-GNN, Tier 4.7)** — top hipótesis para DHA:
cardiovascular (0.85), **neurodegenerativa (0.85)**, fibrilación auricular (0.84), hipertensión (0.82),
**artritis reumatoide (0.81)**.

**Lectura — notablemente congruente**: las dianas reales (FFAR1/OXER1/RXRA) son exactamente las vías
por las que actúan el DHA y los SPM, y las enfermedades de repurposing (cardiovascular, neurodegenerativa,
artritis reumatoide) **coinciden con los contextos donde MaR1 se investiga de verdad** por su acción
pro-resolución/antiinflamatoria. (Recordar el sesgo del modelo hacia enfermedades "hub" cardiovasculares —
ver `dataset_testing/REPORT.md`.)

---

## 8. Síntesis integrada

DrugGraph Open, sin conocer MaR1 a priori, lo caracteriza de forma **coherente y convergente**:

1. **Estructuralmente** lo agrupa con los ácidos grasos omega-3, encabezados por su precursor DHA.
2. **Fisicoquímicamente** lo describe como un lípido anfipático flexible (QED bajo, 19 rasgos hidrofóbicos).
3. **Farmacológicamente** (vía proxy) lo conecta con receptores de lípidos (FFAR1/OXER1/RXRA) y con
   enfermedades inflamatorias/cardiovasculares/neurodegenerativas — el terreno real de los SPM.
4. **Toxicológicamente** lo predice benigno, con un leve flag antioxidante congruente con su biología.
5. **Estructuralmente (docking)** confirma que no es un inhibidor de NDM-1 (no-hit informativo).

## Limitaciones (honestidad)

- Todo es **in silico** (hipótesis), sin validación experimental.
- MaR1 **no está en el catálogo**: las consultas de red usan al DHA como **proxy** (sim 0.667), no a
  MaR1 exacto; MaR1 tiene actividades propias (receptor **ERV1/ChemR23, LGR6**) que el catálogo no cubre.
- Las predicciones GNN heredan el **sesgo de grado** hacia enfermedades/dianas muy conectadas.
- El docking es rígido y no modela coordinación metálica.
