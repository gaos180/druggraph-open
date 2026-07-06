#!/usr/bin/env python3
"""
eval_chemprop.py — Evaluación held-out del GNN Chemprop de toxicidad (Tier 4.6).

Chemprop entrenó con split por SCAFFOLD y dejó sus predicciones sobre el test held-out en
model_0/test_predictions.csv (moléculas cuyo esqueleto no está en train → evaluación honesta).
Este script une esas predicciones con las etiquetas reales de Tox21 (por SMILES) y calcula el
ROC-AUC por cada uno de los 12 ensayos + el macro-promedio. Guarda el dataset etiquetado y una
gráfica de barras de ROC por ensayo en ../dataset_testing/chemprop/.
"""
import csv
import json
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config.services.chemprop_service import MODEL_DIR, TOX21_TASKS, TASK_LABELS

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "dataset_testing", "chemprop")
PRED_CSV = os.path.join(MODEL_DIR, "tox21", "model_0", "test_predictions.csv")
TRUTH_CSV = "/tmp/moleculenet/tox21_chemprop.csv"


def _canon(smi):
    from rdkit import Chem
    m = Chem.MolFromSmiles(str(smi))
    return Chem.MolToSmiles(m) if m else str(smi)


def main():
    os.makedirs(OUT, exist_ok=True)
    preds = pd.read_csv(PRED_CSV)
    truth = pd.read_csv(TRUTH_CSV)
    # unir por SMILES canónico (chemprop puede recanonizar)
    preds["_k"] = preds["smiles"].map(_canon)
    truth["_k"] = truth["smiles"].map(_canon)
    truth_by_k = truth.drop_duplicates("_k").set_index("_k")

    per_assay, rows_out = {}, []
    header = ["smiles"] + [f"{t}_true" for t in TOX21_TASKS] + [f"{t}_prob" for t in TOX21_TASKS]
    aucs = []
    for _, pr in preds.iterrows():
        k = pr["_k"]
        if k not in truth_by_k.index:
            continue
        tr = truth_by_k.loc[k]
        row = [pr["smiles"]]
        row += [("" if pd.isna(tr[t]) else int(tr[t])) for t in TOX21_TASKS]
        row += [round(float(pr[t]), 4) for t in TOX21_TASKS]
        rows_out.append(row)

    with open(os.path.join(OUT, "testset.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(header); w.writerows(rows_out)

    # ROC por ensayo (sobre el held-out, ignorando etiquetas faltantes)
    for t in TOX21_TASKS:
        y, p = [], []
        for _, pr in preds.iterrows():
            k = pr["_k"]
            if k not in truth_by_k.index:
                continue
            val = truth_by_k.loc[k, t]
            if pd.isna(val):
                continue
            y.append(int(val)); p.append(float(pr[t]))
        if len(set(y)) == 2 and len(y) >= 10:
            auc = float(roc_auc_score(y, p))
            per_assay[t] = {"roc_auc": round(auc, 4), "label": TASK_LABELS.get(t, t), "n": len(y)}
            aucs.append(auc)

    macro = round(float(np.mean(aucs)), 4) if aucs else None
    metrics = {"model": "chemprop-dmpnn", "protocol": "scaffold-split held-out",
               "n_test_molecules": len(rows_out), "macro_roc_auc": macro, "per_assay": per_assay}
    with open(os.path.join(OUT, "metrics.json"), "w") as fh:
        json.dump(metrics, fh, indent=2, ensure_ascii=False)

    # barras ROC por ensayo
    if per_assay:
        ts = list(per_assay.keys()); vals = [per_assay[t]["roc_auc"] for t in ts]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(range(len(ts)), vals, color="teal")
        ax.axhline(macro, color="crimson", ls="--", lw=1, label=f"macro={macro}")
        ax.axhline(0.5, color="gray", ls=":", lw=0.8, label="azar")
        ax.set_xticks(range(len(ts))); ax.set_xticklabels(ts, rotation=60, ha="right", fontsize=8)
        ax.set_ylabel("ROC-AUC (test)"); ax.set_title("Chemprop Tox21 — ROC-AUC por ensayo (held-out)")
        ax.set_ylim(0, 1); ax.legend()
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "roc_by_assay.png"), dpi=110); plt.close(fig)

    print(f"[chemprop] macro ROC-AUC held-out = {macro} sobre {len(rows_out)} moléculas, "
          f"{len(per_assay)} ensayos evaluables.")


if __name__ == "__main__":
    main()
