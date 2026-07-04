#!/usr/bin/env python3
"""
populate_fingerprints.py — Calcula fingerprints moleculares para los fármacos
reales y los escribe como propiedad `fingerprint` en los nodos (:Drug) de Neo4j.

Esto desbloquea la similitud ESTRUCTURAL del módulo sandbox
(sandbox_service.structural_similarity), que compara el compuesto del usuario
contra d.fingerprint vía Tanimoto.

FLUJO:
    MongoDB (drugs)  ──SMILES──►  RDKit Morgan/ECFP4  ──FPS──►  Neo4j (:Drug.fingerprint)

USO (como script standalone, fuera de Django):
    # Requiere variables de entorno o edición de la sección CONFIG abajo
    python3 populate_fingerprints.py

USO (como Django management command):
    Copia este archivo a  drugs/management/commands/populate_fingerprints.py
    y ejecútalo con:
        python manage.py populate_fingerprints
        python manage.py populate_fingerprints --limit 500 --batch 100
        python manage.py populate_fingerprints --overwrite

El formato del fingerprint (DataStructs.BitVectToFPSText, Morgan radio 2,
2048 bits) es IDÉNTICO al de sandbox_service.compute_fingerprint, de modo que
los Tanimoto entre sandbox y fármacos reales son directamente comparables.

Dependencias: pip install rdkit pymongo neo4j
"""

import os
import sys
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── RDKit ───────────────────────────────────────────────────────────────────
# Mismos parámetros que sandbox_service.py — NO cambiar sin re-poblar todo
FP_RADIUS = 2
FP_NBITS  = 2048

try:
    from rdkit import Chem
    from rdkit.Chem import DataStructs, rdFingerprintGenerator
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")  # silenciar warnings de RDKit en SMILES feos
    RDKIT_OK = True
    # Generador Morgan (API moderna); bits idénticos al antiguo
    # GetMorganFingerprintAsBitVect, así que no requiere repoblar lo ya cargado.
    _MORGAN_GEN = rdFingerprintGenerator.GetMorganGenerator(radius=FP_RADIUS, fpSize=FP_NBITS)
except ImportError:
    RDKIT_OK = False


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACCIÓN DE SMILES Y DRUGBANK-ID (consistente con services.py / cypher)
# ══════════════════════════════════════════════════════════════════════════════

def extract_smiles(drug: dict) -> str | None:
    """
    Extrae SMILES de calculated-properties.
    Replica services.get_smiles para consistencia total.
    """
    props = drug.get("calculated-properties") or []
    for p in props:
        if isinstance(p, dict) and p.get("kind") == "SMILES":
            return p.get("value")
    return None


def extract_primary_drugbank_id(drug: dict) -> str:
    """
    Resuelve el drugbank-id primario igual que lo hace drugbank_to_cypher.py,
    para que la clave coincida EXACTAMENTE con la usada en los nodos (:Drug).

    El campo puede ser:
      - string:                       "DB00001"
      - dict:                         {"value": "DB00001", "primary": "true"}
      - lista de dicts/strings:       [{"value": "DB00001", "primary": "true"}, ...]
    """
    raw = drug.get("drugbank-id")
    if not raw:
        return ""

    # Caso lista
    if isinstance(raw, list):
        # Buscar el marcado como primary
        for item in raw:
            if isinstance(item, dict) and str(item.get("primary")).lower() == "true":
                return str(item.get("value", "")).strip()
        # Si ninguno es primary, tomar el primero
        first = raw[0]
        if isinstance(first, dict):
            return str(first.get("value", "")).strip()
        return str(first).strip()

    # Caso dict
    if isinstance(raw, dict):
        return str(raw.get("value", "")).strip()

    # Caso string
    return str(raw).strip()


def compute_fingerprint(smiles: str) -> str | None:
    """
    Morgan/ECFP4 → string FPS. Idéntico a sandbox_service.compute_fingerprint.
    """
    if not RDKIT_OK or not smiles:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    fp = _MORGAN_GEN.GetFingerprint(mol)
    return DataStructs.BitVectToFPSText(fp)


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def populate(
    mongo_db,
    neo4j_session,
    limit: int | None = None,
    batch_size: int = 200,
    overwrite: bool = False,
) -> dict:
    """
    Recorre los fármacos en MongoDB, calcula fingerprints y los escribe en Neo4j.

    Parámetros:
        mongo_db        : objeto Database de pymongo (debe tener .drugs)
        neo4j_session   : sesión Neo4j abierta
        limit           : máx. de fármacos a procesar (None = todos)
        batch_size      : nodos por transacción de escritura a Neo4j
        overwrite       : si False, solo escribe en nodos sin fingerprint previo

    Retorna estadísticas del proceso.
    """
    if not RDKIT_OK:
        raise RuntimeError("RDKit no está instalado. pip install rdkit")

    start = time.time()

    # Proyección mínima: solo lo necesario para extraer SMILES y el id
    projection = {
        "drugbank-id": 1,
        "calculated-properties": 1,
        "name": 1,
    }

    cursor = mongo_db.drugs.find({}, projection)
    if limit:
        cursor = cursor.limit(limit)

    stats = {
        "processed":      0,
        "no_smiles":      0,
        "invalid_smiles": 0,
        "no_id":          0,
        "written":        0,
        "skipped_existing": 0,
    }

    # Cypher de escritura por lotes con UNWIND (eficiente)
    cypher_write = """
        UNWIND $rows AS row
        MATCH (d:Drug {drugbank_id: row.drugbank_id})
        // Si overwrite es false, no tocar nodos que ya tienen fingerprint
        WITH d, row
        WHERE $overwrite OR d.fingerprint IS NULL OR d.fingerprint = ''
        SET d.fingerprint = row.fingerprint
        RETURN count(d) AS written
    """

    batch: list[dict] = []

    def flush(batch_rows):
        if not batch_rows:
            return 0
        result = neo4j_session.run(
            cypher_write, rows=batch_rows, overwrite=overwrite
        ).single()
        return result["written"] if result else 0

    for drug in cursor:
        stats["processed"] += 1

        drugbank_id = extract_primary_drugbank_id(drug)
        if not drugbank_id:
            stats["no_id"] += 1
            continue

        smiles = extract_smiles(drug)
        if not smiles:
            stats["no_smiles"] += 1
            continue

        fp = compute_fingerprint(smiles)
        if fp is None:
            stats["invalid_smiles"] += 1
            continue

        batch.append({"drugbank_id": drugbank_id, "fingerprint": fp})

        if len(batch) >= batch_size:
            written = flush(batch)
            stats["written"] += written
            stats["skipped_existing"] += len(batch) - written
            batch = []
            elapsed = time.time() - start
            print(
                f"  {stats['processed']:,} procesados  |  "
                f"{stats['written']:,} escritos  ({elapsed:.0f}s)",
                end="\r",
            )

    # Flush final
    written = flush(batch)
    stats["written"] += written
    stats["skipped_existing"] += len(batch) - written

    stats["elapsed_sec"] = round(time.time() - start, 1)
    return stats


