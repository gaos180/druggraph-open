"""
populate_targets.py — Carga dianas moleculares en MongoDB desde Neo4j.

Uso:
    cd backend && python populate_targets.py              # solo datos Neo4j (rápido)
    cd backend && python populate_targets.py --uniprot   # + enriquece con UniProt (~34 min)
    cd backend && python populate_targets.py --refresh   # re-guarda aunque ya existan

Los datos de UniProt se obtienen bajo demanda (y quedan cacheados en MongoDB)
la primera vez que un usuario abre la pestaña UniProt de un target.
"""

import os
import sys
import time
import argparse
import django
from concurrent.futures import ThreadPoolExecutor, as_completed

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from config.services.neo4j_service import get_driver
from config.services.mongo import get_db

BATCH_SIZE   = 100
MAX_WORKERS  = 4    # peticiones UniProt en paralelo


def fetch_all_targets() -> list[dict]:
    """Lee todos los nodos :Target con sus fármacos desde Neo4j."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run("""
            MATCH (t:Target)
            OPTIONAL MATCH (d:Drug)-[r]->(t)
            WITH t,
                 collect(DISTINCT {
                     drugbank_id: coalesce(d.drugbank_id, ''),
                     drug_name:   coalesce(d.name, ''),
                     rel_type:    type(r)
                 }) AS drug_refs
            RETURN
              coalesce(t.drugbank_target_id, '') AS id,
              coalesce(t.name, '')               AS name,
              coalesce(t.gene_name, '')           AS gene_name,
              coalesce(t.uniprot_id, '')          AS uniprot_id,
              coalesce(t.organism, '')            AS organism,
              coalesce(t.cellular_location, '')   AS cellular_location,
              coalesce(t.chromosome_location, '') AS chromosome_location,
              coalesce(t.known_action, '')        AS known_action,
              drug_refs
            ORDER BY t.name
        """)
        return [dict(r) for r in result]


def _fetch_uniprot_safe(accession: str):
    """Wrapper seguro para usar en threads."""
    from config.services.uniprot_service import get_uniprot_entry
    try:
        return accession, get_uniprot_entry(accession)
    except Exception:
        return accession, None


def populate(refresh: bool = False, with_uniprot: bool = False):
    db      = get_db()
    targets = fetch_all_targets()
    total   = len(targets)

    print(f"[populate_targets] {total} targets leídos de Neo4j.")

    # ── Fase 1: guardar datos de Neo4j en MongoDB ─────────────────────────────
    ok = skip = fail = 0
    targets_needing_uniprot = []   # acumulamos los que necesitan UniProt

    for i, t in enumerate(targets, 1):
        target_id  = t.get('id', '')
        uniprot_id = t.get('uniprot_id', '')

        if not target_id:
            fail += 1
            continue

        if not refresh:
            existing = db.targets.find_one({'_id': target_id}, {'_id': 1, 'uniprot': 1})
            if existing:
                # Si ya tiene uniprot embebido no lo necesitamos re-fetch
                if not with_uniprot or existing.get('uniprot'):
                    skip += 1
                    if i % BATCH_SIZE == 0:
                        print(f"  [{i}/{total}] skip…")
                    continue

        drug_refs = [d for d in t.get('drug_refs', []) if d.get('drugbank_id')]

        doc = {
            '_id':                 target_id,
            'name':                t['name'],
            'gene_name':           t['gene_name'],
            'uniprot_id':          uniprot_id,
            'organism':            t['organism'],
            'cellular_location':   t['cellular_location'],
            'chromosome_location': t['chromosome_location'],
            'known_action':        t['known_action'],
            'drug_refs':           drug_refs,
            'drug_count':          len(drug_refs),
            'uniprot':             None,
            'populated_at':        time.time(),
        }

        try:
            db.targets.replace_one({'_id': target_id}, doc, upsert=True)
            ok += 1
            if uniprot_id and with_uniprot:
                targets_needing_uniprot.append((target_id, uniprot_id))
            if i % BATCH_SIZE == 0 or i == total:
                print(f"  [{i}/{total}] guardados: {ok}")
        except Exception as exc:
            fail += 1
            print(f"  [{i}/{total}] FAIL {target_id}: {exc}")

    print(f"\n[populate_targets] Neo4j → MongoDB: {ok} guardados · {skip} ya existían · {fail} fallos")

    # ── Fase 2: enriquecer con UniProt en paralelo ────────────────────────────
    if with_uniprot and targets_needing_uniprot:
        nu_total = len(targets_needing_uniprot)
        print(f"\n[populate_targets] Enriqueciendo {nu_total} targets con UniProt "
              f"({MAX_WORKERS} workers en paralelo)…")

        done = fail_u = 0
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(_fetch_uniprot_safe, uid): tid
                for tid, uid in targets_needing_uniprot
            }
            for future in as_completed(futures):
                tid = futures[future]
                try:
                    accession, parsed = future.result()
                    if parsed:
                        db.targets.update_one({'_id': tid}, {'$set': {'uniprot': parsed}})
                        done += 1
                    else:
                        fail_u += 1
                except Exception as exc:
                    fail_u += 1
                    print(f"  ERROR {tid}: {exc}")

                if (done + fail_u) % BATCH_SIZE == 0 or (done + fail_u) == nu_total:
                    print(f"  [{done + fail_u}/{nu_total}] UniProt OK: {done} · fallos: {fail_u}")

        print(f"\n[populate_targets] UniProt completado: {done} OK · {fail_u} fallos")

    # ── Índices ───────────────────────────────────────────────────────────────
    try:
        db.targets.create_index('name')
        db.targets.create_index('gene_name')
        db.targets.create_index('uniprot_id')
        db.targets.create_index('organism')
        db.targets.create_index('drug_count')
        print("[populate_targets] Índices OK.")
    except Exception as exc:
        print(f"[populate_targets] WARNING índices: {exc}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh', action='store_true',
                        help='Re-guarda aunque el target ya exista')
    parser.add_argument('--uniprot', action='store_true',
                        help=f'Enriquecer con UniProt API en paralelo ({MAX_WORKERS} workers)')
    args = parser.parse_args()
    populate(refresh=args.refresh, with_uniprot=args.uniprot)
