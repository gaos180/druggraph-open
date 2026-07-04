#!/usr/bin/env python3
"""
populate_chemberta_embeddings.py — Precalcula embeddings ChemBERTa de los :Drug (Tier 3.2).

Delega en config.services.chemberta_index.populate_missing (misma lógica idempotente que
usa el autostart del backend): calcula el embedding ChemBERTa (768-dim) de cada :Drug con
SMILES que aún no lo tenga, lo guarda como `d.chemberta` y crea el índice vectorial nativo
de Neo4j (`drug_chemberta`, coseno) para búsqueda kNN.

Es idempotente: correrlo de nuevo solo procesa lo que falte.

USO (desde backend/, con el venv activo):
    python -m scripts.populate_chemberta_embeddings
    python -m scripts.populate_chemberta_embeddings --limit 200   # subconjunto (debug)

Dependencias: torch + transformers (pesadas, opcionales). Neo4j 5.11+ para vector index.
"""

import argparse
import logging
import os
import sys

import django

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("chemberta")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from config.services import chemberta_service           # noqa: E402
from config.services.chemberta_index import populate_missing, count_status  # noqa: E402


def main():
    if not chemberta_service.EMBEDDINGS_OK:
        log.error("torch/transformers no están instalados. Instala: pip install torch transformers")
        sys.exit(1)

    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="máximo de fármacos pendientes a procesar (0 = todos)")
    args = ap.parse_args()

    log.info("Estado inicial: %s", count_status())
    result = populate_missing(limit=args.limit)
    log.info("Resultado: %s", result)
    log.info("Estado final: %s", count_status())


if __name__ == "__main__":
    main()
