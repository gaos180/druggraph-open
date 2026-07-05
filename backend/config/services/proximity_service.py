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
import random
import statistics

from config.services.neo4j_service import _session
from config.services.propagation_service import string_network_loaded

log = logging.getLogger(__name__)

MAX_DEPTH = 6          # cota de saltos (la mayoría de proteínas están a ≤5 en STRING)
MAX_GENES = 60         # cota por conjunto
DEFAULT_N_RANDOM = 50  # permutaciones del modelo nulo (compromiso coste/estabilidad)
BIN_MIN = 100          # tamaño mínimo de bin de grado para el muestreo emparejado


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


# ── Significancia por modelo nulo que preserva el grado (Guney et al. 2016) ───────
# La proximidad cruda d_c NO es interpretable por sí sola: los hubs del interactoma la
# deprimen trivialmente (están cerca de casi todo). Para saber si dos módulos están
# MÁS cerca de lo esperable por azar, se compara d_c(A,B) contra una distribución nula
# de d_c(A, B_rand) donde B_rand son genes aleatorios con el MISMO grado que B.

def _gene_degrees(session) -> dict:
    """{gen: grado} en el interactoma STRING (una sola pasada)."""
    return {
        r["name"]: r["deg"]
        for r in session.run(
            "MATCH (g:Gene) RETURN g.name AS name, count{(g)--()} AS deg"
        )
    }


def _degree_bins(degrees: dict, bin_min: int = BIN_MIN) -> dict:
    """Mapa gen → lista de genes de grado similar (bins acumulativos de ≥ bin_min genes).

    Los bins no cortan a mitad de un valor de grado, para que el muestreo sea justo.
    """
    ordered = sorted(degrees.items(), key=lambda kv: kv[1])
    names = [n for n, _ in ordered]
    n = len(names)

    # 1) fronteras de bins de ≥ bin_min, sin partir un grupo del mismo grado
    bounds = []
    i = 0
    while i < n:
        j = min(i + bin_min, n)
        while j < n and ordered[j][1] == ordered[j - 1][1]:
            j += 1
        bounds.append((i, j))
        i = j
    # 2) si el último bin quedó subdimensionado, fusiónalo con el anterior
    if len(bounds) >= 2 and (bounds[-1][1] - bounds[-1][0]) < bin_min:
        (s_prev, _), (_, e_last) = bounds[-2], bounds[-1]
        bounds[-2:] = [(s_prev, e_last)]

    gene_to_bin: dict = {}
    for s, e in bounds:
        bin_names = names[s:e]
        for g in bin_names:
            gene_to_bin[g] = bin_names
    return gene_to_bin


def _zscore_pvalue(d_obs, null_vals: list):
    """z-score y p-valor empírico (una cola: d_obs MENOR que el nulo ⇒ cercanía significativa)."""
    null = [v for v in null_vals if v is not None]
    if d_obs is None or len(null) < 2:
        return None, None, None, None
    mu = statistics.fmean(null)
    sd = statistics.pstdev(null)
    z = (d_obs - mu) / sd if sd > 0 else 0.0
    # +1 en numerador/denominador: p-valor empírico conservador (nunca 0).
    p = (sum(1 for v in null if v <= d_obs) + 1) / (len(null) + 1)
    return round(z, 3), round(p, 4), round(mu, 3), round(sd, 3)


def proximity_significance(genes_a: list, genes_b: list,
                           n_random: int = DEFAULT_N_RANDOM, seed: int | None = None) -> dict:
    """Proximidad d_c(A→B) con significancia por modelo nulo que preserva el grado.

    Mantiene A fijo (p.ej. el módulo de dianas del fármaco consultado) y randomiza B con
    genes de igual grado, `n_random` veces, para obtener z-score y p-valor. Devuelve el d_c
    observado más `z_score`, `p_value`, media/desv. del nulo y las permutaciones efectivas.
    """
    rng = random.Random(seed)
    obs = closest_proximity(genes_a, genes_b)
    d_obs = obs.get("d_c")
    a_present = obs.get("genes_a_used") or []
    b_present = obs.get("genes_b_used") or []
    result = dict(obs)
    result.update({"z_score": None, "p_value": None, "null_mean": None,
                   "null_std": None, "n_random_effective": 0})
    if d_obs is None or not a_present or not b_present:
        return result

    with _session() as session:
        if not string_network_loaded(session):
            raise ProximityUnavailable("Red STRING no cargada (ejecuta load_string_network.py).")
        degrees = _gene_degrees(session)
        gene_to_bin = _degree_bins(degrees)

        # Genes de B que existen en el mapa de grado (deberían ser todos los presentes)
        b_bins = [gene_to_bin.get(g) for g in b_present]
        if any(bin_ is None for bin_ in b_bins):
            b_present = [g for g, bin_ in zip(b_present, b_bins) if bin_]
            b_bins = [bin_ for bin_ in b_bins if bin_]
        if not b_present:
            return result

        null_vals = []
        for _ in range(max(2, n_random)):
            b_rand = list({rng.choice(bin_) for bin_ in b_bins})  # muestreo emparejado por grado
            mean, _per, _reach = _mean_nearest_within(session, a_present, b_rand)
            null_vals.append(mean)

    z, p, mu, sd = _zscore_pvalue(d_obs, null_vals)
    result.update({
        "z_score": z, "p_value": p, "null_mean": mu, "null_std": sd,
        "n_random_effective": len([v for v in null_vals if v is not None]),
        "significant": bool(z is not None and z <= -1.6),  # ~p<0.05 una cola
    })
    return result


def _mean_nearest_within(session, sources: list, targets: list):
    """d_c(sources→targets) reutilizando la sesión abierta (para el bucle del nulo)."""
    per, dists = [], []
    for s in sources:
        d = _nearest_distance(session, s, targets)
        per.append({"gene": s, "distance": d})
        if d is not None:
            dists.append(d)
    mean = round(sum(dists) / len(dists), 3) if dists else None
    return mean, per, len(dists)
