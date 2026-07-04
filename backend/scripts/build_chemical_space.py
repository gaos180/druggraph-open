#!/usr/bin/env python3
"""
build_chemical_space.py — Construye el mapa 2D del espacio químico (Tier 4.1).

Ajusta UMAP (2D) + HDBSCAN sobre los embeddings ChemBERTa poblados en :Drug.chemberta,
persiste el modelo (backend/models/chemical_space/umap.joblib) para poder ubicar
moléculas nuevas, y escribe la nube resultante en la colección Mongo `chemical_space`.

Es idempotente: sobreescribe la colección y el .joblib en cada corrida.

USO (desde backend/, con el venv activo):
    python -m scripts.build_chemical_space
    python -m scripts.build_chemical_space --min-cluster-size 20 --n-neighbors 20

Prerequisitos:
  - Embeddings ChemBERTa poblados (scripts/populate_chemberta_embeddings.py).
  - Deps: pip install umap-learn hdbscan joblib
"""

import argparse
import logging
import os
import sys

import django

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("chemical_space")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from config.services import chemical_space_service  # noqa: E402


def main():
    if not chemical_space_service.SPACE_OK:
        log.error("umap-learn/hdbscan/joblib no instalados. Instala: pip install umap-learn hdbscan joblib")
        sys.exit(1)

    ap = argparse.ArgumentParser()
    ap.add_argument("--n-neighbors", type=int, default=15, help="UMAP n_neighbors")
    ap.add_argument("--min-dist", type=float, default=0.1, help="UMAP min_dist")
    ap.add_argument("--min-cluster-size", type=int, default=15, help="HDBSCAN min_cluster_size")
    args = ap.parse_args()

    log.info("Construyendo mapa de espacio químico…")
    result = chemical_space_service.build(
        n_neighbors=args.n_neighbors,
        min_dist=args.min_dist,
        min_cluster_size=args.min_cluster_size,
    )
    log.info("Resultado: %s", result)
    if not result.get("available"):
        sys.exit(2)


if __name__ == "__main__":
    main()
