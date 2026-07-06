#!/usr/bin/env python3
"""
eval_graph_models.py — Evaluación held-out de las GNN de grafo (Disease-GNN 4.7, DTI-GNN 4.2).

Protocolo (estándar de link-prediction transductivo sobre knowledge graphs):
  1. Embeddings FastRP del subgrafo Drug↔Target↔Disease (features estructurales no supervisadas).
  2. Positivos = aristas reales (ASSOCIATED_WITH para enfermedad, TARGETS para diana).
  3. Split 80/20 a nivel de arista (semilla fija). El cabezal (regresión logística) se entrena
     SOLO con el 80% + negativos muestreados; se evalúa en el 20% held-out + negativos.
  4. Métricas en test: ROC-AUC, PR-AUC (AP), matriz de confusión @0.5, y correlación
     (probabilidad del modelo vs. score de Open Targets) para el caso enfermedad.
  5. Guarda el dataset de test con nombres reales (aciertos y errores por separado) + curvas.

Salida en ../dataset_testing/{disease_gnn,dti_gnn}/.
"""

import csv
import json
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import (average_precision_score, roc_auc_score, roc_curve,
                             precision_recall_curve, confusion_matrix)
from scipy.stats import pearsonr, spearmanr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config.services.neo4j_service import _session

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "dataset_testing")
SEED = 7
np.random.seed(SEED)


def _fastrp():
    """Embeddings FastRP del subgrafo + info por nodo (elementId → vec, meta)."""
    g = "eval_emb"
    with _session() as s:
        s.run("CALL gds.graph.drop($g, false)", g=g)
        s.run("CALL gds.graph.project($g, ['Drug','Target','Disease'], "
              "{ALL:{type:'*', orientation:'UNDIRECTED'}})", g=g)
        rows = s.run(
            "CALL gds.fastRP.stream($g, {embeddingDimension:128, randomSeed:42}) "
            "YIELD nodeId, embedding "
            "WITH gds.util.asNode(nodeId) AS n, embedding "
            "RETURN elementId(n) AS key, labels(n) AS labels, embedding, "
            "n.drugbank_id AS drug, n.name AS name, n.disease_id AS disease, "
            "n.drugbank_target_id AS target, n.gene_name AS gene, n.uniprot_id AS uniprot",
            g=g).data()
        s.run("CALL gds.graph.drop($g, false)", g=g)
    emb, info = {}, {}
    for r in rows:
        emb[r["key"]] = np.array(r["embedding"], dtype="float32")
        info[r["key"]] = r
    return emb, info


