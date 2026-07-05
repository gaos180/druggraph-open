"""
propagation_service.py — Propagación de efectos en cadena sobre la red PPI local.

Dada una lista de genes "semilla" (los targets directos de un fármaco/compuesto),
propaga la perturbación por la red STRING cargada localmente
(:Gene)-[:STRING_ASSOC {score}]->(:Gene) usando Personalized PageRank de GDS.

El resultado es un ranking de genes por "alcance del efecto": qué tan fuertemente
llega la perturbación del fármaco a cada nodo de la red a través de las
interacciones proteína-proteína. Es la magnitud de difusión (no dirigida / sin
signo); el signo activación/inhibición vendría de fuentes dirigidas (KEGG KGML,
Reactome, CTD) en una fase posterior.

Requiere:
  - Plugin GDS en Neo4j.
  - Red STRING cargada con load_string_network.py.
"""

import logging
import uuid
from collections import defaultdict

from neo4j import exceptions as neo4j_exc
from config.services.neo4j_service import _session

log = logging.getLogger(__name__)

DEFAULT_TOP_N = 40
MAX_TOP_N = 150
MAX_SEEDS = 60


class PropagationUnavailable(RuntimeError):
    """GDS no disponible o red STRING no cargada."""
    pass


def _gds_available(session) -> bool:
    try:
        return session.run("RETURN gds.version() AS v").single() is not None
    except Exception as e:
        log.debug('GDS no disponible: %s', e)
        return False


def string_network_loaded(session=None) -> bool:
    """True si la red STRING (:Gene)-[:STRING_ASSOC] está cargada."""
    def _check(s):
        return s.run("MATCH ()-[r:STRING_ASSOC]->() RETURN count(r) > 0 AS ok").single()["ok"]
    if session is not None:
        return _check(session)
    with _session() as s:
        return _check(s)


def regulatory_network_loaded(session=None) -> bool:
    """True si la red dirigida con signo (:Gene)-[:REGULATES] está cargada."""
    def _check(s):
        return s.run("MATCH ()-[r:REGULATES]->() RETURN count(r) > 0 AS ok").single()["ok"]
    if session is not None:
        return _check(session)
    with _session() as s:
        return _check(s)


# ── Propagación DIRIGIDA con SIGNO (red regulatoria KEGG) ────────────────────────

MAX_HOPS = 4
FRONTIER_CAP = 800  # poda por salto para acotar explosión en hubs

# Mapeo acción farmacológica → signo de la perturbación inicial en la diana.
# Un fármaco que INHIBE/ANTAGONIZA su diana la perturba negativamente (−1); uno que la
# ACTIVA/AGONIZA, positivamente (+1). Permite semillas con signo POR DIANA en vez de
# asumir uniformemente que el fármaco inhibe todas sus dianas (recomendación del informe
# de biología de sistemas — el dato `actions` ya viaja en la arista (:Drug)-[:TARGETS]).
_NEGATIVE_ACTIONS = {
    "inhibitor", "antagonist", "blocker", "negative modulator", "inverse agonist",
    "suppressor", "downregulator", "inactivator", "antisense", "gating inhibitor",
    "channel blocker", "negative allosteric modulator", "weak inhibitor",
}
_POSITIVE_ACTIONS = {
    "agonist", "activator", "inducer", "positive modulator", "partial agonist",
    "stimulator", "potentiator", "upregulator", "opener",
    "positive allosteric modulator",
}


def sign_for_action(actions) -> int | None:
    """Deriva el signo de perturbación (−1/+1) de la(s) acción(es) del fármaco sobre la diana.

    Devuelve None si no hay señal clara (acción desconocida, ausente o mixta), para que el
    llamador aplique el signo por defecto. `actions` puede ser un string o un iterable.
    """
    if not actions:
        return None
    if isinstance(actions, str):
        actions = [actions]
    neg = pos = 0
    for a in actions:
        s = str(a).strip().lower()
        if s in _NEGATIVE_ACTIONS:
            neg += 1
        elif s in _POSITIVE_ACTIONS:
            pos += 1
    if neg and not pos:
        return -1
    if pos and not neg:
        return 1
    return None  # ambiguo/desconocido


