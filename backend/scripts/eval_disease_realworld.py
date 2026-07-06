#!/usr/bin/env python3
"""
eval_disease_realworld.py — Cruce de credibilidad del Disease-GNN con fármacos reales conocidos.

Para un conjunto de fármacos bien conocidos, junta:
  - sus INDICACIONES CLÍNICAS reales (campo `indications` de DrugCentral — "para qué se usa"),
  - las top-5 enfermedades PREDICHAS por el Disease-GNN + los genes mediadores.
Permite juzgar la plausibilidad de las hipótesis del modelo frente al uso real del fármaco.

IMPORTANTE (honestidad): el Disease-GNN predice ASOCIACIONES fármaco→enfermedad de tipo
genético/mecanístico (vía Open Targets: diana → enfermedad), NO indicaciones clínicas aprobadas.
Por eso las columnas se muestran lado a lado como contexto, no como una métrica de recuperación.

Salida: ../dataset_testing/disease_gnn/real_drug_predictions.csv
"""
import csv
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from config.services.mongo import get_db
from config.services.neo4j_service import _session

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "dataset_testing", "disease_gnn")

WELL_KNOWN = [
    "metformin", "aspirin", "ibuprofen", "warfarin", "atorvastatin", "sildenafil",
    "diazepam", "morphine", "fluoxetine", "omeprazole", "amoxicillin", "levothyroxine",
    "prednisone", "losartan", "metoprolol", "gabapentin",
]


def main():
    db = get_db()
    rows = []
    with _session() as session:
        for name in WELL_KNOWN:
            doc = db.drugs.find_one(
                {"name": {"$regex": f"^{name}$", "$options": "i"}},
                {"drugbank-id": 1, "name": 1, "indications": 1},
            )
            if not doc:
                continue
            dbid = doc.get("drugbank-id")
            if isinstance(dbid, dict):
                dbid = dbid.get("value")
            inds = doc.get("indications") or []
            clinical = "; ".join(inds[:4]) if inds else "(sin indicaciones)"

            preds = session.run(
                """
                MATCH (d:Drug {drugbank_id:$id})-[r:PREDICTED_DISEASE]->(x:Disease)
                OPTIONAL MATCH (d)-[a:ASSOCIATED_WITH]->(x)
                RETURN x.name AS disease, r.score AS score, a.gene AS gene
                ORDER BY r.score DESC LIMIT 5
                """,
                id=dbid,
            ).data()
            pred_str = "; ".join(f"{p['disease']} ({p['score']:.2f})" for p in preds) or "(sin predicciones)"
            genes = "; ".join(sorted({p["gene"] for p in preds if p.get("gene")})) or ""

            rows.append([doc["name"], dbid, clinical, pred_str, genes])

    header = ["drug_name", "drug_id", "clinical_indications_drugcentral",
              "top5_predicted_diseases_model", "mediating_genes"]
    with open(os.path.join(OUT, "real_drug_predictions.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(header); w.writerows(rows)
    print(f"Escritos {len(rows)} fármacos reales en real_drug_predictions.csv")
    for r in rows[:6]:
        print(f"  {r[0]:14s} | usa: {r[2][:45]:45s} | predice: {r[3][:50]}")


if __name__ == "__main__":
    main()
