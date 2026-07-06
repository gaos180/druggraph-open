#!/usr/bin/env python3
"""
eval_admet.py — Evaluación held-out de los modelos ADMET (RandomForest, Tier 4.3).

Reproduce EXACTAMENTE el split de entrenamiento (train_test_split test_size=0.2, random_state=42)
por endpoint, de modo que el 20% evaluado es un held-out real: el modelo se entrenó solo con el
80%. Carga el .joblib entrenado, predice en el test y reporta:
  - clasificación (BBBP, Tox21): ROC-AUC, matriz de confusión @0.5, accuracy.
  - regresión (ESOL): RMSE, R², correlación (Pearson) predicho vs. medido.
Guarda el dataset de test con SMILES + valor real + predicho + acierto en ../dataset_testing/admet/.
"""
import csv
import json
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import (roc_auc_score, confusion_matrix, mean_squared_error, r2_score,
                             roc_curve)
from scipy.stats import pearsonr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config.services.admet_service import ENDPOINTS, MODEL_DIR, featurize

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "dataset_testing", "admet")
DATA_DIR = "/tmp/moleculenet"
DATASETS = {
    "tox21":   ("tox21.csv.gz", "smiles"),
    "bbbp":    ("BBBP.csv", "smiles"),
    "delaney": ("delaney-processed.csv", "smiles"),
}


def _load(name):
    import pandas as pd
    fn, col = DATASETS[name]
    return pd.read_csv(os.path.join(DATA_DIR, fn)), col


def main():
    os.makedirs(OUT, exist_ok=True)
    import pandas as pd  # noqa
    cache = {}
    summary = {}

    for ep, meta in ENDPOINTS.items():
        model_path = os.path.join(MODEL_DIR, f"{ep}.joblib")
        if not os.path.exists(model_path):
            print(f"[{ep}] modelo ausente, se omite."); continue
        ds, col = meta["dataset"], meta["column"]
        if ds not in cache:
            cache[ds] = _load(ds)
        df, smiles_col = cache[ds]
        if col not in df.columns:
            print(f"[{ep}] columna {col} ausente, se omite."); continue

        smiles, X, y = [], [], []
        for _, row in df.iterrows():
            label = row[col]
            if label is None or (isinstance(label, float) and np.isnan(label)):
                continue
            feats = featurize(str(row[smiles_col]))
            if feats is None:
                continue
            smiles.append(str(row[smiles_col])); X.append(feats); y.append(float(label))
        X = np.array(X); y = np.array(y); smiles = np.array(smiles)

        strat = y if meta["task"] == "classification" else None
        idx = np.arange(len(y))
        _, ite = train_test_split(idx, test_size=0.2, random_state=42, stratify=strat)
        Xte, yte, ste = X[ite], y[ite], smiles[ite]

        model = joblib.load(model_path)
        rows, metrics = [], {"endpoint": ep, "label": meta["label"], "task": meta["task"],
                             "n_test": int(len(ite))}

        if meta["task"] == "classification":
            proba = model.predict_proba(Xte)[:, 1]
            pred = (proba >= 0.5).astype(int)
            roc = float(roc_auc_score(yte, proba))
            tn, fp, fn, tp = confusion_matrix(yte, pred).ravel()
            metrics.update({"roc_auc": round(roc, 4),
                            "confusion_at_0.5": {"tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn)},
                            "accuracy": round(float((tp + tn) / len(yte)), 4)})
            header = ["smiles", "true", "prob", "predicted", "correct"]
            for smi, t, pr, pd_ in zip(ste, yte, proba, pred):
                rows.append([smi, int(t), round(float(pr), 4), int(pd_), int(pd_ == t)])
            # ROC plot
            fpr, tpr, _ = roc_curve(yte, proba)
            fig, ax = plt.subplots(figsize=(4.5, 4))
            ax.plot(fpr, tpr, label=f"AUC={roc:.3f}"); ax.plot([0, 1], [0, 1], "k--", lw=0.7)
            ax.set_title(f"ADMET {ep} ROC"); ax.set_xlabel("FPR"); ax.set_ylabel("TPR"); ax.legend()
            fig.tight_layout(); fig.savefig(os.path.join(OUT, f"{ep}_roc.png"), dpi=110); plt.close(fig)
        else:
            pred = model.predict(Xte)
            rmse = float(np.sqrt(mean_squared_error(yte, pred)))
            r2 = float(r2_score(yte, pred))
            pear = float(pearsonr(yte, pred)[0])
            metrics.update({"rmse": round(rmse, 4), "r2": round(r2, 4), "pearson": round(pear, 4)})
            header = ["smiles", "true", "predicted", "abs_error"]
            for smi, t, pr in zip(ste, yte, pred):
                rows.append([smi, round(float(t), 4), round(float(pr), 4), round(abs(t - pr), 4)])
            # scatter real vs predicho
            fig, ax = plt.subplots(figsize=(4.5, 4))
            ax.scatter(yte, pred, s=8, alpha=0.4)
            lims = [min(yte.min(), pred.min()), max(yte.max(), pred.max())]
            ax.plot(lims, lims, "k--", lw=0.7); ax.set_title(f"ESOL real vs predicho (R²={r2:.3f})")
            ax.set_xlabel("logS real"); ax.set_ylabel("logS predicho")
            fig.tight_layout(); fig.savefig(os.path.join(OUT, f"{ep}_scatter.png"), dpi=110); plt.close(fig)

        with open(os.path.join(OUT, f"{ep}_testset.csv"), "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(header); w.writerows(rows)
        summary[ep] = metrics
        print(f"[{ep}] {metrics}")

    with open(os.path.join(OUT, "metrics.json"), "w") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    print("Listo. dataset_testing/admet/")


if __name__ == "__main__":
    main()
