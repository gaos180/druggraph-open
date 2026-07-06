#!/usr/bin/env python3
"""
materialize_gds.py — Materializa las métricas de red GDS como propiedades de nodo.

Louvain (comunidades), PageRank y grado son caros porque REPROYECTAN el grafo Drug↔Target en
cada request. Si los datos del grafo no cambian, no hace falta recalcularlos: este script los
corre UNA vez y escribe `communityId`, `pagerank` y `degree` en cada :Drug/:Target. A partir de
ahí `centrality()`/`communities()` LEEN la propiedad (Cypher barato, sin proyección ni GDS) en vez
de recomputar en cada llamada — menos RAM del proceso Neo4j y respuestas instantáneas.

Reejecutar SOLO cuando cambien los datos del grafo (nueva ingesta de fármacos/dianas). Idempotente.

USO (desde backend/, con el venv activo):
    python -m scripts.materialize_gds

Prerequisitos: plugin GDS instalado en Neo4j + grafo Drug/Target cargado. Correr en serie (no
concurrente con otras escrituras a Neo4j, que es frágil con poca RAM — ver docs/DATASET_STATE.md).
"""

import logging
import os

import django

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("materialize_gds")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from config.services import gds_service  # noqa: E402


def main():
    try:
        result = gds_service.materialize_graph_metrics()
    except gds_service.GDSUnavailable as exc:
        log.error("GDS no disponible: %s", exc)
        raise SystemExit(2)
    log.info("Materialización completada: %s", result)
    log.info("Ahora /api/drugs/gds/communities/ y /gds/centrality/ leen las propiedades "
             "(usa ?fresh=true para forzar recálculo).")


if __name__ == "__main__":
    main()
