"""
dti_gnn_service.py — Predicción de interacción fármaco-diana con GNN (Tier 4.2).

A diferencia de la predicción topológica de enlaces (Adamic-Adar en gds_service), aquí
APRENDEMOS representaciones de nodo con una red neuronal de grafos (GraphSAGE, con fallback
a FastRP) usando Neo4j GDS, y entrenamos un cabezal de Link Prediction (regresión logística)
sobre el producto de Hadamard de los embeddings, con muestreo negativo y evaluación AUCPR/AP
en un conjunto de test. El resultado son enlaces :Drug→:Target NO documentados con
probabilidad calibrada (hipótesis de repurposing in silico).

El entrenamiento (scripts/train_dti_gnn.py) escribe las top-K predicciones por fármaco como
relaciones (:Drug)-[:PREDICTED_TARGET {score}]->(:Target) y persiste las métricas del modelo
en la colección Mongo `model_metrics`. El endpoint solo LEE esas aristas (rápido).

Requiere el plugin GDS (para los embeddings) + scikit-learn/numpy (para el cabezal LP).
Degrada con 503 (DTIUnavailable) si GDS no está o el modelo no se ha entrenado.
"""

import datetime as _dt
import logging

from neo4j import exceptions as neo4j_exc

from config.services.neo4j_service import _session

log = logging.getLogger(__name__)

MODEL_NAME = "graphsage-lp"
PREDICTED_REL = "PREDICTED_TARGET"
METRICS_COLLECTION = "model_metrics"
EMBED_DIM = 128


class DTIUnavailable(RuntimeError):
    """GDS no disponible o modelo DTI no entrenado."""
    pass


try:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import average_precision_score, roc_auc_score
    DTI_LIBS_OK = True
except ImportError:
    DTI_LIBS_OK = False
    log.info("numpy/scikit-learn no disponibles — cabezal DTI deshabilitado.")


# ══════════════════════════════════════════════════════════════════════════════
# EMBEDDINGS DE GRAFO (GraphSAGE con fallback a FastRP)
# ══════════════════════════════════════════════════════════════════════════════

def _gds_available(session) -> bool:
    try:
        return session.run("RETURN gds.version() AS v").single() is not None
    except Exception:
        return False


def _project(session, g: str):
    session.run(
        "CALL gds.graph.project($g, ['Drug','Target'], "
        "{ ALL: { type: '*', orientation: 'UNDIRECTED' } })",
        g=g,
    )


def _drop_graph(session, g: str):
    try:
        session.run("CALL gds.graph.drop($g, false)", g=g)
    except Exception:
        pass


def _stream_embeddings(session, g: str, method: str) -> tuple[dict, dict]:
    """
    Devuelve (emb_by_key, info_by_key) con key = elementId del nodo.
    Intenta GraphSAGE; si falla, cae a FastRP.
    """
    used = method
    rows = None
    if method == "graphsage":
        try:
            session.run("CALL gds.degree.mutate($g, {mutateProperty:'deg'})", g=g)
            session.run(
                "CALL gds.beta.graphSage.train($g, {modelName:$m, featureProperties:['deg'], "
                "embeddingDimension:$dim, aggregator:'mean', sampleSizes:[10,10], randomSeed:42})",
                g=g, m=MODEL_NAME, dim=EMBED_DIM,
            )
            rows = session.run(
                """
                CALL gds.beta.graphSage.stream($g, {modelName:$m})
                YIELD nodeId, embedding
                WITH gds.util.asNode(nodeId) AS n, embedding
                RETURN elementId(n) AS key, labels(n) AS labels, embedding,
                       n.drugbank_id AS drugbank_id, n.drugbank_target_id AS target_id,
                       n.name AS name, n.uniprot_id AS uniprot
                """,
                g=g, m=MODEL_NAME,
            ).data()
            try:
                session.run("CALL gds.beta.model.drop($m)", m=MODEL_NAME)
            except Exception:
                pass
        except neo4j_exc.ClientError as exc:
            log.warning("GraphSAGE no disponible (%s) — fallback a FastRP.", exc)
            rows = None
            used = "fastrp"

    if rows is None:
        used = "fastrp"
        rows = session.run(
            """
            CALL gds.fastRP.stream($g, {embeddingDimension:$dim, randomSeed:42})
            YIELD nodeId, embedding
            WITH gds.util.asNode(nodeId) AS n, embedding
            RETURN elementId(n) AS key, labels(n) AS labels, embedding,
                   n.drugbank_id AS drugbank_id, n.drugbank_target_id AS target_id,
                   n.name AS name, n.uniprot_id AS uniprot
            """,
            g=g, dim=EMBED_DIM,
        ).data()

    emb, info = {}, {}
    for r in rows:
        emb[r["key"]] = np.array(r["embedding"], dtype="float32")
        info[r["key"]] = {
            "labels": r["labels"], "drugbank_id": r["drugbank_id"],
            "target_id": r["target_id"], "name": r["name"], "uniprot": r["uniprot"],
        }
    return emb, info, used


