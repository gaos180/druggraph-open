"""ETL paso 6 (enriquecedor) — evidencia diana→enfermedad desde Open Targets.

Para cada fármaco toma los genes de sus dianas (`doc['targets'][*]['gene_name']`),
los mapea a Ensembl gene id (ENSG) vía Open Targets y recupera las enfermedades
asociadas con su score integrado. Escribe en el documento Mongo `drugs` el campo
`open_targets_diseases`: lista de `{disease, score, target_gene}` (top-N por score).

Fuente: Open Targets Platform (GraphQL, sin API key). Licencia CC0 1.0.
Reutiliza `config/services/opentargets_service.py` (ya implementa el cliente GraphQL
con rate-limit y caché): `ensembl_from_symbol(symbol)` y `target_diseases(ensg, size)`.

Idempotente: `update_one($set)` por fármaco. Cachea por gen dentro de la corrida para
no repetir el mapeo/consulta cuando un gen es diana de varios fármacos.

Degradación limpia: si el servicio no está disponible (sin `requests`), registra un
warning y sale sin tocar la base.

Uso (desde backend/, con el venv activo):
    python -m scripts.ingest.step06_opentargets
    python -m scripts.ingest.step06_opentargets --limit 200 --top 10
    python -m scripts.ingest.step06_opentargets --per-target 20 --top 15
"""
from __future__ import annotations

import argparse

from scripts.ingest._common import log, mongo_db
from config.services import opentargets_service as ot


def _drug_genes(doc: dict) -> list[str]:
    """Símbolos de gen únicos (en orden) de las dianas humanas del fármaco."""
    genes: list[str] = []
    seen: set[str] = set()
    for t in doc.get("targets", []) or []:
        g = (t.get("gene_name") or "").strip().upper()
        if g and g not in seen:
            seen.add(g)
            genes.append(g)
    return genes


def _diseases_for_gene(gene: str, per_target: int, cache: dict) -> list[dict]:
    """Enfermedades asociadas a un gen (con score), cacheadas por gen en la corrida."""
    if gene in cache:
        return cache[gene]
    rows: list[dict] = []
    ensg = ot.ensembl_from_symbol(gene)
    if ensg:
        for d in ot.target_diseases(ensg, size=per_target):
            rows.append({
                "disease": d["disease_name"],
                "disease_id": d["disease_id"],
                "score": d["score"],
                "target_gene": gene,
            })
    cache[gene] = rows
    return rows


def _open_targets_diseases(doc: dict, per_target: int, top: int, cache: dict) -> list[dict]:
    """Agrega las enfermedades de todas las dianas del fármaco y devuelve el top-N por score.

    Conserva la (diana, enfermedad) de mayor score cuando la misma enfermedad aparece
    por varios genes, evitando filas duplicadas.
    """
    best: dict = {}  # disease_id -> fila de mayor score
    for gene in _drug_genes(doc):
        for row in _diseases_for_gene(gene, per_target, cache):
            did = row["disease_id"]
            if did not in best or row["score"] > best[did]["score"]:
                best[did] = row
    diseases = sorted(best.values(), key=lambda r: r["score"], reverse=True)
    return diseases[:top]


def run(limit: int | None = None, per_target: int = 15, top: int = 10):
    if not ot.REQUESTS_OK:
        log.warning("Open Targets no disponible (falta `requests`); nada que hacer.")
        return 0

    db = mongo_db()
    # solo fármacos con al menos una diana con símbolo de gen
    q = {"targets.gene_name": {"$exists": True, "$ne": ""}}
    proj = {"targets.gene_name": 1}
    cur = db.drugs.find(q, proj)
    if limit:
        cur = cur.limit(limit)

    gene_cache: dict = {}
    updated = 0
    processed = 0
    for doc in cur:
        processed += 1
        diseases = _open_targets_diseases(doc, per_target=per_target, top=top, cache=gene_cache)
        if diseases:
            db.drugs.update_one(
                {"_id": doc["_id"]},
                {"$set": {"open_targets_diseases": diseases}},
            )
            updated += 1
        if processed % 50 == 0:
            log.info("  … %d fármacos procesados (%d anotados, %d genes en caché)",
                     processed, updated, len(gene_cache))

    log.info("Open Targets: %d/%d fármacos anotados con open_targets_diseases (%d genes consultados).",
             updated, processed, len(gene_cache))
    return updated


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Enriquecer drugs con evidencia diana→enfermedad (Open Targets)")
    ap.add_argument("--limit", type=int, default=None, help="límite de fármacos (prueba)")
    ap.add_argument("--per-target", type=int, default=15, help="enfermedades a pedir por gen (Open Targets)")
    ap.add_argument("--top", type=int, default=10, help="nº de enfermedades a guardar por fármaco (top por score)")
    args = ap.parse_args()
    run(limit=args.limit, per_target=args.per_target, top=args.top)
