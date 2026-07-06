#!/usr/bin/env python3
"""
load_disease_associations.py — Construye la capa de ENFERMEDAD del grafo (Tier 4.7, BiomedGPS).

DrugGraph ya es un knowledge graph biomédico en Neo4j (Drug/Target/Gene/Category). Este script
lo enriquece con enfermedades para habilitar la predicción de enlaces fármaco→enfermedad
(repurposing) al estilo BiomedGPS: proyecta el campo Mongo `open_targets_diseases` (evidencia
diana→enfermedad de Open Targets, agregada por fármaco) a:

    (:Disease {disease_id, name})
    (:Drug)-[:ASSOCIATED_WITH {score, gene}]->(:Disease)

Idempotente (MERGE). Correr en serie (no concurrente con otras escrituras a Neo4j).

USO (desde backend/, con el venv activo):
    python -m scripts.load_disease_associations
    python -m scripts.load_disease_associations --min-score 0.3   # filtra evidencia débil
"""

import argparse
import logging
import os

import django

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("load_disease")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()


def _drug_id(doc: dict) -> str:
    dbid = doc.get("drugbank-id")
    if isinstance(dbid, dict):
        dbid = dbid.get("value")
    if isinstance(dbid, list) and dbid:
        dbid = dbid[0].get("value") if isinstance(dbid[0], dict) else dbid[0]
    return str(dbid) if dbid else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-score", type=float, default=0.0,
                    help="score mínimo de Open Targets para incluir la asociación")
    ap.add_argument("--batch", type=int, default=1000)
    args = ap.parse_args()

    from config.services.mongo import get_db
    from config.services.neo4j_service import _session

    db = get_db()
    cursor = db.drugs.find(
        {"open_targets_diseases": {"$exists": True, "$ne": []}},
        {"drugbank-id": 1, "open_targets_diseases": 1},
    )

    rows = []
    diseases = {}
    for doc in cursor:
        did = _drug_id(doc)
        if not did:
            continue
        for a in (doc.get("open_targets_diseases") or []):
            dis_id = a.get("disease_id")
            score = a.get("score")
            if not dis_id or (score is not None and score < args.min_score):
                continue
            diseases[dis_id] = a.get("disease") or dis_id
            rows.append({"drug": did, "dis": dis_id,
                         "score": round(float(score), 4) if score is not None else None,
                         "gene": a.get("target_gene") or ""})

    log.info("Preparadas %d asociaciones fármaco→enfermedad (%d enfermedades únicas).",
             len(rows), len(diseases))

    with _session() as session:
        # Índice para MERGE eficiente sobre :Disease(disease_id).
        session.run("CREATE INDEX disease_id IF NOT EXISTS FOR (x:Disease) ON (x.disease_id)")
        # Nodos de enfermedad.
        dis_rows = [{"id": k, "name": v} for k, v in diseases.items()]
        for i in range(0, len(dis_rows), args.batch):
            session.run(
                "UNWIND $rows AS r MERGE (x:Disease {disease_id:r.id}) SET x.name = r.name",
                rows=dis_rows[i:i + args.batch],
            )
        # Aristas fármaco→enfermedad (serial, por lotes — Neo4j frágil).
        written = 0
        for i in range(0, len(rows), args.batch):
            res = session.run(
                """
                UNWIND $rows AS r
                MATCH (d:Drug {drugbank_id:r.drug})
                MATCH (x:Disease {disease_id:r.dis})
                MERGE (d)-[e:ASSOCIATED_WITH]->(x)
                SET e.score = r.score, e.gene = r.gene
                RETURN count(e) AS c
                """,
                rows=rows[i:i + args.batch],
            ).single()
            written += res["c"] if res else 0
        log.info("Cargadas %d aristas ASSOCIATED_WITH y %d nodos :Disease.", written, len(dis_rows))


if __name__ == "__main__":
    main()
