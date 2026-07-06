# Referencias y atribución metodológica — DrugGraph Open

Catálogo de las fuentes que fundamentan los métodos, esquemas de puntaje, valores por defecto y
protocolos de evaluación del proyecto. Para cada entrada se indica **qué informó**:

- **[lib]** librería/código usado · **[método]** algoritmo o idea · **[puntaje]** esquema de score ·
  **[default]** valor por defecto elegido · **[eval]** protocolo de evaluación · **[datos]** fuente de datos.

Las atribuciones de **datos** (DrugCentral, ChEMBL, Open Targets, etc.) están en [`NOTICE`](../NOTICE).
Las **licencias** de código en [`LICENSE`](../LICENSE).

---

## 1. Quimioinformática — descriptores, similitud y drug-likeness

| Referencia | Uso |
|-----------|-----|
| Landrum G. *RDKit: Open-source cheminformatics.* rdkit.org | **[lib]** base de toda la manipulación molecular (fingerprints, descriptores, features, embebido 3D) |
| Rogers D, Hahn M. *Extended-Connectivity Fingerprints.* J Chem Inf Model. 2010;50:742-754 | **[método]** fingerprints Morgan/ECFP4 (radio 2) para similitud de sandbox y features ADMET |
| Jaccard/**Tanimoto** (Willett P. Drug Discov Today. 2006;11:1046) | **[puntaje]** coeficiente de similitud estructural y de diversidad (umbral 0.85 en de novo) |
| Bickerton GR, et al. *Quantifying the chemical beauty of drugs (QED).* Nat Chem. 2012;4:90-98 | **[puntaje][default]** QED para ranking drug-like; umbral QED≥0.3 en filtros de novo |
| Ertl P, Schuffenhauer A. *Estimation of synthetic accessibility (SA score).* J Cheminform. 2009;1:8 | **[puntaje][default]** SA score (1 fácil–10 difícil); umbral SA≤5 |
| Lipinski CA, et al. *Rule of Five.* Adv Drug Deliv Rev. 2001;46:3-26 | **[puntaje][default]** reglas de Lipinski (MW≤500, logP≤5, HBD≤5, HBA≤10) |
| Veber DF, et al. *Molecular properties and oral bioavailability.* J Med Chem. 2002;45:2615 | **[default]** umbral PSA≤140 Å² en filtros ADMET |
| Riniker S, Landrum GA. *Better conformer generation (ETKDG).* J Chem Inf Model. 2015;55:2562 | **[método][default]** embebido 3D ETKDG para pharmacóforos (Tier 5.1) |
| Halgren TA. *MMFF94.* J Comput Chem. 1996;17:490 | **[método]** optimización MMFF de los conformeros 3D |

## 2. Pharmacóforos (Tier 5.1)

| Referencia | Uso |
|-----------|-----|
| Gobbi A, Poppinger D. *Genetic optimization of combinatorial libraries.* Biotechnol Bioeng. 1998;61:47-54 | **[método]** definiciones de rasgos pharmacofóricos de RDKit (`BaseFeatures.fdef`) |
| Wolber G, Langer T. *LigandScout: 3-D pharmacophores.* J Chem Inf Model. 2005;45:160-169 | **[método]** modelado de pharmacóforos; radios de clustering por tipo de rasgo |
| Baroni M, et al. *A common reference framework (consensus, PHASE).* J Chem Inf Model. 2007;47:279-294 | **[método][puntaje]** consenso ponderado de pharmacóforos (idea del voto multi-modelo) |
| Salentin S, et al. *PLIP: protein-ligand interaction profiler.* Nucleic Acids Res. 2015;43:W443 | **[lib]** (opcional) interacciones para pharmacóforo structure-based (Tier 5.2 planeado) |
| **pharmaco-suite** (E. Cubillos). github.com/EduardoCubillos/pharmaco-suite | **[método]** inspiración del esquema SBP/LBP/RBP+consenso; **implementación propia, sin su código** (ver NOTICE) |

## 3. Diseño de novo (Tier 4.4)

| Referencia | Uso |
|-----------|-----|
| Polishchuk P. *CReM: chemically reasonable mutations.* J Cheminform. 2020;12:28 | **[método][lib]** motor de novo por defecto (grow/mutate/link) |
| Swanson K, et al. *Generative AI for synthesizable antibiotics (SyntheMol).* Nat Mach Intell. 2024;6:338-353 | **[método][lib]** motor de novo con síntesis garantizada (Tier 4.4c) |
| Loeffler HH, et al. *REINVENT 4.* J Cheminform. 2024;16:20 | **[método][lib]** motor generativo RNN opcional (Tier 4.4b) |
| Krenn M, et al. *SELFIES.* Mach Learn: Sci Technol. 2020;1:045024 | **[método]** representación robusta para generación (base del enfoque GA, Tier 5.2 planeado) |

## 4. ML de propiedades y toxicidad (Tier 4.3 ADMET, 4.6 Chemprop)

| Referencia | Uso |
|-----------|-----|
| Breiman L. *Random Forests.* Mach Learn. 2001;45:5-32 | **[método]** modelos ADMET supervisados (4.3) |
| Pedregosa F, et al. *Scikit-learn.* J Mach Learn Res. 2011;12:2825 | **[lib]** RandomForest, regresión logística (cabezal LP), split, métricas |
| Yang K, et al. *Analyzing learned molecular representations (D-MPNN).* J Chem Inf Model. 2019;59:3370 | **[método]** GNN de paso de mensajes dirigido (Chemprop) |
| Heid E, et al. *Chemprop.* J Chem Inf Model. 2024;64:9-17 | **[lib]** paquete Chemprop usado en Tier 4.6 |
| Wu Z, et al. *MoleculeNet: a benchmark for molecular ML.* Chem Sci. 2018;9:513 | **[datos][eval]** benchmark y splits para ADMET/Chemprop |
| Huang R, et al. *Tox21 / Tox21 10K.* (Tox21 Data Challenge, NCATS) | **[datos]** 12 ensayos de toxicidad (Tier 4.3/4.6) |
| Martins IF, et al. *A Bayesian approach to BBB penetration (BBBP).* J Chem Inf Model. 2012;52:1686 | **[datos]** dataset BBBP |
| Delaney JS. *ESOL: estimating aqueous solubility.* J Chem Inf Comput Sci. 2004;44:1000 | **[datos]** dataset de solubilidad (ESOL/Delaney) |
| Bemis GW, Murcko MA. *The properties of known drugs: molecular frameworks.* J Med Chem. 1996;39:2887 | **[eval]** scaffold split (evaluación honesta de Chemprop, Tier 4.6) |

## 5. Embeddings y reducción de dimensión (Tier 3.2, 4.1)

| Referencia | Uso |
|-----------|-----|
| Chithrananda S, et al. *ChemBERTa.* arXiv:2010.09885 (2020) | **[método][lib]** embeddings moleculares 768-dim (similitud + mapa químico) |
| Vaswani A, et al. *Attention is all you need.* NeurIPS 2017 · Devlin J, et al. *BERT.* NAACL 2019 | **[método]** arquitectura transformer subyacente a ChemBERTa |
| McInnes L, et al. *UMAP.* arXiv:1802.03426 (2018) | **[método][lib]** proyección 2D del espacio químico (Tier 4.1) |
| Campello RJGB, et al. *Density-based clustering (HDBSCAN).* PAKDD 2013 · McInnes L, et al. JOSS 2017 | **[método][lib]** clustering del mapa químico |

## 6. Graph ML y medicina de redes (Tier 4.2, 4.7 y servicios)

| Referencia | Uso |
|-----------|-----|
| Neo4j Graph Data Science (GDS) library | **[lib]** proyecciones y algoritmos de grafo |
| Chen H, et al. *Fast and Accurate Network Embeddings (FastRP).* CIKM 2019 | **[método][default]** embeddings de grafo (dim 128) para DTI-GNN y Disease-GNN |
| Hamilton W, et al. *Inductive representation learning (GraphSAGE).* NeurIPS 2017 | **[método]** embeddings inductivos (opción de DTI-GNN) |
| Grover A, Leskovec J. *node2vec.* KDD 2016 | **[método]** familia de embeddings de grafo (contexto) |
| Blondel VD, et al. *Fast unfolding of communities (Louvain).* J Stat Mech. 2008;P10008 | **[método]** detección de comunidades (GDS materializado) |
| Page L, Brin S. *The PageRank citation ranking.* 1998 | **[método][default]** centralidad PageRank (damping 0.85) |
| Adamic LA, Adar E. *Friends and neighbors on the Web.* Soc Networks. 2003;25:211 | **[método]** predicción de enlaces topológica (Adamic-Adar) |
| Guney E, et al. *Network-based in silico drug efficacy screening.* Nat Commun. 2016;7:10331 | **[método][puntaje]** proximidad de red `d_c` + modelo nulo por grado (z-score/p-valor) |
| Resnik P. *Using information content.* IJCAI 1995 · Lin D. *Information-theoretic similarity.* ICML 1998 | **[puntaje]** peso de especificidad IDF `log2((N+1)/(n+1))` en repurposing |
| BiomedGPS (KG + GNN) — github.com/… (concepto) | **[método]** idea de link-prediction fármaco→enfermedad sobre el KG (Tier 4.7) |
| Antibiotics_Chemprop (Wong/Stokes, Cell 2020, MIT) | **[método]** inspiración del predictor GNN de bioactividad (Tier 4.6) |

## 7. Recursos y APIs de bioinformática

| Referencia | Uso |
|-----------|-----|
| Szklarczyk D, et al. *STRING.* Nucleic Acids Res. | **[datos][lib]** PPI + enriquecimiento GO/KEGG/Reactome (FDR); umbrales 700/900 (confianza alta/altísima) |
| Kanehisa M, Goto S. *KEGG.* Nucleic Acids Res. | **[datos][lib]** pathways y relaciones reguladoras KGML (signo activación/inhibición) |
| Ochoa D, et al. *Open Targets Platform.* Nucleic Acids Res. | **[datos]** evidencia diana→enfermedad (capa `:Disease`, Tier 4.7) |
| Salentin S, et al. *PLIP.* NAR 2015 (ver §2) | **[lib]** interacciones proteína-ligando |
| Altschul SF, et al. *Basic Local Alignment Search Tool (BLAST).* J Mol Biol. 1990;215:403 | **[lib][método]** búsqueda de homología de secuencia |
| Raudvere U, et al. *g:Profiler.* Nucleic Acids Res. 2019;47:W191 | **[lib]** enriquecimiento GO (DEG, repurposing) |
| Subramanian A, et al. *LINCS L1000.* Cell. 2017;171:1437 | **[datos][método]** reversión de firma transcriptómica (Tier 3.1) |
| Trott O, Olson AJ. *AutoDock Vina.* J Comput Chem. 2010;31:455 · Eberhardt J, et al. *Vina 1.2.* JCIM 2021;61:3891 | **[método][lib]** docking del Tier 5 (planeado, `docs/TIER5_PLAN.md`) |

## 8. Sistema de evaluación (protocolos y métricas)

| Referencia | Uso |
|-----------|-----|
| Fawcett T. *An introduction to ROC analysis.* Pattern Recogn Lett. 2006;27:861 | **[eval]** ROC-AUC (todos los clasificadores) |
| Davis J, Goadrich M. *The relationship between PR and ROC curves.* ICML 2006 | **[eval]** PR-AUC / Average Precision (recomendado en clases desbalanceadas) |
| Bemis & Murcko 1996 (ver §4) | **[eval]** scaffold split |
| Pearson / Spearman (correlaciones) | **[eval]** correlación predicho vs. medido (ESOL) y prob vs. score-OT |
| Baroni et al. 2007 (ver §2) | **[eval][puntaje]** pesos de confianza del consenso pharmacofórico (★☆☆–★★★) |
| Enrichment Factor (EF) + ROC vs. decoys DUD-E (Mysinger MM, et al. J Med Chem. 2012;55:6582) | **[eval]** validación del docking del Tier 5 (planeado) |

**Protocolo held-out del proyecto** (ver `dataset_testing/REPORT.md`): split 80/20 con `random_state`
fijo; muestreo negativo 1:1 para link-prediction; embeddings de grafo no supervisados (transductivo);
matriz de confusión @0.5 + ROC/PR + correlación. Valores por defecto: `test_size=0.2`, `neg_ratio=1`,
`top_k=20`, `embeddingDimension=128`, `min_consensus/min_fraction=0.5`.

---

## 9. Atribución metodológica (inspiración, sin código)

- **pharmaco-suite** (Eduardo Cubillos) — inspiración del módulo de pharmacóforos del Tier 5 (§2).
- **SyntheMol / Antibiotics_Chemprop / BiomedGPS** — inspiración de los Tiers 4.4c / 4.6 / 4.7,
  implementados con librerías open y código propio (ver la tabla evaluada en `docs/TIER4_ACTIVATION.md §5`).

> Nota: las citas dan la referencia canónica de cada método. Donde el proyecto usa una **librería**
> ([lib]) se cita también su paper. Los **valores por defecto** ([default]) siguen la convención de la
> fuente citada o son estándar de ML; se listan de forma consolidada en `dataset_testing/REPORT.md`.
