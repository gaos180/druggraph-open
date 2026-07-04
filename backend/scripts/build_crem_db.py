#!/usr/bin/env python3
"""
build_crem_db.py — Prepara la base de fragmentos para el diseño de novo con CReM (Tier 4.4).

CReM necesita una base de fragmentos SQLite. Hay dos caminos:

  A) DESCARGAR una base precompilada (recomendado, ChEMBL) desde el proyecto CReM:
        https://github.com/DrrDom/crem  (sección "Fragment databases")
     y luego exportar:  export CREM_DB_PATH=/ruta/replacements.db

  B) CONSTRUIRLA localmente a partir del catálogo de DrugGraph. Este script EXPORTA los
     SMILES de todos los :Drug a un fichero y te imprime los comandos de CReM a ejecutar
     (fragmentación + creación de la base). Requiere `pip install crem` (trae los CLIs
     `fragmentation`, `frag_to_env`, `import_env` / `cremdb_create` según versión).

USO (desde backend/, con el venv activo):
    python -m scripts.build_crem_db --out /tmp/druggraph_smiles.smi

Tras obtener la base, define la env var antes de arrancar el backend:
    export CREM_DB_PATH=/ruta/a/replacements.db
"""

import argparse
import logging
import os

import django

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("crem_db")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()


def export_catalog_smiles(out_path: str) -> int:
    """Escribe 'SMILES<TAB>drugbank_id' de todos los :Drug con SMILES a un fichero."""
    from config.services.neo4j_service import _session
    from config.services.mongo import get_db
    from config.services.chemberta_index import _smiles_for

    db = get_db()
    with _session() as session:
        ids = [r["id"] for r in session.run(
            "MATCH (d:Drug) WHERE d.drugbank_id IS NOT NULL RETURN d.drugbank_id AS id"
        ).data()]

    n = 0
    with open(out_path, "w") as fh:
        for dbid in ids:
            smi = _smiles_for(db, dbid)
            if smi:
                fh.write(f"{smi}\t{dbid}\n")
                n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/druggraph_smiles.smi",
                    help="fichero de salida con los SMILES del catálogo")
    args = ap.parse_args()

    n = export_catalog_smiles(args.out)
    log.info("Exportados %d SMILES a %s", n, args.out)

    print("\n── Siguientes pasos para construir la base de fragmentos CReM ─────────────")
    print("  Opción A (descargar precompilada ChEMBL): ver https://github.com/DrrDom/crem")
    print("  Opción B (construir desde el catálogo exportado), con `crem` instalado:")
    print(f"     fragmentation {args.out} -o /tmp/frags.txt -c $(nproc)")
    print("     frag_to_env /tmp/frags.txt -o /tmp/env.txt -c $(nproc)")
    print("     import_env /tmp/env.txt -o /tmp/replacements.db")
    print("  Finalmente:")
    print("     export CREM_DB_PATH=/tmp/replacements.db   # antes de arrancar el backend\n")


if __name__ == "__main__":
    main()