def propagate_signed(
    seed_genes: list[str],
    seed_sign: int = -1,
    max_hops: int = 3,
    decay: float = 0.5,
    top_n: int = 40,
    seed_signs: dict | None = None,
) -> dict:
    """
    Propaga el efecto con SIGNO y DIRECCIÓN por la red regulatoria de KEGG
    (:Gene)-[:REGULATES {sign}]->(:Gene). Difusión en K pasos: el efecto de un
    nodo se transmite a sus sucesores multiplicado por el signo de la arista y
    atenuado por `decay` en cada salto.

    Parámetros:
        seed_sign : signo por defecto de la perturbación inicial en las dianas.
                    -1 = el fármaco INHIBE sus dianas (caso típico). +1 = las activa.
        seed_signs: mapa opcional {gen: ±1} con el signo POR DIANA (derivado de la
                    acción del fármaco vía `sign_for_action`). Para los genes ausentes
                    del mapa se usa `seed_sign`. Evita asumir que el fármaco inhibe
                    TODAS sus dianas cuando en realidad agoniza algunas.
        max_hops  : profundidad de la cascada (1..MAX_HOPS).
        decay     : atenuación por salto (0..1).

    Retorna:
        {
          "available": bool,
          "mode": "directed",
          "seed_sign": int, "max_hops": int,
          "seeds_used": [str], "seeds_missing": [str],
          "downstream": [
            { "gene", "effect" (signed float), "magnitude", "sign" (+1/-1), "is_target" }
          ]
        }
    """
    seeds = list(dict.fromkeys(g for g in seed_genes if g))[:MAX_SEEDS]
    max_hops = max(1, min(int(max_hops), MAX_HOPS))
    top_n = max(1, min(top_n, MAX_TOP_N))
    seed_sign = 1 if int(seed_sign) >= 0 else -1

    if not seeds:
        return {"available": False, "mode": "directed", "downstream": [],
                "seeds_used": [], "seeds_missing": [], "seed_sign": seed_sign, "max_hops": max_hops}

    with _session() as session:
        if not regulatory_network_loaded(session):
            return {"available": False, "mode": "directed", "downstream": [],
                    "seeds_used": [], "seeds_missing": seeds, "seed_sign": seed_sign,
                    "max_hops": max_hops,
                    "reason": "Red regulatoria KEGG no cargada (ejecuta load_kegg_regulatory.py)."}

        # Adyacencia dirigida con signo
        adj: dict = defaultdict(list)
        for r in session.run("MATCH (a:Gene)-[r:REGULATES]->(b:Gene) RETURN a.name AS a, b.name AS b, r.sign AS s"):
            adj[r["a"]].append((r["b"], int(r["s"])))

        target_genes = {
            row["g"] for row in session.run(
                "MATCH (t:Target) WHERE t.gene_name IS NOT NULL RETURN DISTINCT t.gene_name AS g"
            )
        }

    seeds_used = [g for g in seeds if g in adj]
    seeds_missing = [g for g in seeds if g not in adj]
    if not seeds_used:
        return {"available": True, "mode": "directed", "downstream": [],
                "seeds_used": [], "seeds_missing": seeds_missing, "seed_sign": seed_sign,
                "max_hops": max_hops}

    # Difusión en K pasos (signed). Signo inicial POR DIANA: usa seed_signs[g] si se
    # proporcionó (derivado de la acción del fármaco), si no el seed_sign uniforme.
    def _seed_value(g: str) -> float:
        if seed_signs and g in seed_signs and seed_signs[g] is not None:
            return 1.0 if int(seed_signs[g]) >= 0 else -1.0
        return float(seed_sign)

    reach: dict = defaultdict(float)
    frontier: dict = {g: _seed_value(g) for g in seeds_used}
    seed_set = set(seeds_used)

    for _hop in range(max_hops):
        nxt: dict = defaultdict(float)
        for g1, v in frontier.items():
            for g2, sgn in adj.get(g1, ()):  # sucesores
                nxt[g2] += v * sgn * decay
        if not nxt:
            break
        for g2, val in nxt.items():
            reach[g2] += val
        # poda: conservar los de mayor |valor| para el siguiente salto
        if len(nxt) > FRONTIER_CAP:
            top = sorted(nxt.items(), key=lambda kv: abs(kv[1]), reverse=True)[:FRONTIER_CAP]
            frontier = dict(top)
        else:
            frontier = nxt

    downstream = []
    for gene, eff in reach.items():
        if gene in seed_set or abs(eff) < 1e-9:
            continue
        downstream.append({
            "gene": gene,
            "effect": round(eff, 5),
            "magnitude": round(abs(eff), 5),
            "sign": 1 if eff > 0 else -1,
            "is_target": gene in target_genes,
        })
    downstream.sort(key=lambda d: d["magnitude"], reverse=True)
    shown = downstream[:top_n]

    # Subgrafo regulatorio entre semillas y genes mostrados (para el grafo dirigido)
    node_names = set(seeds_used) | {d["gene"] for d in shown}
    edges = []
    seen_e = set()
    for g1 in node_names:
        for g2, sgn in adj.get(g1, ()):  # sucesores
            if g2 in node_names and (g1, g2) not in seen_e:
                seen_e.add((g1, g2))
                edges.append({"source": g1, "target": g2, "sign": sgn})

    return {
        "available": True,
        "mode": "directed",
        "seed_sign": seed_sign,
        "per_seed_sign": bool(seed_signs),   # True si se usó signo por diana (acción)
        "max_hops": max_hops,
        "seeds_used": seeds_used,
        "seeds_missing": seeds_missing,
        "downstream": shown,
        "edges": edges,
    }


