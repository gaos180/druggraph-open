"""
gds_service.py — Análisis de red con Neo4j Graph Data Science (GDS) para DrugGraph.

Tres familias de análisis sobre el grafo fármaco-target:

  1. CENTRALIDAD  — qué nodos son más influyentes/conectados.
       · PageRank y grado sobre :Target  → dianas "hub" promiscuas (posibles off-targets)
       · PageRank y grado sobre :Drug     → fármacos multi-diana

  2. COMUNIDADES  — Louvain sobre el grafo bipartito Drug↔Target
       → módulos de fármacos y dianas funcionalmente relacionados

  3. PREDICCIÓN DE ENLACES — vecinos comunes / Adamic-Adar
       → sugiere interacciones fármaco→target NO documentadas (repurposing in silico)

Ubicación sugerida: config/gds_service.py

Requisitos:
  - Plugin GDS instalado en Neo4j 5 (Graph Data Science library).
  - Grafo cargado con drugbank_to_cypher.py (nodos :Drug, :Target y relaciones).

Diseño:
  - Toda proyección se nombra de forma única y se elimina en un finally,
    incluso si la consulta falla, para no dejar grafos en memoria.
  - Cada función captura neo4j_exc.ClientError (procedimiento gds.* no
    encontrado) y lanza GDSUnavailable, que la vista traduce a HTTP 503.
  - Límites de resultados para proteger la RAM del proceso Django.
"""

import logging
import uuid

from neo4j import exceptions as neo4j_exc

from config.services.neo4j_service import _session

log = logging.getLogger(__name__)


class GDSUnavailable(RuntimeError):
    """Se lanza cuando el plugin GDS no está instalado o disponible."""
    pass


# ── Límites de seguridad ────────────────────────────────────────────────────────
DEFAULT_TOP_N      = 50
MAX_TOP_N          = 200
MAX_COMMUNITIES    = 100
MAX_PREDICTIONS    = 100


# ══════════════════════════════════════════════════════════════════════════════
# UTILIDADES DE PROYECCIÓN
# ══════════════════════════════════════════════════════════════════════════════

def _unique_graph_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _gds_available(session) -> bool:
    """Comprueba si el plugin GDS responde."""
    try:
        rec = session.run("RETURN gds.version() AS v").single()
        return rec is not None
    except neo4j_exc.ClientError:
        return False
    except Exception as e:
        log.debug('GDS no disponible: %s', e)
        return False


def _drop_graph(session, graph_name: str):
    """Elimina una proyección si existe (failOnMissing=false)."""
    try:
        session.run("CALL gds.graph.drop($g, false)", g=graph_name)
    except Exception as exc:
        log.warning("No se pudo eliminar la proyección %s: %s", graph_name, exc)


# Proyección bipartita Drug→Target.
# Se usa una relación homogénea virtual "CONNECTS" tratada como NO dirigida
# (UNDIRECTED) para que algoritmos como Louvain y degree funcionen sobre el
# grafo fármaco-target sin importar el tipo semántico de la arista.
def _project_drug_target(session, graph_name: str, undirected: bool = True):
    orientation = "UNDIRECTED" if undirected else "NATURAL"
    cypher = """
        CALL gds.graph.project.cypher(
            $graph_name,
            'MATCH (n) WHERE n:Drug OR n:Target
             RETURN id(n) AS id, labels(n) AS labels',
            'MATCH (d:Drug)-[]->(t:Target)
             RETURN id(d) AS source, id(t) AS target, "CONNECTS" AS type',
            { validateRelationships: false }
        )
        YIELD graphName, nodeCount, relationshipCount
        RETURN graphName, nodeCount, relationshipCount
    """
    # La orientación se controla en el algoritmo, no en la proyección Cypher,
    # vía el parámetro relationshipTypes/orientation cuando aplique.
    return session.run(cypher, graph_name=graph_name).single()


# ══════════════════════════════════════════════════════════════════════════════
# 1. CENTRALIDAD
# ══════════════════════════════════════════════════════════════════════════════

