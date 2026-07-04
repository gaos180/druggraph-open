#!/usr/bin/env python3
"""
train_dti_gnn.py — Entrena la GNN de predicción fármaco-diana (Tier 4.2).

Aprende embeddings de grafo (GraphSAGE, fallback FastRP) con Neo4j GDS + un cabezal de Link
Prediction (regresión logística) con muestreo negativo; reporta AUCPR/AP en test, escribe las
top-K predicciones como (:Drug)-[:PREDICTED_TARGET {score}]->(:Target) y persiste las métricas
en la colección Mongo `model_metrics`. Idempotente (reescribe las aristas del modelo).

USO (desde backend/, con el venv activo):
    python -m scripts.train_dti_gnn
    python -m scripts.train_dti_gnn --method fastrp --top-k 30

Prerequisitos: plugin GDS instalado en Neo4j + grafo Drug/Target cargado + scikit-learn.
"""

import argparse
import logging
import os

import django

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("dti_gnn")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from config.services import dti_gnn_service  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=["graphsage", "fastrp"], default="graphsage")
    ap.add_argument("--neg-ratio", type=int, default=1, help="negativos por positivo")
    ap.add_argument("--top-k", type=int, default=20, help="predicciones a escribir por fármaco")
    ap.add_argument("--candidate-cap", type=int, default=50000)
    args = ap.parse_args()

    if not dti_gnn_service.DTI_LIBS_OK:
        log.error("Faltan deps: pip install scikit-learn numpy")
        raise SystemExit(1)

    try:
        result = dti_gnn_service.train(
            method=args.method, neg_ratio=args.neg_ratio,
            top_k=args.top_k, candidate_cap=args.candidate_cap,
        )
    except dti_gnn_service.DTIUnavailable as exc:
        log.error("No se pudo entrenar (GDS/datos): %s", exc)
        raise SystemExit(2)

    log.info("Resultado: %s", result)


if __name__ == "__main__":
    main()
