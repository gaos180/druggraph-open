"""
_similarity.py — Similitud estructural (Tanimoto) y de comportamiento (GDS/Jaccard).

- structural_similarity: Tanimoto del fingerprint sandbox contra fármacos reales.
- behavioral_*: Jaccard por identidad proteica (uniprot_id/gene_name) sobre targets
  compartidos, con variante GDS nodeSimilarity y fallback.

NOTA: structural_similarity requiere que los nodos (:Drug) tengan la propiedad
`fingerprint` precalculada (mismo formato que compute_fingerprint, string FPS de
DataStructs.BitVectToFPSText). La puebla scripts/populate_fingerprints.py. Mientras
no exista, structural_similarity() devuelve [] y el pipeline cae a "jaccard"/"none"
sin romper el endpoint.
"""

import logging

from neo4j import exceptions as neo4j_exc

from config.services.neo4j_service import _session
from ._chemistry import RDKIT_OK, tanimoto_similarity

log = logging.getLogger(__name__)

# ── Configuración ──────────────────────────────────────────────────────────────
MAX_SIMILAR_RESULTS    = 30        # tope de fármacos similares devueltos
MAX_GDS_CANDIDATE_POOL = 20_000    # todos los fármacos con fingerprint (~12k actualmente)


def _get_real_drugs_with_fingerprints(limit: int) -> list[dict]:
    """
    Obtiene fármacos reales del grafo que tengan fingerprint precalculado.

    Si la propiedad d.fingerprint no existe en ningún nodo, devuelve [] y la
    similitud estructural queda vacía sin romper el flujo.
    """
    cypher = """
        MATCH (d:Drug)
        WHERE d.fingerprint IS NOT NULL AND d.fingerprint <> ''
        RETURN d.drugbank_id AS drugbank_id,
               d.name        AS name,
               d.fingerprint AS fingerprint
        LIMIT $limit
    """
    try:
        with _session() as session:
            return session.run(cypher, limit=limit).data()
    except Exception as exc:
        log.error("Error obteniendo fingerprints reales: %s", exc)
        return []