# ══════════════════════════════════════════════════════════════════════════════
# ENTRENAMIENTO (offline)
# ══════════════════════════════════════════════════════════════════════════════

def train(method: str = "graphsage", neg_ratio: int = 1, top_k: int = 20,
          candidate_cap: int = 50000) -> dict:
    """
    Entrena el modelo DTI: embeddings de grafo + cabezal LP (regresión logística), evalúa
    AUCPR/AP en test, escribe top-K :PREDICTED_TARGET por fármaco y persiste métricas.
    """
    if not DTI_LIBS_OK:
        raise DTIUnavailable("numpy/scikit-learn no instalados.")

    g = f"dti_{_dt.datetime.now().strftime('%H%M%S')}"
    with _session() as session:
        if not _gds_available(session):
            raise DTIUnavailable("El plugin GDS no está instalado en Neo4j.")
        try:
            _project(session, g)
            emb, info, used = _stream_embeddings(session, g, method)

            pos = session.run(
                "MATCH (d:Drug)-[]->(t:Target) RETURN elementId(d) AS dk, elementId(t) AS tk"
            ).data()
        except neo4j_exc.ClientError as exc:
            _drop_graph(session, g)
            raise DTIUnavailable(f"Error GDS: {exc}")

        # Pares positivos con embedding en ambos extremos.
        positives = [(p["dk"], p["tk"]) for p in pos if p["dk"] in emb and p["tk"] in emb]
        if len(positives) < 20:
            _drop_graph(session, g)
            raise DTIUnavailable(f"Muy pocas aristas Drug→Target con embedding ({len(positives)}).")

        drug_keys = [k for k, v in info.items() if "Drug" in v["labels"]]
        target_keys = [k for k, v in info.items() if "Target" in v["labels"]]
        pos_set = set(positives)

        # Muestreo negativo: pares (drug, target) inexistentes.
        rng = np.random.default_rng(42)
        negatives: list[tuple[str, str]] = []
        want = len(positives) * neg_ratio
        attempts = 0
        while len(negatives) < want and attempts < want * 20:
            dk = drug_keys[rng.integers(len(drug_keys))]
            tk = target_keys[rng.integers(len(target_keys))]
            attempts += 1
            if (dk, tk) not in pos_set:
                negatives.append((dk, tk))

        def feat(dk, tk):
            return emb[dk] * emb[tk]  # producto de Hadamard

        X = np.array([feat(dk, tk) for dk, tk in positives + negatives])
        y = np.array([1] * len(positives) + [0] * len(negatives))
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

        clf = LogisticRegression(max_iter=1000, class_weight="balanced")
        clf.fit(Xtr, ytr)
        proba_te = clf.predict_proba(Xte)[:, 1]
        auc_pr = float(average_precision_score(yte, proba_te))
        roc = float(roc_auc_score(yte, proba_te))

        # Candidatos (2-hop, no conectados) para escribir predicciones.
        try:
            cand = session.run(
                """
                MATCH (d:Drug)-[]->(:Target)<-[]-(:Drug)-[]->(cand:Target)
                WHERE NOT (d)-[]->(cand)
                RETURN DISTINCT elementId(d) AS dk, elementId(cand) AS tk
                LIMIT $cap
                """,
                cap=candidate_cap,
            ).data()
        except neo4j_exc.ClientError as exc:
            _drop_graph(session, g)
            raise DTIUnavailable(f"Error generando candidatos: {exc}")

        pairs = [(c["dk"], c["tk"]) for c in cand if c["dk"] in emb and c["tk"] in emb]
        by_drug: dict[str, list[tuple[str, float]]] = {}
        if pairs:
            Xc = np.array([feat(dk, tk) for dk, tk in pairs])
            scores = clf.predict_proba(Xc)[:, 1]
            for (dk, tk), s in zip(pairs, scores):
                by_drug.setdefault(dk, []).append((tk, float(s)))

        # Reescribe las aristas del modelo (idempotente).
        session.run(f"MATCH ()-[r:{PREDICTED_REL} {{model:$m}}]->() DELETE r", m=MODEL_NAME)
        edges = []
        for dk, lst in by_drug.items():
            for tk, s in sorted(lst, key=lambda x: -x[1])[:top_k]:
                edges.append({"dk": dk, "tk": tk, "score": round(s, 4)})
        for i in range(0, len(edges), 1000):
            session.run(
                f"""
                UNWIND $rows AS row
                MATCH (d) WHERE elementId(d) = row.dk
                MATCH (t) WHERE elementId(t) = row.tk
                MERGE (d)-[r:{PREDICTED_REL} {{model:$m}}]->(t)
                SET r.score = row.score
                """,
                rows=edges[i:i + 1000], m=MODEL_NAME,
            )
        _drop_graph(session, g)

    now = _dt.datetime.now(_dt.timezone.utc)
    metrics = {
        "_id": MODEL_NAME,
        "model": MODEL_NAME,
        "embedding_method": used,
        "auc_pr": round(auc_pr, 4),
        "roc_auc": round(roc, 4),
        "n_positive": len(positives),
        "n_negative": len(negatives),
        "n_edges_written": len(edges),
        "embedding_dim": EMBED_DIM,
        "trained_at": now,
    }
    try:
        from config.services.mongo import get_db
        get_db()[METRICS_COLLECTION].replace_one({"_id": MODEL_NAME}, metrics, upsert=True)
    except Exception as exc:
        log.warning("No se pudieron persistir las métricas DTI: %s", exc)

    log.info("DTI entrenado (%s): AUCPR=%.4f ROC=%.4f, %d aristas.", used, auc_pr, roc, len(edges))
    return {**metrics, "trained_at": now.isoformat()}