def print_report(stats: dict):
    log.info("")
    log.info("═══ Resumen ═══")
    log.info(f"  Fármacos procesados:        {stats['processed']:,}")
    log.info(f"  Fingerprints escritos:      {stats['written']:,}")
    log.info(f"  Saltados (ya tenían FP):    {stats['skipped_existing']:,}")
    log.info(f"  Sin SMILES:                 {stats['no_smiles']:,}")
    log.info(f"  SMILES inválido:            {stats['invalid_smiles']:,}")
    log.info(f"  Sin drugbank-id:            {stats['no_id']:,}")
    log.info(f"  Tiempo:                     {stats['elapsed_sec']}s")
    log.info("")
    log.info("La similitud estructural del sandbox ya está activa.")


# ══════════════════════════════════════════════════════════════════════════════
# MODO STANDALONE (sin Django)
# ══════════════════════════════════════════════════════════════════════════════

def _run_standalone():
    """
    Ejecución directa. Lee config de variables de entorno:
        MONGO_URI       (default mongodb://localhost:27017)
        MONGO_DB        (default druggraph)
        NEO4J_URI       (default bolt://localhost:7687)
        NEO4J_USER      (default neo4j)
        NEO4J_PASSWORD  (requerido)
    """
    import argparse
    from pymongo import MongoClient
    from neo4j import GraphDatabase

    parser = argparse.ArgumentParser(description="Poblar fingerprints en Neo4j")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch", type=int, default=200)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if not RDKIT_OK:
        log.error("RDKit no está instalado. pip install rdkit")
        sys.exit(1)

    mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    mongo_db_name = os.environ.get("MONGO_DB", "druggraph")
    neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_pwd = os.environ.get("NEO4J_PASSWORD")

    if not neo4j_pwd:
        log.error("Define NEO4J_PASSWORD en el entorno.")
        sys.exit(1)

    log.info(f"MongoDB: {mongo_uri} / {mongo_db_name}")
    log.info(f"Neo4j:   {neo4j_uri}")
    log.info("")

    mongo_client = MongoClient(mongo_uri)
    mongo_db = mongo_client[mongo_db_name]
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pwd))

    try:
        with driver.session() as session:
            stats = populate(
                mongo_db, session,
                limit=args.limit, batch_size=args.batch, overwrite=args.overwrite,
            )
        print_report(stats)
    finally:
        driver.close()
        mongo_client.close()


# ══════════════════════════════════════════════════════════════════════════════
# MODO DJANGO MANAGEMENT COMMAND
# ══════════════════════════════════════════════════════════════════════════════
#
# Para usarlo como `python manage.py populate_fingerprints`, copia este archivo a:
#     drugs/management/commands/populate_fingerprints.py
# y descomenta el bloque siguiente (requiere config.mongo.get_db y
# config.neo4j_service.get_driver, que ya tienes en el proyecto):
#
# from django.core.management.base import BaseCommand
# from config.services.mongo import get_db
# from config.services.neo4j_service import get_driver
#
# class Command(BaseCommand):
#     help = "Calcula fingerprints RDKit y los escribe en los nodos :Drug de Neo4j."
#
#     def add_arguments(self, parser):
#         parser.add_argument("--limit", type=int, default=None)
#         parser.add_argument("--batch", type=int, default=200)
#         parser.add_argument("--overwrite", action="store_true")
#
#     def handle(self, *args, **opts):
#         if not RDKIT_OK:
#             self.stderr.write("RDKit no instalado. pip install rdkit")
#             return
#         db = get_db()
#         driver = get_driver()
#         with driver.session() as session:
#             stats = populate(
#                 db, session,
#                 limit=opts["limit"], batch_size=opts["batch"],
#                 overwrite=opts["overwrite"],
#             )
#         print_report(stats)


if __name__ == "__main__":
    _run_standalone()
