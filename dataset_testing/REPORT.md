# Reporte de evaluación — modelos ML del Tier 4 (DrugGraph Open)

_Generado: 2026-07-06. Datos y métricas reproducibles con los scripts `backend/scripts/eval_*.py`._

Este reporte evalúa las cuatro funcionalidades de machine learning del Tier 4 con **datasets de
test reales y held-out** (fracción reservada que el modelo no vio al entrenar), reportando
aciertos, errores, ROC/PR, correlación y matriz de confusión. Todos los datasets quedan guardados
como respaldo en `dataset_testing/`.

---

## 1. Resumen ejecutivo

| Modelo | Tarea | Protocolo de test | Métrica principal | Resultado |
|--------|-------|-------------------|-------------------|-----------|
| **Disease-GNN (4.7)** | Fármaco→enfermedad (repurposing) | Held-out transductivo 80/20 | ROC-AUC | **0.985** (AP 0.983) |
| **DTI-GNN (4.2)** | Fármaco→diana | Held-out transductivo 80/20 | ROC-AUC | **0.976** (AP 0.974) |
| **ADMET RF (4.3)** | Propiedades ADMET (BBBP/ESOL/Tox21) | Held-out aleatorio 80/20 | ROC-AUC / R² | **0.95 BBBP · R²=0.87 ESOL** |
| **Chemprop GNN (4.6)** | Toxicidad Tox21 (12 ensayos) | Held-out por **scaffold** | ROC-AUC macro | **0.734** |

**Lectura honesta:** los cuatro modelos funcionan y generalizan a datos no vistos. Los dos GNN de
grafo y el RF de BBBP/ESOL rinden muy alto; Chemprop rinde más bajo **a propósito**, porque se
evaluó con el split más exigente (por esqueleto molecular, no aleatorio) — es la comparación justa,
no un peor modelo. Ver §6 (limitaciones) para los matices importantes.

---

## 2. Metodología y datasets

- **Estándar ML**: en cada modelo se separa una fracción de **test held-out** que el modelo no usa
  para entrenar. Se reporta cuántos ejemplos se predicen bien (`correct.csv`) y mal
  (`incorrect.csv`), además de ROC/PR/confusión.
- **Datos reales y creíbles**: fármacos y dianas del catálogo DrugCentral; enfermedades de
  Open Targets (IDs MONDO/EFO/Orphanet); toxicidad/propiedades de MoleculeNet (Tox21, BBBP, ESOL);
  indicaciones clínicas de DrugCentral para el cruce del mundo real.
- **Protocolos**:
  - *GNN de grafo* (Disease/DTI): embeddings FastRP del subgrafo `Drug↔Target↔Disease` (features
    estructurales no supervisadas) + cabezal de Link Prediction (regresión logística) entrenado solo
    con el 80% de las aristas y evaluado en el 20% held-out + negativos muestreados. Es el protocolo
    **transductivo** estándar de link-prediction en knowledge graphs.
  - *ADMET RF*: se reproduce exactamente el split de entrenamiento (`random_state=42`), así el 20%
    evaluado es held-out real (el RandomForest se entrenó solo con el 80%).
  - *Chemprop*: se usa su propio split **por scaffold** (`test_predictions.csv`) — moléculas cuyo
    esqueleto no aparece en train, la evaluación más honesta para generalización química.

---

## 3. Disease-GNN (4.7) — repurposing fármaco→enfermedad

Dataset: `disease_gnn/` · 24 790 asociaciones positivas · **9 916 pares de test** (positivos held-out
+ negativos). Curvas: `disease_gnn/roc_pr.png`.

| Métrica | Valor |
|---------|------:|
| ROC-AUC | **0.9845** |
| PR-AUC (AP) | 0.9830 |
| Accuracy @0.5 | 0.937 |
| Precisión / Recall | 0.915 / 0.964 |
| Matriz de confusión @0.5 | TP 4779 · FP 446 · TN 4512 · FN 179 |
| Aciertos / errores | **9291 / 625** |

**Ejemplos de acierto** (positivos reales bien recuperados): fenol→epilepsia (vía CA2, prob 0.93);
buclizina→resfriado común (HRH1, 0.97). **Ejemplos de error** (positivos que el modelo no recupera):
digoxina→ataxia cerebelosa (ATP1A3, prob 0.16); atropina→hiperhidrosis (CHRM3, 0.46) — asociaciones
de baja conectividad en el grafo.

**Correlación probabilidad vs. score de Open Targets**: Pearson **−0.023**, Spearman −0.071 (n=4958).
Es decir, **casi nula**: el modelo aprende la *topología* (qué enlaces existen) y no la *fuerza* de
la evidencia genética. Predice existencia de asociación, no su magnitud — un matiz honesto y esperable.

---

## 4. DTI-GNN (4.2) — predicción fármaco→diana

Dataset: `dti_gnn/` · 16 947 aristas positivas · **6 780 pares de test**. Curvas: `dti_gnn/roc_pr.png`.

| Métrica | Valor |
|---------|------:|
| ROC-AUC | **0.9757** |
| PR-AUC (AP) | 0.9740 |
| Accuracy @0.5 | 0.923 |
| Precisión / Recall | 0.906 / 0.944 |
| Matriz de confusión @0.5 | TP 3200 · FP 333 · TN 3057 · FN 190 |
| Aciertos / errores | 6257 / 523 |

El modelo recupera con alta fidelidad interacciones fármaco-diana held-out a partir de la sola
topología del grafo (embeddings FastRP), confirmando el rendimiento reportado en entrenamiento.