# ══════════════════════════════════════════════════════════════════════════════
# INFERENCIA (endpoint)
# ══════════════════════════════════════════════════════════════════════════════

def _model_metrics() -> dict:
    try:
        from config.services.mongo import get_db
        doc = get_db()[METRICS_COLLECTION].find_one({"_id": MODEL_NAME})
        if not doc:
            return {}
        doc.pop("_id", None)
        ts = doc.get("trained_at")
        if isinstance(ts, _dt.datetime):
            doc["trained_at"] = ts.isoformat()
        return doc
    except Exception:
        return {}


def predict_for_drug(drugbank_id: str, top_n: int = 20) -> dict:
    """Lee las predicciones :PREDICTED_TARGET de un fármaco + métricas del modelo."""
    top_n = max(1, min(top_n, 100))
    with _session() as session:
        drug = session.run(
            "MATCH (d:Drug {drugbank_id:$id}) RETURN d.name AS name LIMIT 1", id=drugbank_id
        ).single()
        if not drug:
            return {"available": True, "drug": {"drugbank_id": drugbank_id, "name": drugbank_id},
                    "predictions": [], "model": _model_metrics()}
        rows = session.run(
            f"""
            MATCH (d:Drug {{drugbank_id:$id}})-[r:{PREDICTED_REL} {{model:$m}}]->(t:Target)
            RETURN t.drugbank_target_id AS target_id, t.name AS name,
                   t.uniprot_id AS uniprot_id, t.gene_name AS gene_name, r.score AS score
            ORDER BY r.score DESC LIMIT $n
            """,
            id=drugbank_id, m=MODEL_NAME, n=top_n,
        ).data()

    predictions = [{
        "target_id": r["target_id"] or "", "target_name": r["name"] or "",
        "uniprot_id": r["uniprot_id"] or "", "gene_name": r["gene_name"] or "",
        "probability": round(float(r["score"]), 4),
    } for r in rows]

    return {
        "available": True,
        "drug": {"drugbank_id": drugbank_id, "name": drug["name"] or drugbank_id},
        "predictions": predictions,
        "model": _model_metrics(),
    }
