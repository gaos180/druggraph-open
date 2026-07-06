"""
disease_gnn_service.py — Predicción de enlaces fármaco→ENFERMEDAD con GNN (Tier 4.7, BiomedGPS).

Extiende la idea de la DTI-GNN (4.2) del par Drug→Target al par Drug→Disease: sobre el knowledge
graph biomédico (Drug/Target/Disease) aprende embeddings de nodo con GDS (FastRP) y entrena un
cabezal de Link Prediction (regresión logística sobre el producto de Hadamard) con muestreo
negativo, evaluando AUCPR/AP en test. El resultado son enlaces Drug→Disease NO documentados con
probabilidad calibrada: HIPÓTESIS DE REPURPOSING in silico.

Alineado con el enfoque "knowledge graph + GNN" de BiomedGPS. Requiere la capa de enfermedad
cargada (scripts/load_disease_associations.py) + GDS + scikit-learn.

train() (scripts/train_disease_gnn.py) escribe top-K (:Drug)-[:PREDICTED_DISEASE {score}]->(:Disease)
y persiste métricas en Mongo `model_metrics`. El endpoint solo LEE esas aristas.
Degrada con 503 (DiseaseGNNUnavailable) si falta GDS/datos/modelo.
"""

import datetime as _dt
import logging

from neo4j import exceptions as neo4j_exc

from config.services.neo4j_service import _session
# Helpers genéricos reutilizados de la DTI-GNN (4.2).
from config.services.dti_gnn_service import _gds_available, _drop_graph, DTI_LIBS_OK

log = logging.getLogger(__name__)

MODEL_NAME = "disease-lp"
PREDICTED_REL = "PREDICTED_DISEASE"
ASSOC_REL = "ASSOCIATED_WITH"
METRICS_COLLECTION = "model_metrics"
EMBED_DIM = 128

if DTI_LIBS_OK:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import average_precision_score, roc_auc_score


class DiseaseGNNUnavailable(RuntimeError):
    """GDS no disponible, capa de enfermedad ausente, o modelo no entrenado."""
    pass


def _project(session, g: str):
    """Proyecta el subgrafo Drug↔Target↔Disease (no dirigido) para embeddings."""
    session.run(
        "CALL gds.graph.project($g, ['Drug','Target','Disease'], "
        "{ ALL: { type: '*', orientation: 'UNDIRECTED' } })",
        g=g,
    )


def _stream_embeddings(session, g: str) -> tuple[dict, dict]:
    """FastRP sobre el subgrafo. Devuelve (emb_by_key, info_by_key) con key = elementId."""
    rows = session.run(
        """
        CALL gds.fastRP.stream($g, {embeddingDimension:$dim, randomSeed:42})
        YIELD nodeId, embedding
        WITH gds.util.asNode(nodeId) AS n, embedding
        RETURN elementId(n) AS key, labels(n) AS labels, embedding,
               n.drugbank_id AS drugbank_id, n.disease_id AS disease_id, n.name AS name
        """,
        g=g, dim=EMBED_DIM,
    ).data()
    emb, info = {}, {}
    for r in rows:
        emb[r["key"]] = np.array(r["embedding"], dtype="float32")
        info[r["key"]] = {"labels": r["labels"], "drugbank_id": r["drugbank_id"],
                          "disease_id": r["disease_id"], "name": r["name"]}
    return emb, info


# ══════════════════════════════════════════════════════════════════════════════
# ENTRENAMIENTO (offline)
# ══════════════════════════════════════════════════════════════════════════════