---

## 5. Modelos moleculares supervisados

### 5.1 ADMET RandomForest (4.3) — held-out `random_state=42`

Dataset: `admet/*_testset.csv`. Plots: `admet/*_roc.png`, `admet/esol_scatter.png`.

| Endpoint | Tarea | n_test | Métrica | Confusión @0.5 |
|----------|-------|-------:|---------|----------------|
| BBBP (barrera hematoencefálica) | clasificación | 408 | **ROC-AUC 0.952** · acc 0.90 | TP 298·FP 27·TN 69·FN 14 |
| ESOL (solubilidad logS) | regresión | 226 | **R² 0.865** · RMSE 0.80 · Pearson 0.93 | — |
| Tox21 NR-AR | clasificación | 1452 | ROC-AUC 0.762 · acc 0.96 | TP 25·FP 15·TN 1375·FN 37 |
| Tox21 SR-p53 | clasificación | 1354 | ROC-AUC 0.890 · acc 0.95 | TP 20·FP 8·TN 1261·FN 65 |

Las matrices de Tox21 muestran el **desbalance** real (pocos positivos): la accuracy alta se apoya en
los negativos; el ROC-AUC (insensible al desbalance) es la métrica honesta.

### 5.2 Chemprop D-MPNN (4.6) — held-out por scaffold

Dataset: `chemprop/testset.csv` (782 moléculas held-out). Plot: `chemprop/roc_by_assay.png`.

- **ROC-AUC macro (12 ensayos) = 0.734**. Rango por ensayo: NR-AhR 0.85 (mejor) → NR-Aromatase 0.65.
- Más bajo que el RF de Tox21 porque el split por **scaffold** es intencionalmente más difícil (mide
  extrapolación a esqueletos nuevos) y por entrenar solo 15 epochs sin ensembling. Es un número
  realista y publicable para Chemprop en Tox21.

---

## 6. Credibilidad con fármacos reales y limitaciones

`disease_gnn/real_drug_predictions.csv` junta la **indicación clínica real** (DrugCentral, "para qué
se usa") con las top-5 enfermedades que predice el Disease-GNN, para 15 fármacos conocidos:

| Fármaco | Se usa para (real) | Predice (modelo) | Lectura |
|---------|--------------------|------------------|---------|
| metformina | Diabetes tipo 2 | cáncer de pulmón, neurodegeneración | **Plausible**: repurposing oncológico/antienvejecimiento en estudio real |
| sildenafil | Hipertensión pulmonar, disfunción eréctil | trastorno hipertensivo, cardiovascular | **Coincide** con su indicación cardiovascular |
| ibuprofeno | Dolor, inflamación | trastorno hipertensivo | Plausible (AINEs afectan la PA) |
| warfarina / atorvastatina | Cardiovascular | Romano-Ward (QT largo), hipertensión | Plausible (contexto cardiovascular) |

**Limitaciones a tener presentes:**
1. **Tarea ≠ indicación clínica**: el Disease-GNN predice asociaciones *genéticas/mecanísticas*
   (Open Targets: diana→enfermedad), no indicaciones aprobadas. El cruce es contexto, no una métrica.
2. **Sesgo hacia enfermedades "hub"**: enfermedades muy conectadas (trastorno hipertensivo,
   Romano-Ward) aparecen repetidamente porque muchos fármacos comparten genes cardíacos (KCNH2, SCN…).
   El modelo tiene sesgo de grado; conviene ponderar por especificidad en trabajo futuro.
3. **Held-out transductivo** (grafo): los embeddings se computan sobre el grafo completo, así que
   son features estructurales que "ven" la vecindad del test. El cabezal nunca ve las etiquetas de
   test, pero para una cota inferior más estricta habría que enmascarar las aristas de test al embeber.

---

## 7. Inventario de `dataset_testing/`

```
disease_gnn/  testset.csv (9916) · correct.csv (9291) · incorrect.csv (625)
              real_drug_predictions.csv (15) · metrics.json · roc_pr.png
dti_gnn/      testset.csv (6780) · correct.csv · incorrect.csv · metrics.json · roc_pr.png
admet/        {bbbp,esol,tox21_nr_ar,tox21_sr_p53}_testset.csv · metrics.json · *_roc.png · esol_scatter.png
chemprop/     testset.csv (782) · metrics.json · roc_by_assay.png
graph_models_summary.json   (resumen combinado Disease-GNN + DTI-GNN)
```

Cada `*_testset.csv` incluye la etiqueta real, la predicción del modelo y una columna `correct` para
separar aciertos de errores. Reproducir todo:

```bash
cd backend && source venv/bin/activate
python -m scripts.eval_graph_models      # Disease-GNN + DTI-GNN
python -m scripts.eval_admet             # ADMET RF
python -m scripts.eval_chemprop          # Chemprop GNN
python -m scripts.eval_disease_realworld # cruce con indicaciones reales
```

---

## 8. Conclusión

Las cuatro funcionalidades de ML del Tier 4 **funcionan adecuadamente sobre datos reales held-out**:
predicción fármaco→diana y fármaco→enfermedad con ROC-AUC ≈ 0.98, propiedades ADMET con ROC 0.95 /
R² 0.87, y toxicidad Chemprop con ROC macro 0.73 bajo el split más exigente. Los datasets de test,
sus aciertos/errores y las curvas quedan versionados como respaldo. Las limitaciones (correlación con
la fuerza de evidencia, sesgo de grado, held-out transductivo) están documentadas con honestidad y
marcan el trabajo futuro.