def _train_eval(pos, emb, info, out_dir, extra_cols, name_fn, corr_col=None):
    """Split, entrena LP, evalúa held-out; escribe CSVs + curvas; devuelve métricas."""
    os.makedirs(out_dir, exist_ok=True)
    pos = [p for p in pos if p[0] in emb and p[1] in emb]
    pos_set = {(a, b) for a, b, *_ in pos}
    drug_keys = [k for k, v in info.items() if "Drug" in v["labels"]]
    dst_label = "Disease" if "disease" in extra_cols else "Target"
    dst_keys = [k for k, v in info.items() if dst_label in v["labels"]]

    # negativos: mismo nº que positivos, pares inexistentes
    rng = np.random.default_rng(SEED)
    neg = []
    while len(neg) < len(pos):
        a = drug_keys[rng.integers(len(drug_keys))]
        b = dst_keys[rng.integers(len(dst_keys))]
        if (a, b) not in pos_set:
            neg.append((a, b))

    def feat(a, b):
        return emb[a] * emb[b]

    # índices de split sobre positivos y negativos por separado (estratificado por clase)
    pos_tr, pos_te = train_test_split(pos, test_size=0.2, random_state=SEED)
    neg_tr, neg_te = train_test_split(neg, test_size=0.2, random_state=SEED)

    Xtr = np.array([feat(a, b) for a, b, *_ in pos_tr] + [feat(a, b) for a, b in neg_tr])
    ytr = np.array([1] * len(pos_tr) + [0] * len(neg_tr))
    clf = LogisticRegression(max_iter=1000, class_weight="balanced").fit(Xtr, ytr)

    test_rows = [(a, b, meta, 1) for (a, b, *meta) in pos_te] + [(a, b, [], 0) for (a, b) in neg_te]
    Xte = np.array([feat(a, b) for a, b, _m, _y in test_rows])
    yte = np.array([y for *_r, y in test_rows])
    proba = clf.predict_proba(Xte)[:, 1]
    pred = (proba >= 0.5).astype(int)

    roc = float(roc_auc_score(yte, proba))
    ap = float(average_precision_score(yte, proba))
    tn, fp, fn, tp = confusion_matrix(yte, pred).ravel()

    # correlación prob vs score OT (solo positivos con score)
    corr = {}
    if corr_col:
        xs, ys = [], []
        for (a, b, meta, y), pr in zip(test_rows, proba):
            if y == 1 and meta and meta[0] is not None:
                xs.append(float(meta[0])); ys.append(float(pr))
        if len(xs) > 10:
            corr = {"pearson": round(float(pearsonr(xs, ys)[0]), 4),
                    "spearman": round(float(spearmanr(xs, ys)[0]), 4), "n": len(xs)}

    # ── guardar dataset de test con nombres reales ──
    header = ["drug_id", "drug_name"] + extra_cols + ["label", "model_prob", "predicted", "correct"]
    all_rows, correct_rows, incorrect_rows = [], [], []
    for (a, b, meta, y), pr, pd_ in zip(test_rows, proba, pred):
        row = name_fn(info[a], info[b], meta) + [y, round(float(pr), 4), int(pd_), int(pd_ == y)]
        all_rows.append(row)
        (correct_rows if pd_ == y else incorrect_rows).append(row)

    for fname, rows in [("testset.csv", all_rows), ("correct.csv", correct_rows),
                        ("incorrect.csv", incorrect_rows)]:
        with open(os.path.join(out_dir, fname), "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(header); w.writerows(rows)

    # ── curvas ROC + PR ──
    fpr, tpr, _ = roc_curve(yte, proba)
    prec, rec, _ = precision_recall_curve(yte, proba)
    fig, ax = plt.subplots(1, 2, figsize=(9, 4))
    ax[0].plot(fpr, tpr, label=f"AUC={roc:.3f}"); ax[0].plot([0, 1], [0, 1], "k--", lw=0.7)
    ax[0].set_title("ROC"); ax[0].set_xlabel("FPR"); ax[0].set_ylabel("TPR"); ax[0].legend()
    ax[1].plot(rec, prec, label=f"AP={ap:.3f}", color="darkorange")
    ax[1].set_title("Precision-Recall"); ax[1].set_xlabel("Recall"); ax[1].set_ylabel("Precision"); ax[1].legend()
    fig.suptitle(os.path.basename(out_dir)); fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "roc_pr.png"), dpi=110); plt.close(fig)

    metrics = {
        "model": os.path.basename(out_dir), "protocol": "transductive held-out (80/20)",
        "n_positives": len(pos), "n_test": len(test_rows),
        "roc_auc": round(roc, 4), "pr_auc_ap": round(ap, 4),
        "confusion_at_0.5": {"tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn)},
        "accuracy": round(float((tp + tn) / len(yte)), 4),
        "precision": round(float(tp / (tp + fp)) if (tp + fp) else 0, 4),
        "recall": round(float(tp / (tp + fn)) if (tp + fn) else 0, 4),
        "correlation_prob_vs_ot_score": corr,
        "n_correct": len(correct_rows), "n_incorrect": len(incorrect_rows),
    }
    with open(os.path.join(out_dir, "metrics.json"), "w") as fh:
        json.dump(metrics, fh, indent=2, ensure_ascii=False)
    print(f"[{metrics['model']}] ROC={roc:.4f} AP={ap:.4f} acc={metrics['accuracy']} "
          f"corr={corr} (test n={len(test_rows)})")
    return metrics


def eval_disease(emb, info):
    with _session() as s:
        pos = s.run(
            "MATCH (d:Drug)-[r:ASSOCIATED_WITH]->(x:Disease) "
            "RETURN elementId(d) AS dk, elementId(x) AS xk, r.score AS score, r.gene AS gene"
        ).data()
    pos = [(p["dk"], p["xk"], p["score"], p["gene"]) for p in pos]

    def name_fn(di, xi, meta):
        score = meta[0] if meta else None
        gene = meta[1] if len(meta) > 1 else ""
        return [di["drug"] or "", di["name"] or "", xi["disease"] or "", xi["name"] or "",
                gene or "", "" if score is None else round(float(score), 4)]

    return _train_eval(pos, emb, info, os.path.join(OUT, "disease_gnn"),
                       ["disease_id", "disease_name", "gene", "ot_score"], name_fn, corr_col=True)


def eval_dti(emb, info):
    with _session() as s:
        pos = s.run(
            "MATCH (d:Drug)-[:TARGETS]->(t:Target) "
            "RETURN elementId(d) AS dk, elementId(t) AS tk"
        ).data()
    pos = [(p["dk"], p["tk"]) for p in pos]

    def name_fn(di, ti, meta):
        return [di["drug"] or "", di["name"] or "", ti["target"] or "", ti["name"] or "",
                ti["gene"] or "", ti["uniprot"] or ""]

    return _train_eval(pos, emb, info, os.path.join(OUT, "dti_gnn"),
                       ["target_id", "target_name", "gene", "uniprot"], name_fn)


def main():
    print("Calculando embeddings FastRP del knowledge graph…")
    emb, info = _fastrp()
    print(f"  {len(emb)} nodos embebidos.")
    summary = {"disease_gnn": eval_disease(emb, info), "dti_gnn": eval_dti(emb, info)}
    with open(os.path.join(OUT, "graph_models_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    print("Listo. Datasets + métricas en dataset_testing/{disease_gnn,dti_gnn}/")


if __name__ == "__main__":
    main()