def centrality(
    node_label: str = "Target",
    metric: str = "pagerank",
    top_n: int = DEFAULT_TOP_N,
) -> dict:
    """
    Calcula centralidad sobre nodos :Target o :Drug.

    Parámetros:
        node_label : "Target" | "Drug"  — sobre qué nodos rankear.
        metric     : "pagerank" | "degree"
        top_n      : número de nodos top a devolver.

    Retorna:
        {
            "node_label": str,
            "metric": str,
            "results": [
                {
                    "id": str,            # drugbank_target_id o drugbank_id
                    "name": str,
                    "uniprot_id": str,    # solo para Target
                    "organism": str,      # solo para Target
                    "score": float,       # PageRank o grado
                }
            ]
        }
    """
    if node_label not in ("Target", "Drug"):
        raise ValueError("node_label debe ser 'Target' o 'Drug'")
    if metric not in ("pagerank", "degree"):
        raise ValueError("metric debe ser 'pagerank' o 'degree'")

    top_n = max(1, min(top_n, MAX_TOP_N))
    graph_name = _unique_graph_name("central")

    with _session() as session:
        if not _gds_available(session):
            raise GDSUnavailable("El plugin GDS no está instalado en Neo4j.")

        try:
            _project_drug_target(session, graph_name, undirected=True)

            if metric == "pagerank":
                algo_cypher = """
                    CALL gds.pageRank.stream($graph_name, {
                        maxIterations: 20,
                        dampingFactor: 0.85
                    })
                    YIELD nodeId, score
                    WITH gds.util.asNode(nodeId) AS node, score
                    WHERE $label IN labels(node)
                    RETURN node, score
                    ORDER BY score DESC
                    LIMIT $top_n
                """
            else:  # degree
                algo_cypher = """
                    CALL gds.degree.stream($graph_name)
                    YIELD nodeId, score
                    WITH gds.util.asNode(nodeId) AS node, score
                    WHERE $label IN labels(node)
                    RETURN node, score
                    ORDER BY score DESC
                    LIMIT $top_n
                """

            rows = session.run(
                algo_cypher, graph_name=graph_name, label=node_label, top_n=top_n
            )

            results = []
            for row in rows:
                node = row["node"]
                props = dict(node)
                if node_label == "Target":
                    results.append({
                        "id":         props.get("drugbank_target_id", ""),
                        "name":       props.get("name", ""),
                        "uniprot_id": props.get("uniprot_id", ""),
                        "organism":   props.get("organism", ""),
                        "score":      round(float(row["score"]), 4),
                    })
                else:
                    results.append({
                        "id":     props.get("drugbank_id", ""),
                        "name":   props.get("name", ""),
                        "type":   props.get("type", ""),
                        "score":  round(float(row["score"]), 4),
                    })

        except neo4j_exc.ClientError as exc:
            raise GDSUnavailable(f"Error GDS: {exc}")
        finally:
            _drop_graph(session, graph_name)

    return {"node_label": node_label, "metric": metric, "results": results}


# ══════════════════════════════════════════════════════════════════════════════
# 2. COMUNIDADES (Louvain)
# ══════════════════════════════════════════════════════════════════════════════