def train(neg_ratio: int = 1, top_k: int = 20, candidate_cap: int = 100000) -> dict:
    """Embeddings FastRP + cabezal LP para Drug→Disease; escribe :PREDICTED_DISEASE + métricas."""
    if not DTI_LIBS_OK:
        raise DiseaseGNNUnavailable("numpy/scikit-learn no instalados.")

    g = f"disease_{_dt.datetime.now().strftime('%H%M%S')}"
    with _session() as session:
        if not _gds_available(session):
            raise DiseaseGNNUnavailable("El plugin GDS no está instalado en Neo4j.")
        if not session.run(f"MATCH ()-[r:{ASSOC_REL}]->(:Disease) RETURN r LIMIT 1").single():
            raise DiseaseGNNUnavailable(
                "Capa de enfermedad ausente (corre scripts/load_disease_associations.py).")
        try:
            _project(session, g)
            emb, info = _stream_embeddings(session, g)
            pos = session.run(
                f"MATCH (d:Drug)-[:{ASSOC_REL}]->(x:Disease) "
                "RETURN elementId(d) AS dk, elementId(x) AS xk"
            ).data()
        except neo4j_exc.ClientError as exc:
            _drop_graph(session, g)
            raise DiseaseGNNUnavailable(f"Error GDS: {exc}")

        positives = [(p["dk"], p["xk"]) for p in pos if p["dk"] in emb and p["xk"] in emb]
        if len(positives) < 20:
            _drop_graph(session, g)
            raise DiseaseGNNUnavailable(f"Muy pocas aristas Drug→Disease con embedding ({len(positives)}).")

        drug_keys = [k for k, v in info.items() if "Drug" in v["labels"]]
        disease_keys = [k for k, v in info.items() if "Disease" in v["labels"]]
        pos_set = set(positives)

        rng = np.random.default_rng(42)
        negatives: list[tuple[str, str]] = []
        want = len(positives) * neg_ratio
        attempts = 0
        while len(negatives) < want and attempts < want * 20:
            dk = drug_keys[rng.integers(len(drug_keys))]
            xk = disease_keys[rng.integers(len(disease_keys))]
            attempts += 1
            if (dk, xk) not in pos_set:
                negatives.append((dk, xk))

        def feat(dk, xk):
            return emb[dk] * emb[xk]  # producto de Hadamard

        X = np.array([feat(dk, xk) for dk, xk in positives + negatives])
        y = np.array([1] * len(positives) + [0] * len(negatives))
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

        clf = LogisticRegression(max_iter=1000, class_weight="balanced")
        clf.fit(Xtr, ytr)
        proba_te = clf.predict_proba(Xte)[:, 1]
        auc_pr = float(average_precision_score(yte, proba_te))
        roc = float(roc_auc_score(yte, proba_te))

        # Candidatos de repurposing: enfermedades a 2 hops (colaborativo) no asociadas aún.
        try:
            cand = session.run(
                f"""
                MATCH (d:Drug)-[:{ASSOC_REL}]->(:Disease)<-[:{ASSOC_REL}]-(:Drug)-[:{ASSOC_REL}]->(c:Disease)
                WHERE NOT (d)-[:{ASSOC_REL}]->(c)
                RETURN DISTINCT elementId(d) AS dk, elementId(c) AS xk
                LIMIT $cap
                """,
                cap=candidate_cap,
            ).data()
        except neo4j_exc.ClientError as exc:
            _drop_graph(session, g)
            raise DiseaseGNNUnavailable(f"Error generando candidatos: {exc}")

        pairs = [(c["dk"], c["xk"]) for c in cand if c["dk"] in emb and c["xk"] in emb]
        by_drug: dict[str, list[tuple[str, float]]] = {}
        if pairs:
            Xc = np.array([feat(dk, xk) for dk, xk in pairs])
            scores = clf.predict_proba(Xc)[:, 1]
            for (dk, xk), s in zip(pairs, scores):
                by_drug.setdefault(dk, []).append((xk, float(s)))

        session.run(f"MATCH ()-[r:{PREDICTED_REL} {{model:$m}}]->() DELETE r", m=MODEL_NAME)
        edges = []
        for dk, lst in by_drug.items():
            for xk, s in sorted(lst, key=lambda x: -x[1])[:top_k]:
                edges.append({"dk": dk, "xk": xk, "score": round(s, 4)})
        for i in range(0, len(edges), 1000):
            session.run(
                f"""
                UNWIND $rows AS row
                MATCH (d) WHERE elementId(d) = row.dk
                MATCH (x) WHERE elementId(x) = row.xk
                MERGE (d)-[r:{PREDICTED_REL} {{model:$m}}]->(x)
                SET r.score = row.score
                """,
                rows=edges[i:i + 1000], m=MODEL_NAME,
            )
        _drop_graph(session, g)

    now = _dt.datetime.now(_dt.timezone.utc)
    metrics = {
        "_id": MODEL_NAME, "model": MODEL_NAME, "task": "drug-disease",
        "embedding_method": "fastrp", "auc_pr": round(auc_pr, 4), "roc_auc": round(roc, 4),
        "n_positive": len(positives), "n_negative": len(negatives),
        "n_edges_written": len(edges), "embedding_dim": EMBED_DIM, "trained_at": now,
    }
    try:
        from config.services.mongo import get_db
        get_db()[METRICS_COLLECTION].replace_one({"_id": MODEL_NAME}, metrics, upsert=True)
    except Exception as exc:
        log.warning("No se pudieron persistir las métricas Disease-GNN: %s", exc)

    log.info("Disease-GNN entrenado: AUCPR=%.4f ROC=%.4f, %d aristas.", auc_pr, roc, len(edges))
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
    """Lee las predicciones :PREDICTED_DISEASE de un fármaco + métricas del modelo."""
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
            MATCH (d:Drug {{drugbank_id:$id}})-[r:{PREDICTED_REL} {{model:$m}}]->(x:Disease)
            RETURN x.disease_id AS disease_id, x.name AS name, r.score AS score
            ORDER BY r.score DESC LIMIT $n
            """,
            id=drugbank_id, m=MODEL_NAME, n=top_n,
        ).data()

    predictions = [{
        "disease_id": r["disease_id"] or "", "disease_name": r["name"] or "",
        "probability": round(float(r["score"]), 4),
    } for r in rows]

    return {
        "available": True,
        "drug": {"drugbank_id": drugbank_id, "name": drug["name"] or drugbank_id},
        "predictions": predictions,
        "model": _model_metrics(),
    }
