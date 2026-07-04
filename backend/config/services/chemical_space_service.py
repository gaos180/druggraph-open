"""
chemical_space_service.py — Mapa 2D del espacio químico (Tier 4.1).

Proyecta los embeddings ChemBERTa (768-d, ya poblados en :Drug.chemberta) a 2D con
UMAP y los clusteriza con HDBSCAN. El resultado es una nube de puntos coloreada por
cluster que muestra la estructura del catálogo de fármacos y permite ubicar una
molécula nueva (sandbox) en ese mapa.

Deps OPCIONALES y algo pesadas: `umap-learn`, `hdbscan`, `joblib`, `numpy`. Si faltan,
SPACE_OK es False y los endpoints devuelven 503 (degradación elegante, como ChemBERTa/GDS).

El cómputo (ajuste de UMAP+HDBSCAN sobre todo el catálogo) es caro, así que se hace
OFFLINE con scripts/build_chemical_space.py: persiste el modelo UMAP+clusterer con
joblib (para proyectar puntos nuevos) y la nube en la colección Mongo `chemical_space`.
Los endpoints solo LEEN esa nube cacheada (rápido).
"""

import logging
import os
from collections import Counter

log = logging.getLogger(__name__)

# Directorio de artefactos entrenados (modelo UMAP + clusterer HDBSCAN).
MODEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "models", "chemical_space",
)
UMAP_PATH = os.path.join(MODEL_DIR, "umap.joblib")

# Colección Mongo con la nube 2D ya calculada.
COLLECTION = "chemical_space"

try:
    import numpy as np
    import umap
    import hdbscan
    import joblib
    SPACE_OK = True
except ImportError:
    SPACE_OK = False
    log.info("umap-learn/hdbscan/joblib no instalados — mapa de espacio químico deshabilitado.")


# ══════════════════════════════════════════════════════════════════════════════
# CÓMPUTO OFFLINE (build)
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_embeddings() -> tuple[list[dict], "np.ndarray"]:
    """Lee todos los :Drug con embedding ChemBERTa desde Neo4j."""
    from config.services.neo4j_service import _session
    with _session() as session:
        rows = session.run(
            """
            MATCH (d:Drug)
            WHERE d.drugbank_id IS NOT NULL AND d.chemberta IS NOT NULL
            RETURN d.drugbank_id AS drugbank_id, coalesce(d.name, '') AS name,
                   coalesce(d.type, '') AS type, d.groups AS groups, d.chemberta AS vec
            ORDER BY d.drugbank_id
            """
        ).data()
    meta = [
        {
            "drugbank_id": r["drugbank_id"],
            "name": r["name"],
            "type": r["type"],
            "groups": r["groups"] or [],
        }
        for r in rows
    ]
    vectors = np.array([r["vec"] for r in rows], dtype="float32") if rows else np.empty((0, 0))
    return meta, vectors


