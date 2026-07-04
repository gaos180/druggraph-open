"""
warm_kegg_cache.py — Precalienta la caché persistente de KEGG (colección Mongo
`kegg_cache`) para los fármacos más costosos de resolver en frío.

En frío, /api/drugs/<id>/pathways/ puede tardar decenas de segundos porque KEGG
se consulta por target con un rate-limit de cortesía (~3 req/s) y latencia de red.
Con la caché persistente (ver kegg_service), poblarla una vez offline hace que las
peticiones posteriores del servidor sean casi instantáneas y sobrevivan reinicios.

Estrategia por defecto: calentar los N fármacos con MÁS targets con UniProt
(los de mayor coste y, típicamente, los más consultados). También acepta IDs
concretos con --drug (repetible).

Uso (desde backend/, con el venv activo y Neo4j+Mongo arriba):
    python scripts/warm_kegg_cache.py                 # top 50 por nº de targets
    python scripts/warm_kegg_cache.py --limit 100
    python scripts/warm_kegg_cache.py --drug DB00682 --drug DB00945
"""

import argparse
import os
import sys
import time

import django

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from config.services.neo4j_service import get_driver          # noqa: E402
from config.services.kegg_service import pathways_for_targets  # noqa: E402

MAX_TARGETS_PER_DRUG = 25   # mismo tope que la vista pathways


def _top_drugs(limit: int) -> list[str]:
    cypher = """
        MATCH (d:Drug)-[]->(t:Target)
        WHERE t.uniprot_id IS NOT NULL AND t.uniprot_id <> ''
        WITH d, count(DISTINCT t) AS n
        WHERE n > 0
        RETURN d.drugbank_id AS id ORDER BY n DESC LIMIT $limit
    """
    with get_driver().session() as s:
        return [r["id"] for r in s.run(cypher, limit=limit) if r["id"]]


def _targets_for(drugbank_id: str) -> list[dict]:
    cypher = """
        MATCH (d:Drug {drugbank_id: $id})-[]->(t:Target)
        WHERE t.uniprot_id IS NOT NULL AND t.uniprot_id <> ''
        RETURN DISTINCT t.uniprot_id AS uniprot_id,
               t.name AS name,
               coalesce(t.gene_name, '') AS gene_name
        LIMIT $cap
    """
    with get_driver().session() as s:
        return [dict(r) for r in s.run(cypher, id=drugbank_id, cap=MAX_TARGETS_PER_DRUG)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50, help="nº de fármacos top por nº de targets")
    ap.add_argument("--drug", action="append", default=[], help="DrugBank ID concreto (repetible)")
    args = ap.parse_args()

    drug_ids = args.drug or _top_drugs(args.limit)
    print(f"Calentando caché KEGG para {len(drug_ids)} fármaco(s)…\n")

    started = time.time()
    warmed = 0
    for i, dbid in enumerate(drug_ids, 1):
        targets = _targets_for(dbid)
        if not targets:
            print(f"  [{i}/{len(drug_ids)}] {dbid}: sin targets con UniProt, omitido")
            continue
        t0 = time.time()
        result = pathways_for_targets(targets)
        warmed += 1
        print(
            f"  [{i}/{len(drug_ids)}] {dbid}: {len(targets)} targets → "
            f"{result['pathway_count']} rutas en {time.time() - t0:.1f}s"
        )

    print(f"\nListo: {warmed} fármaco(s) calentados en {time.time() - started:.0f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
