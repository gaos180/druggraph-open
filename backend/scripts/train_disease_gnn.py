#!/usr/bin/env python3
"""
train_disease_gnn.py — Entrena la GNN de repurposing fármaco→enfermedad (Tier 4.7, BiomedGPS).

Extiende la DTI-GNN (4.2) al par Drug→Disease sobre el knowledge graph. Aprende embeddings FastRP
del subgrafo Drug↔Target↔Disease + un cabezal Link Prediction, reporta AUCPR/AP, escribe las
top-K predicciones como (:Drug)-[:PREDICTED_DISEASE {score}]->(:Disease) y persiste métricas en
Mongo `model_metrics`. Idempotente.

USO (desde backend/, con el venv activo):
    python -m scripts.train_disease_gnn
    python -m scripts.train_disease_gnn --top-k 30 --neg-ratio 2

Prerequisitos: capa de enfermedad cargada (scripts/load_disease_associations.py) + GDS + sklearn.
"""

import argparse
import logging
import os

import django

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("disease_gnn")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from config.services import disease_gnn_service  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--neg-ratio", type=int, default=1)
    ap.add_argument("--top-k", type=int, default=20)
    ap.add_argument("--candidate-cap", type=int, default=100000)
    args = ap.parse_args()

    if not disease_gnn_service.DTI_LIBS_OK:
        log.error("Faltan deps: pip install scikit-learn numpy")
        raise SystemExit(1)

    try:
        result = disease_gnn_service.train(
            neg_ratio=args.neg_ratio, top_k=args.top_k, candidate_cap=args.candidate_cap,
        )
    except disease_gnn_service.DiseaseGNNUnavailable as exc:
        log.error("No se pudo entrenar (GDS/datos): %s", exc)
        raise SystemExit(2)

    log.info("Resultado: %s", result)


if __name__ == "__main__":
    main()