def build(n_neighbors: int = 15, min_dist: float = 0.1, min_cluster_size: int = 15) -> dict:
    """
    Ajusta UMAP (2D) + HDBSCAN sobre el catálogo, persiste el modelo y escribe la
    nube en Mongo. Idempotente: sobreescribe la colección y el .joblib.
    """
    if not SPACE_OK:
        return {"available": False, "reason": "umap-learn/hdbscan no instalados."}

    meta, vectors = _fetch_embeddings()
    n = len(meta)
    if n < 10:
        return {"available": False, "reason": f"Muy pocos embeddings ChemBERTa poblados ({n}).",
                "points": n}

    # UMAP a 2D. n_neighbors se acota a n-1 para catálogos pequeños.
    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=min(n_neighbors, n - 1),
        min_dist=min_dist,
        metric="cosine",
        random_state=42,
    )
    coords = reducer.fit_transform(vectors)

    # HDBSCAN sobre las coordenadas 2D; prediction_data para ubicar puntos nuevos.
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=max(2, min(min_cluster_size, n // 2)),
        prediction_data=True,
    )
    labels = clusterer.fit_predict(coords)

    # Persistir modelo (UMAP + clusterer) para locate().
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump({"reducer": reducer, "clusterer": clusterer}, UMAP_PATH)

    # Escribir la nube en Mongo (reemplazo completo).
    from config.services.mongo import get_db
    db = get_db()
    docs = []
    for m, (x, y), lab in zip(meta, coords, labels):
        docs.append({
            "drugbank_id": m["drugbank_id"],
            "name": m["name"],
            "type": m["type"],
            "groups": m["groups"],
            "x": float(x),
            "y": float(y),
            "cluster": int(lab),
        })
    db[COLLECTION].delete_many({})
    if docs:
        db[COLLECTION].insert_many(docs)

    n_clusters = len({int(l) for l in labels if l >= 0})
    n_outliers = int((labels < 0).sum())
    log.info("chemical_space: %d puntos, %d clusters, %d outliers.", n, n_clusters, n_outliers)
    return {
        "available": True,
        "points": n,
        "clusters": n_clusters,
        "outliers": n_outliers,
    }


# ══════════════════════════════════════════════════════════════════════════════
# LECTURA (endpoints)
# ══════════════════════════════════════════════════════════════════════════════

def load_points() -> dict:
    """Lee la nube cacheada de Mongo + resumen por cluster. 'available' False si vacía."""
    from config.services.mongo import get_db
    db = get_db()
    docs = list(db[COLLECTION].find({}, {"_id": 0}))
    if not docs:
        return {"available": False, "points": [], "clusters": []}

    by_cluster: dict[int, list] = {}
    for d in docs:
        by_cluster.setdefault(d["cluster"], []).append(d)

    clusters = []
    for cid, members in sorted(by_cluster.items(), key=lambda kv: -len(kv[1])):
        type_counts = Counter(m["type"] for m in members if m["type"])
        clusters.append({
            "cluster": cid,
            "size": len(members),
            "is_outlier": cid < 0,
            "top_types": [t for t, _ in type_counts.most_common(3)],
            "examples": [m["name"] for m in members[:5] if m["name"]],
        })

    return {"available": True, "points": docs, "clusters": clusters}


def locate(smiles: str, k: int = 10) -> dict:
    """
    Ubica un SMILES nuevo en el mapa: embed ChemBERTa → UMAP.transform → cluster
    (HDBSCAN approximate_predict) + vecinos más cercanos (índice vectorial drug_chemberta).
    """
    if not SPACE_OK:
        return {"available": False, "reason": "umap-learn/hdbscan no instalados."}
    if not os.path.exists(UMAP_PATH):
        return {"available": False, "reason": "Mapa no construido. Ejecuta build_chemical_space.py."}

    from config.services import chemberta_service
    if not chemberta_service.EMBEDDINGS_OK:
        return {"available": False, "reason": "ChemBERTa no disponible (instala torch + transformers)."}

    vec = chemberta_service.embed(smiles)
    if not vec:
        return {"available": False, "reason": "No se pudo calcular el embedding del SMILES."}

    models = joblib.load(UMAP_PATH)
    coords = models["reducer"].transform(np.array([vec], dtype="float32"))
    x, y = float(coords[0][0]), float(coords[0][1])

    cluster = -1
    try:
        labels, _ = hdbscan.approximate_predict(models["clusterer"], coords)
        cluster = int(labels[0])
    except Exception as exc:
        log.debug("approximate_predict falló: %s", exc)

    # Vecinos más cercanos vía el índice vectorial nativo (reusa infra ChemBERTa).
    neighbors = []
    try:
        from config.services.neo4j_service import _session
        with _session() as session:
            rows = session.run(
                """
                CALL db.index.vector.queryNodes('drug_chemberta', $k, $vec)
                YIELD node, score
                RETURN node.drugbank_id AS drugbank_id, node.name AS name, score
                """,
                k=k, vec=vec,
            ).data()
        neighbors = [
            {"drugbank_id": r["drugbank_id"], "name": r["name"], "score": round(float(r["score"]), 4)}
            for r in rows
        ]
    except Exception as exc:
        log.debug("KNN vecinos falló: %s", exc)

    return {"available": True, "x": x, "y": y, "cluster": cluster, "neighbors": neighbors}
