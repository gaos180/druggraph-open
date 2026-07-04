"""
populate_uniprot.py — Pre-carga datos de UniProt en MongoDB para todos los targets.

Correr una vez (o periódicamente para refrescar):
    cd backend && python populate_uniprot.py

Progreso:
    Imprime una línea por accession: OK / SKIP (ya en caché) / FAIL
    Al final muestra un resumen.

Prerequisitos:
    - Neo4j corriendo con targets importados
    - MongoDB corriendo
    - venv activado con requirements instalados
"""

import os
import sys
import time
import django

# Bootstrap Django para poder usar los servicios (el script vive en backend/scripts/)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from config.services.neo4j_service import get_driver
from config.services.mongo import get_db
from config.services.uniprot_service import _fetch_uniprot, parse_protein_details

BATCH_SIZE   = 50     # log cada N accessions
RATE_DELAY   = 0.5    # segundos entre llamadas (cortesía con UniProt)
CACHE_TTL    = 86_400 * 30   # 30 días; refrescar si superado


def get_all_uniprot_ids() -> list[str]:
    """Obtiene todos los UniProt IDs únicos de los nodos :Target en Neo4j."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (t:Target) WHERE t.uniprot_id IS NOT NULL AND t.uniprot_id <> '' "
            "RETURN DISTINCT t.uniprot_id AS uid ORDER BY uid"
        )
        return [r['uid'] for r in result]


def is_cached(db, accession: str) -> bool:
    """True si la entrada existe en MongoDB y no ha expirado."""
    doc = db.uniprot_cache.find_one({'_id': accession})
    if not doc:
        return False
    return (time.time() - doc.get('cached_at', 0)) < CACHE_TTL


def populate():
    db         = get_db()
    accessions = get_all_uniprot_ids()
    total      = len(accessions)

    print(f"[populate_uniprot] {total} accessions únicos encontrados en Neo4j.")

    ok = skip = fail = 0

    for i, acc in enumerate(accessions, 1):
        if is_cached(db, acc):
            skip += 1
            if i % BATCH_SIZE == 0:
                print(f"  [{i}/{total}] {acc} — SKIP (en caché)")
            continue

        raw = _fetch_uniprot(acc)
        if not raw:
            fail += 1
            print(f"  [{i}/{total}] {acc} — FAIL (no disponible en UniProt)")
            time.sleep(RATE_DELAY)
            continue

        try:
            parsed = parse_protein_details(raw)
        except Exception as exc:
            fail += 1
            print(f"  [{i}/{total}] {acc} — FAIL (parse error: {exc})")
            time.sleep(RATE_DELAY)
            continue

        db.uniprot_cache.replace_one(
            {'_id': acc},
            {'_id': acc, 'parsed': parsed, 'cached_at': time.time()},
            upsert=True,
        )
        ok += 1

        if i % BATCH_SIZE == 0 or i == total:
            print(f"  [{i}/{total}] {acc} — OK ({parsed.get('protein_name', '')[:40]})")

        time.sleep(RATE_DELAY)

    print(f"\n[populate_uniprot] Completado: {ok} OK · {skip} ya en caché · {fail} fallos")


if __name__ == '__main__':
    populate()