def structural_similarity(sandbox_fingerprint: str, limit: int = MAX_SIMILAR_RESULTS) -> list[dict]:
    """
    Calcula similitud de Tanimoto entre el fingerprint del sandbox y todos
    los fármacos reales que tengan fingerprint precalculado.

    Retorna lista ordenada descendente por score:
        [{ "drugbank_id", "name", "score" }]
    """
    if not RDKIT_OK or not sandbox_fingerprint:
        return []

    candidates = _get_real_drugs_with_fingerprints(limit=MAX_GDS_CANDIDATE_POOL)

    scored = []
    for c in candidates:
        score = tanimoto_similarity(sandbox_fingerprint, c["fingerprint"])
        if score > 0:
            scored.append({
                "drugbank_id": c["drugbank_id"],
                "name":        c["name"],
                "score":       round(score, 4),
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def behavioral_similarity_by_shared_targets(
    target_ids: list[str], limit: int = MAX_SIMILAR_RESULTS
) -> list[dict]:
    """
    Similitud Jaccard por proteínas compartidas.

    Usa uniprot_id como clave canónica de proteína (gene_name como respaldo).
    Esto evita el falso 0% que ocurre cuando la misma proteína (ej. PTGS2)
    aparece en Neo4j con distintos drugbank_target_id según el rol
    (target farmacológico vs enzima vs transportador).
    """
    if not target_ids:
        return []

    cypher = """
        // Paso 1 — proteínas del sandbox: uniprot_id como clave, gene_name como respaldo
        MATCH (st:Target)
        WHERE st.drugbank_target_id IN $target_ids
        WITH collect(DISTINCT
               CASE WHEN st.uniprot_id IS NOT NULL AND st.uniprot_id <> ''
                    THEN st.uniprot_id
                    ELSE st.gene_name
               END
             ) AS sandboxProteins

        // Paso 2 — todos los Target nodes que representen esas proteínas
        //          (captura los distintos BE-IDs de la misma proteína)
        MATCH (mt:Target)
        WHERE (mt.uniprot_id IS NOT NULL AND mt.uniprot_id <> '' AND mt.uniprot_id IN sandboxProteins)
           OR (mt.gene_name  IS NOT NULL AND mt.gene_name  <> '' AND mt.gene_name  IN sandboxProteins)

        // Paso 3 — fármacos reales vinculados a esos targets
        MATCH (d:Drug)-[]->(mt)
        WITH d, sandboxProteins,
             collect(DISTINCT
               CASE WHEN mt.uniprot_id IS NOT NULL AND mt.uniprot_id <> ''
                    THEN mt.uniprot_id
                    ELSE mt.gene_name
               END
             ) AS sharedProteins

        // Paso 4 — total de proteínas únicas del fármaco (denominador Jaccard)
        MATCH (d)-[]->(allT:Target)
        WITH d, sandboxProteins, sharedProteins,
             collect(DISTINCT
               CASE WHEN allT.uniprot_id IS NOT NULL AND allT.uniprot_id <> ''
                    THEN allT.uniprot_id
                    ELSE allT.gene_name
               END
             ) AS drugProteins

        WITH d, sharedProteins, drugProteins, sandboxProteins,
             size(sharedProteins)  AS sharedCount,
             size(sandboxProteins) AS sandboxCount,
             size(drugProteins)    AS drugCount

        WITH d, sharedProteins, sharedCount,
             toFloat(sharedCount) / (sandboxCount + drugCount - sharedCount) AS jaccard
        WHERE jaccard > 0

        RETURN d.drugbank_id  AS drugbank_id,
               d.name         AS name,
               sharedCount    AS shared_target_count,
               sharedProteins AS shared_targets,
               jaccard        AS score
        ORDER BY score DESC, sharedCount DESC
        LIMIT $limit
    """

    try:
        with _session() as session:
            return session.run(cypher, target_ids=target_ids, limit=limit).data()
    except Exception as exc:
        log.error("Error en behavioral_similarity_by_shared_targets: %s", exc)
        return []


def _behavioral_score_for_drugs(target_ids: list[str], drug_ids: list[str]) -> list[dict]:
    """
    Calcula Jaccard por identidad proteica SOLO para los drug_ids indicados.
    Se usa para rescatar fármacos que están en el top estructural pero cayeron
    fuera del LIMIT del ranking comportamental general.
    """
    if not target_ids or not drug_ids:
        return []

    cypher = """
        MATCH (st:Target)
        WHERE st.drugbank_target_id IN $target_ids
        WITH collect(DISTINCT
               CASE WHEN st.uniprot_id IS NOT NULL AND st.uniprot_id <> ''
                    THEN st.uniprot_id ELSE st.gene_name END
             ) AS sandboxProteins

        MATCH (mt:Target)
        WHERE (mt.uniprot_id IS NOT NULL AND mt.uniprot_id <> '' AND mt.uniprot_id IN sandboxProteins)
           OR (mt.gene_name  IS NOT NULL AND mt.gene_name  <> '' AND mt.gene_name  IN sandboxProteins)

        MATCH (d:Drug)-[]->(mt)
        WHERE d.drugbank_id IN $drug_ids
        WITH d, sandboxProteins,
             collect(DISTINCT
               CASE WHEN mt.uniprot_id IS NOT NULL AND mt.uniprot_id <> ''
                    THEN mt.uniprot_id ELSE mt.gene_name END
             ) AS sharedProteins

        MATCH (d)-[]->(allT:Target)
        WITH d, sandboxProteins, sharedProteins,
             collect(DISTINCT
               CASE WHEN allT.uniprot_id IS NOT NULL AND allT.uniprot_id <> ''
                    THEN allT.uniprot_id ELSE allT.gene_name END
             ) AS drugProteins

        WITH d, sharedProteins, drugProteins, sandboxProteins,
             size(sharedProteins)  AS sharedCount,
             size(sandboxProteins) AS sandboxCount,
             size(drugProteins)    AS drugCount

        WITH d, sharedProteins, sharedCount,
             toFloat(sharedCount) / (sandboxCount + drugCount - sharedCount) AS jaccard

        RETURN d.drugbank_id  AS drugbank_id,
               d.name         AS name,
               sharedCount    AS shared_target_count,
               sharedProteins AS shared_targets,
               jaccard        AS score
    """
    try:
        with _session() as session:
            return session.run(cypher, target_ids=target_ids, drug_ids=drug_ids).data()
    except Exception as exc:
        log.error("Error en _behavioral_score_for_drugs: %s", exc)
        return []


def _infer_targets_from_structural(
    structural_results: list[dict], min_score: float = 0.5
) -> list[str]:
    """
    Obtiene los targets (drugbank_target_id) de los fármacos estructuralmente
    más similares (score ≥ min_score) para usarlos como targets inferidos del
    sandbox cuando el usuario no especificó ninguno.

    Si el compuesto es idéntico a un fármaco real (score=1.0), devuelve
    exactamente los targets de ese fármaco. Para compuestos novedosos devuelve
    la unión de targets de todos los candidatos estructurales relevantes.
    """
    top_ids = [s["drugbank_id"] for s in structural_results if s["score"] >= min_score]
    if not top_ids:
        return []

    cypher = """
        MATCH (d:Drug)-[]->(t:Target)
        WHERE d.drugbank_id IN $drug_ids
        RETURN DISTINCT t.drugbank_target_id AS target_id
    """
    try:
        with _session() as session:
            rows = session.run(cypher, drug_ids=top_ids).data()
        return [r["target_id"] for r in rows if r.get("target_id")]
    except Exception as exc:
        log.error("Error infiriendo targets estructurales: %s", exc)
        return []


def behavioral_similarity_gds(sandbox_id: str, limit: int = MAX_SIMILAR_RESULTS) -> list[dict]:
    """
    Versión avanzada usando Graph Data Science (gds.nodeSimilarity).

    Requiere:
      - Plugin GDS instalado en Neo4j 5.
      - El nodo :SandboxDrug ya vinculado a sus targets candidatos vía
        -[:SANDBOX_TARGETS]-> (ver create_sandbox_drug).

    Proyecta en memoria un grafo bipartito (Drug|SandboxDrug)→(Target) y
    ejecuta nodeSimilarity para encontrar drugs reales cuyo conjunto de
    targets se parezca al del sandbox (Jaccard sobre vecinos compartidos).

    Si GDS no está disponible o el procedimiento falla, retorna [] y el
    caller hace fallback a `behavioral_similarity_by_shared_targets`.
    """
    graph_name = f"sandbox_sim_{sandbox_id[:8]}"

    cypher_project = """
        CALL gds.graph.project.cypher(
            $graph_name,
            'MATCH (n) WHERE n:Drug OR n:Target OR n:SandboxDrug
             RETURN id(n) AS id, labels(n) AS labels',
            'MATCH (d)-[r]->(t:Target)
             WHERE d:Drug OR d:SandboxDrug
             RETURN id(d) AS source, id(t) AS target, "CONNECTS_TO" AS type'
        )
    """

    cypher_similarity = """
        CALL gds.nodeSimilarity.stream($graph_name, {
            similarityCutoff: 0.05
        })
        YIELD node1, node2, similarity
        WITH gds.util.asNode(node1) AS n1, gds.util.asNode(node2) AS n2, similarity
        WHERE (n1:SandboxDrug AND n2:Drug) OR (n1:Drug AND n2:SandboxDrug)
        WITH CASE WHEN n1:Drug THEN n1 ELSE n2 END AS drugNode, similarity
        WITH drugNode, max(similarity) AS score
        RETURN drugNode.drugbank_id AS drugbank_id,
               drugNode.name        AS name,
               score
        ORDER BY score DESC
        LIMIT $limit
    """

    cypher_drop = "CALL gds.graph.drop($graph_name, false)"

    try:
        with _session() as session:
            session.run(cypher_project, graph_name=graph_name)
            try:
                results = session.run(
                    cypher_similarity, graph_name=graph_name, limit=limit
                ).data()
            finally:
                session.run(cypher_drop, graph_name=graph_name)
            return results
    except neo4j_exc.ClientError as exc:
        # Procedimiento gds.* no encontrado → GDS no instalado
        log.warning("GDS no disponible (%s) — usando fallback Jaccard", exc)
        return []
    except Exception as exc:
        log.error("Error en behavioral_similarity_gds: %s", exc)
        return []