def communities(
    max_communities: int = MAX_COMMUNITIES,
    min_size: int = 2,
    members_per_community: int = 20,
) -> dict:
    """
    Detecta comunidades en el grafo bipartito Drug↔Target con Louvain.

    Parámetros:
        max_communities       : tope de comunidades a devolver.
        min_size              : tamaño mínimo de comunidad para incluirla.
        members_per_community : máx. de miembros listados por comunidad.

    Retorna:
        {
            "community_count": int,
            "communities": [
                {
                    "community_id": int,
                    "size": int,
                    "drug_count": int,
                    "target_count": int,
                    "members": [
                        { "kind": "Drug"|"Target", "id": str, "name": str }
                    ]
                }
            ]
        }
    """
    max_communities = max(1, min(max_communities, MAX_COMMUNITIES))
    graph_name = _unique_graph_name("louvain")

    with _session() as session:
        if not _gds_available(session):
            raise GDSUnavailable("El plugin GDS no está instalado en Neo4j.")

        try:
            _project_drug_target(session, graph_name, undirected=True)

            # Louvain en streaming, agrupando miembros por communityId
            cypher = """
                CALL gds.louvain.stream($graph_name, {
                    maxLevels: 10,
                    maxIterations: 10
                })
                YIELD nodeId, communityId
                WITH communityId, gds.util.asNode(nodeId) AS node
                WITH communityId,
                     collect({
                        kind: CASE WHEN 'Drug' IN labels(node) THEN 'Drug' ELSE 'Target' END,
                        id:   coalesce(node.drugbank_id, node.drugbank_target_id, ''),
                        name: coalesce(node.name, '')
                     }) AS members
                WITH communityId, members, size(members) AS sz
                WHERE sz >= $min_size
                RETURN communityId, sz, members
                ORDER BY sz DESC
                LIMIT $max_communities
            """

            rows = session.run(
                cypher,
                graph_name=graph_name,
                min_size=min_size,
                max_communities=max_communities,
            )

            communities_out = []
            for row in rows:
                members = row["members"]
                drug_count   = sum(1 for m in members if m["kind"] == "Drug")
                target_count = sum(1 for m in members if m["kind"] == "Target")
                communities_out.append({
                    "community_id": row["communityId"],
                    "size":         row["sz"],
                    "drug_count":   drug_count,
                    "target_count": target_count,
                    "members":      members[:members_per_community],
                })

        except neo4j_exc.ClientError as exc:
            raise GDSUnavailable(f"Error GDS: {exc}")
        finally:
            _drop_graph(session, graph_name)

    return {
        "community_count": len(communities_out),
        "communities": communities_out,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. PREDICCIÓN DE ENLACES (repurposing in silico)
# ══════════════════════════════════════════════════════════════════════════════

def predict_links_for_drug(
    drugbank_id: str,
    top_n: int = DEFAULT_TOP_N,
    method: str = "adamic_adar",
) -> dict:
    """
    Sugiere targets a los que un fármaco PODRÍA unirse pero que NO están
    documentados, usando similitud topológica.

    Lógica: encuentra targets que comparten muchos "fármacos vecinos" con los
    targets actuales del fármaco — es decir, targets en el mismo vecindario
    de la red que el fármaco aún no toca.

    Parámetros:
        drugbank_id : fármaco de interés.
        top_n       : número de predicciones.
        method      : "adamic_adar" | "common_neighbors"

    Retorna:
        {
            "drugbank_id": str,
            "drug_name": str,
            "method": str,
            "current_target_count": int,
            "predictions": [
                {
                    "target_id": str,
                    "target_name": str,
                    "uniprot_id": str,
                    "organism": str,
                    "score": float,           # Adamic-Adar o # vecinos comunes
                    "shared_via_drugs": int,  # fármacos puente
                }
            ]
        }

    NOTA: esta predicción usa una fórmula topológica directa en Cypher
    (no requiere proyección GDS), pero se documenta aquí como parte del
    módulo de análisis de red. Si el plugin GDS está disponible, la función
    `predict_links_gds` ofrece la variante con gds.linkprediction.*.
    """
    if method not in ("adamic_adar", "common_neighbors"):
        raise ValueError("method debe ser 'adamic_adar' o 'common_neighbors'")

    top_n = max(1, min(top_n, MAX_PREDICTIONS))

    # Adamic-Adar: sum(1 / log(grado(fármaco_puente))) sobre fármacos que conectan
    # los targets actuales con targets candidatos. Penaliza puentes muy promiscuos.
    if method == "adamic_adar":
        score_expr = "sum(1.0 / log(bridgeDegree + 2.718281828))"
    else:
        score_expr = "count(DISTINCT bridgeDrug)"

    cypher = f"""
        MATCH (d:Drug {{drugbank_id: $drugbank_id}})
        OPTIONAL MATCH (d)-[]->(currentTarget:Target)
        WITH d, collect(DISTINCT currentTarget) AS currentTargets

        // Targets candidatos: alcanzables vía otros fármacos que comparten
        // targets con d, pero que d aún no toca.
        UNWIND currentTargets AS ct
        MATCH (ct)<-[]-(bridgeDrug:Drug)-[]->(candidate:Target)
        WHERE bridgeDrug <> d
          AND NOT candidate IN currentTargets
        WITH d, candidate, bridgeDrug,
             count{{ (bridgeDrug)-[]->(:Target) }} AS bridgeDegree
        WITH d, candidate,
             {score_expr} AS score,
             count(DISTINCT bridgeDrug) AS sharedViaDrugs
        RETURN candidate.drugbank_target_id AS target_id,
               candidate.name               AS target_name,
               candidate.uniprot_id         AS uniprot_id,
               candidate.organism           AS organism,
               score,
               sharedViaDrugs               AS shared_via_drugs
        ORDER BY score DESC
        LIMIT $top_n
    """

    with _session() as session:
        # Datos del fármaco
        drug_info = session.run(
            """
            MATCH (d:Drug {drugbank_id: $drugbank_id})
            OPTIONAL MATCH (d)-[]->(t:Target)
            RETURN d.name AS name, count(DISTINCT t) AS target_count
            """,
            drugbank_id=drugbank_id,
        ).single()

        if not drug_info:
            return {}

        rows = session.run(cypher, drugbank_id=drugbank_id, top_n=top_n).data()

    predictions = [
        {
            "target_id":        r["target_id"] or "",
            "target_name":      r["target_name"] or "",
            "uniprot_id":       r["uniprot_id"] or "",
            "organism":         r["organism"] or "",
            "score":            round(float(r["score"]), 4),
            "shared_via_drugs": r["shared_via_drugs"],
        }
        for r in rows
    ]

    return {
        "drugbank_id":          drugbank_id,
        "drug_name":            drug_info["name"],
        "method":               method,
        "current_target_count": drug_info["target_count"],
        "predictions":          predictions,
    }


def predict_links_gds(top_n: int = DEFAULT_TOP_N) -> dict:
    """
    Variante global con GDS: usa la función gds.alpha.linkprediction.adamicAdar
    sobre la proyección bipartita para puntuar pares (Drug, Target) no
    conectados a escala de todo el grafo.

    Requiere GDS instalado. Si no, lanza GDSUnavailable.

    Retorna los pares (drug, target) con mayor score Adamic-Adar global.
    """
    top_n = max(1, min(top_n, MAX_PREDICTIONS))
    graph_name = _unique_graph_name("linkpred")

    with _session() as session:
        if not _gds_available(session):
            raise GDSUnavailable("El plugin GDS no está instalado en Neo4j.")

        try:
            _project_drug_target(session, graph_name, undirected=True)

            # Usa gds.alpha.linkprediction.adamicAdar como función sobre pares
            # candidatos generados por vecinos de vecinos.
            cypher = """
                MATCH (d:Drug)-[]->(:Target)<-[]-(:Drug)-[]->(candidate:Target)
                WHERE NOT (d)-[]->(candidate)
                WITH DISTINCT d, candidate
                LIMIT 5000
                WITH d, candidate,
                     gds.alpha.linkprediction.adamicAdar(d, candidate) AS score
                WHERE score > 0
                RETURN d.drugbank_id          AS drugbank_id,
                       d.name                 AS drug_name,
                       candidate.drugbank_target_id AS target_id,
                       candidate.name         AS target_name,
                       candidate.organism     AS organism,
                       score
                ORDER BY score DESC
                LIMIT $top_n
            """
            rows = session.run(cypher, top_n=top_n).data()

        except neo4j_exc.ClientError as exc:
            raise GDSUnavailable(f"Error GDS linkprediction: {exc}")
        finally:
            _drop_graph(session, graph_name)

    predictions = [
        {
            "drugbank_id": r["drugbank_id"] or "",
            "drug_name":   r["drug_name"] or "",
            "target_id":   r["target_id"] or "",
            "target_name": r["target_name"] or "",
            "organism":    r["organism"] or "",
            "score":       round(float(r["score"]), 4),
        }
        for r in rows
    ]

    return {"method": "adamic_adar_gds", "predictions": predictions}