def propagate(seed_genes: list[str], top_n: int = DEFAULT_TOP_N, damping: float = 0.6) -> dict:
    """
    Propaga desde los genes semilla por la red STRING y devuelve los genes más
    alcanzados (efecto en cadena por difusión).

    Retorna:
        {
          "available": bool,
          "seeds_used": [str],          # semillas presentes en la red
          "seeds_missing": [str],       # semillas sin nodo en STRING
          "damping": float,
          "downstream": [               # genes NO semilla, ordenados por alcance
            { "gene": str, "score": float, "is_target": bool }
          ],
          "seed_scores": [              # las semillas con su propio score (contexto)
            { "gene": str, "score": float, "is_target": bool }
          ]
        }
    """
    seeds = list(dict.fromkeys(g for g in seed_genes if g))[:MAX_SEEDS]
    top_n = max(1, min(top_n, MAX_TOP_N))

    if not seeds:
        return {"available": False, "seeds_used": [], "seeds_missing": [],
                "downstream": [], "seed_scores": [], "damping": damping}

    graph_name = f"prop_{uuid.uuid4().hex[:8]}"

    with _session() as session:
        if not _gds_available(session):
            raise PropagationUnavailable("El plugin GDS no está instalado en Neo4j.")
        if not string_network_loaded(session):
            return {"available": False, "seeds_used": [], "seeds_missing": seeds,
                    "downstream": [], "seed_scores": [], "damping": damping,
                    "reason": "Red STRING no cargada (ejecuta load_string_network.py)."}

        # Semillas presentes en la red
        present = session.run(
            "MATCH (g:Gene) WHERE g.name IN $seeds RETURN collect(g.name) AS p", seeds=seeds
        ).single()["p"]
        missing = [g for g in seeds if g not in present]
        if not present:
            return {"available": True, "seeds_used": [], "seeds_missing": missing,
                    "downstream": [], "seed_scores": [], "damping": damping}

        try:
            # Proyección nativa del subgrafo Gene / STRING_ASSOC (no dirigido, ponderado)
            session.run(
                """
                CALL gds.graph.project(
                    $g, 'Gene',
                    { STRING_ASSOC: { orientation: 'UNDIRECTED', properties: 'score' } }
                )
                """,
                g=graph_name,
            )

            seed_ids = session.run(
                "MATCH (g:Gene) WHERE g.name IN $seeds RETURN collect(id(g)) AS ids",
                seeds=present,
            ).single()["ids"]

            rows = session.run(
                """
                CALL gds.pageRank.stream($g, {
                    maxIterations: 30,
                    dampingFactor: $damping,
                    sourceNodes: $ids,
                    relationshipWeightProperty: 'score'
                })
                YIELD nodeId, score
                WITH gds.util.asNode(nodeId) AS node, score
                WHERE score > 0
                RETURN node.name AS gene, score,
                       EXISTS { MATCH (t:Target) WHERE t.gene_name = node.name } AS is_target
                ORDER BY score DESC
                LIMIT $limit
                """,
                g=graph_name, damping=damping, ids=seed_ids, limit=top_n + len(present),
            ).data()
        except neo4j_exc.ClientError as exc:
            raise PropagationUnavailable(f"Error GDS: {exc}")
        finally:
            try:
                session.run("CALL gds.graph.drop($g, false)", g=graph_name)
            except Exception as e:
                log.warning('No se pudo eliminar proyección GDS %s: %s', graph_name, e)

    seed_set = set(present)
    downstream = []
    seed_scores = []
    for r in rows:
        item = {"gene": r["gene"], "score": round(float(r["score"]), 5), "is_target": bool(r["is_target"])}
        if r["gene"] in seed_set:
            seed_scores.append(item)
        else:
            downstream.append(item)

    return {
        "available": True,
        "seeds_used": present,
        "seeds_missing": missing,
        "damping": damping,
        "downstream": downstream[:top_n],
        "seed_scores": seed_scores,
    }
