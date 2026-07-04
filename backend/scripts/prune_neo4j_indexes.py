"""
prune_neo4j_indexes.py — Poda índices Neo4j huérfanos (label sin nodos).

Algunos índices quedaron de un cargador anterior que preveía nodos :Polypeptide
que finalmente nunca se materializaron (el símbolo del gen vive directamente en
:Target.gene_name). Un índice sobre un label con 0 nodos no aporta nada y ensucia
`SHOW INDEXES`.

El script es idempotente y CONSERVADOR: sólo elimina un índice de la lista blanca
si el label al que apunta tiene exactamente 0 nodos. Si el label recupera nodos en
el futuro, el índice no se toca.

Uso (desde backend/, con el venv activo):
    python scripts/prune_neo4j_indexes.py            # aplica
    python scripts/prune_neo4j_indexes.py --dry-run  # sólo muestra
"""

import argparse
import os
import sys

import django

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from config.services.neo4j_service import get_driver  # noqa: E402

# Índices candidatos a poda: apuntan a labels que el modelo actual no usa.
CANDIDATES = ["poly_gene", "poly_cellloc", "polypeptide_uniprot"]


def _label_of(session, index_name: str) -> str | None:
    row = session.run(
        "SHOW INDEXES YIELD name, labelsOrTypes WHERE name = $n RETURN labelsOrTypes AS l",
        n=index_name,
    ).single()
    if not row or not row["l"]:
        return None
    return row["l"][0]


def _is_constraint(session, name: str) -> bool:
    row = session.run(
        "SHOW CONSTRAINTS YIELD name WHERE name = $n RETURN count(*) AS c", n=name
    ).single()
    return bool(row and row["c"])


def _drop(session, name: str) -> None:
    # Un índice respaldado por un constraint no se puede DROP INDEX directamente:
    # hay que eliminar el constraint, que a su vez elimina su índice de respaldo.
    if _is_constraint(session, name):
        session.run(f"DROP CONSTRAINT {name} IF EXISTS")
    else:
        session.run(f"DROP INDEX {name} IF EXISTS")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="sólo mostrar, no eliminar")
    args = ap.parse_args()

    dropped, kept, missing = [], [], []
    with get_driver().session() as session:
        for name in CANDIDATES:
            label = _label_of(session, name)
            if label is None:
                missing.append(name)
                continue
            count = session.run(f"MATCH (n:`{label}`) RETURN count(n) AS c").single()["c"]
            if count > 0:
                kept.append((name, label, count))
                continue
            if not args.dry_run:
                _drop(session, name)
            dropped.append((name, label))

    verb = "Se eliminarían" if args.dry_run else "Eliminados"
    for name, label in dropped:
        print(f"  ✓ {verb}: {name} (:{label}, 0 nodos)")
    for name, label, count in kept:
        print(f"  · Conservado: {name} (:{label}, {count} nodos)")
    for name in missing:
        print(f"  · Ya no existe: {name}")

    print(f"\n{len(dropped)} podado(s), {len(kept)} conservado(s), {len(missing)} inexistente(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
