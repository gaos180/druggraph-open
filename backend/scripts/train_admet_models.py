#!/usr/bin/env python3
"""
train_admet_models.py — Entrena los modelos ADMET supervisados (Tier 4.3).

Descarga datasets públicos de MoleculeNet (Tox21, BBBP, ESOL) desde el S3 de DeepChem,
featuriza con la MISMA función que la inferencia (config.services.admet_service.featurize),
entrena un RandomForest por endpoint, reporta la métrica de test (ROC-AUC / RMSE) y guarda
los modelos (backend/models/admet/<endpoint>.joblib) + metrics.json.

USO (desde backend/, con el venv activo):
    python -m scripts.train_admet_models
    python -m scripts.train_admet_models --data-dir /ruta/csv-locales   # usa CSVs ya descargados

Deps: scikit-learn, joblib, pandas, requests, rdkit.
"""

import argparse
import json
import logging
import os

import django

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("admet_train")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from config.services import admet_service  # noqa: E402
from config.services.admet_service import ENDPOINTS, MODEL_DIR, METRICS_PATH, featurize  # noqa: E402

# dataset → (URL de descarga, columna SMILES)
DATASETS = {
    "tox21":   ("https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/tox21.csv.gz", "smiles"),
    "bbbp":    ("https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/BBBP.csv", "smiles"),
    "delaney": ("https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/delaney-processed.csv", "smiles"),
}


def _load_dataset(name: str, data_dir: str):
    import pandas as pd
    url, smiles_col = DATASETS[name]
    local = os.path.join(data_dir, os.path.basename(url))
    if not os.path.exists(local):
        import requests
        log.info("Descargando %s…", url)
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        with open(local, "wb") as fh:
            fh.write(r.content)
    df = pd.read_csv(local)
    return df, smiles_col


def main():
    if not admet_service.ADMET_OK:
        log.error("Faltan deps: pip install scikit-learn joblib pandas requests")
        raise SystemExit(1)

    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/moleculenet", help="cache de CSVs de MoleculeNet")
    ap.add_argument("--test-size", type=float, default=0.2)
    args = ap.parse_args()

    os.makedirs(args.data_dir, exist_ok=True)
    os.makedirs(MODEL_DIR, exist_ok=True)

    import numpy as np
    import joblib
    from sklearn.model_selection import train_test_split
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.metrics import roc_auc_score, mean_squared_error

    ds_cache: dict = {}
    metrics: dict = {}

    for name, meta in ENDPOINTS.items():
        ds_name, col = meta["dataset"], meta["column"]
        if ds_name not in ds_cache:
            ds_cache[ds_name] = _load_dataset(ds_name, args.data_dir)
        df, smiles_col = ds_cache[ds_name]

        if col not in df.columns:
            log.warning("Columna %s no está en %s — se omite %s.", col, ds_name, name)
            continue

        X, y = [], []
        for _, row in df.iterrows():
            label = row[col]
            if label is None or (isinstance(label, float) and np.isnan(label)):
                continue
            feats = featurize(str(row[smiles_col]))
            if feats is None:
                continue
            X.append(feats)
            y.append(float(label))
        if len(X) < 50:
            log.warning("Muy pocos ejemplos válidos para %s (%d) — se omite.", name, len(X))
            continue

        X = np.array(X)
        y = np.array(y)
        stratify = y if meta["task"] == "classification" else None
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=args.test_size,
                                              random_state=42, stratify=stratify)

        if meta["task"] == "classification":
            model = RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=42,
                                           class_weight="balanced")
            model.fit(Xtr, ytr)
            proba = model.predict_proba(Xte)[:, 1]
            auc = float(roc_auc_score(yte, proba))
            metrics[name] = {"roc_auc": round(auc, 4), "n_train": len(Xtr), "n_test": len(Xte)}
            log.info("%s — ROC-AUC test = %.4f (n_train=%d)", name, auc, len(Xtr))
        else:
            model = RandomForestRegressor(n_estimators=300, n_jobs=-1, random_state=42)
            model.fit(Xtr, ytr)
            pred = model.predict(Xte)
            rmse = float(np.sqrt(mean_squared_error(yte, pred)))
            metrics[name] = {"rmse": round(rmse, 4), "n_train": len(Xtr), "n_test": len(Xte)}
            log.info("%s — RMSE test = %.4f (n_train=%d)", name, rmse, len(Xtr))

        joblib.dump(model, os.path.join(MODEL_DIR, f"{name}.joblib"))

    with open(METRICS_PATH, "w") as fh:
        json.dump(metrics, fh, indent=2)
    log.info("Modelos guardados en %s. Métricas: %s", MODEL_DIR, metrics)


if __name__ == "__main__":
    main()
