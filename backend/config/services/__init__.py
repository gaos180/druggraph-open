"""
config.services — Servicios singleton de acceso a datos y APIs externas.

Reúne las conexiones a las bases (MongoDB, Neo4j) y los clientes de APIs/bioinformática
(BLAST, GDS, KEGG, STRING, CTD, SwissTargetPrediction, UniProt, g:Profiler, propagación
de efectos, sandbox estructural). Las vistas no abren conexiones: las obtienen de aquí.
"""

from .mongo import get_db
from .neo4j_service import get_driver, get_drug_graph

__all__ = ["get_db", "get_driver", "get_drug_graph"]
