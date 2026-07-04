"""
proximity_service.py — Proximidad de red (network medicine) sobre la red STRING.

Implementa la métrica de "proximidad más cercana" d_c de Guney et al. (2016):
para dos conjuntos de genes A y B, promedia —para cada gen de A— la distancia de
camino más corto al gen más cercano de B en el interactoma (:Gene)-[:STRING_ASSOC].
Módulos cercanos ⇒ d_c baja ⇒ mayor probabilidad de relación funcional (base
principled para reposicionamiento y DDI).

Usa `shortestPath` de Cypher (no requiere GDS) sobre la red STRING ya cargada por
scripts/load_string_network.py. Traversal no dirigido, acotado en profundidad.

Requiere: red STRING cargada (:Gene)-[:STRING_ASSOC]->(:Gene).
"""

import logging

from config.services.neo4j_service import _session
from config.services.propagation_service import string_network_loaded

log = logging.getLogger(__name__)

MAX_DEPTH = 6          # cota de saltos (la mayoría de proteínas están a ≤5 en STRING)
MAX_GENES = 60         # cota por conjunto


class ProximityUnavailable(RuntimeError):
    """Red STRING no cargada."""
    pass


def _present_genes(session, genes: list[str]) -> list[str]:
    rows = session.run(
        "MATCH (g:Gene) WHERE g.name IN $genes RETURN collect(g.name) AS p", genes=genes
    ).single()["p"]
    return rows or []


def _nearest_distance(session, source: str, targets: list[str]) -> int | None:
    """Distancia (nº de saltos) del gen source al target más cercano; None si inalcanzable."""
    if source in targets:
        return 0
    rec = session.run(
        """
        MATCH (a:Gene {name: $source}), (b:Gene)
        WHERE b.name IN $targets AND b.name <> $source
        MATCH p = shortestPath((a)-[:STRING_ASSOC*..%d]-(b))
        RETURN min(length(p)) AS d
        """ % MAX_DEPTH,
        source=source, targets=targets,
    ).single()
    return rec["d"] if rec and rec["d"] is not None else None


def closest_proximity(genes_a: list[str], genes_b: list[str]) -> dict:
    """
    Calcula d_c(A→B): promedio de la distancia más corta de cada gen de A al gen
    más cercano de B. Devuelve también la versión simétrica (media de A→B y B→A).

    Retorna:
        {
          "available": bool,
          "d_c": float | None,            # A→B (menor = más cercano)
          "d_c_symmetric": float | None,  # media de A→B y B→A
          "genes_a_used": [str], "genes_b_used": [str],
          "reachable_a": int, "coverage_a": float,
          "per_source": [ {gene, distance} ]   # distancia de cada gen de A (None si inalcanzable)
        }
    """
    a = list(dict.fromkeys(g for g in genes_a if g))[:MAX_GENES]
    b = list(dict.fromkeys(g for g in genes_b if g))[:MAX_GENES]
    if not a or not b:
        return {"available": False, "d_c": None, "d_c_symmetric": None,
                "genes_a_used": [], "genes_b_used": [], "reachable_a": 0,
                "coverage_a": 0.0, "per_source": []}

    with _session() as session:
        if not string_network_loaded(session):
            raise ProximityUnavailable(
                "Red STRING no cargada (ejecuta load_string_network.py)."
            )

        a_present = _present_genes(session, a)
        b_present = _present_genes(session, b)
        if not a_present or not b_present:
            return {"available": True, "d_c": None, "d_c_symmetric": None,
                    "genes_a_used": a_present, "genes_b_used": b_present,
                    "reachable_a": 0, "coverage_a": 0.0, "per_source": []}

        def _mean_nearest(sources, targets):
            per = []
            dists = []
            for s in sources:
                d = _nearest_distance(session, s, targets)
                per.append({"gene": s, "distance": d})
                if d is not None:
                    dists.append(d)
            mean = round(sum(dists) / len(dists), 3) if dists else None
            return mean, per, len(dists)

        d_ab, per_source, reachable = _mean_nearest(a_present, b_present)
        d_ba, _, _ = _mean_nearest(b_present, a_present)

    if d_ab is not None and d_ba is not None:
        d_sym = round((d_ab + d_ba) / 2, 3)
    else:
        d_sym = d_ab if d_ab is not None else d_ba

    return {
        "available": True,
        "d_c": d_ab,
        "d_c_symmetric": d_sym,
        "genes_a_used": a_present,
        "genes_b_used": b_present,
        "reachable_a": reachable,
        "coverage_a": round(reachable / len(a_present), 3) if a_present else 0.0,
        "per_source": per_source,
    }
