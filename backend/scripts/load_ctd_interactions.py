#!/usr/bin/env python3
"""
load_ctd_interactions.py — Carga interacciones químico-gen de CTD a MongoDB.

Fuente: Comparative Toxicogenomics Database (CTD)
        https://ctdbase.org/downloads/  →  CTD_chem_gene_ixns.csv.gz

CTD documenta, con curación de literatura, cómo los químicos interactúan con los
genes (increases/decreases expression/activity, binding, etc.). Esto enriquece el
análisis de red del sandbox: para cada gen diana se sabe qué químicos lo afectan
y de qué forma, ampliando la exploración de "qué afecta y qué posiblemente afecta".

FLUJO:
    CTD_chem_gene_ixns.csv.gz (Homo sapiens)
        │  filtra a genes presentes en Neo4j (:Target.gene_name)
        ▼
    Agregación por gen (nº químicos, nº interacciones, acciones, top químicos)
        ▼
    MongoDB  →  colección  ctd_gene_interactions  (un documento por gen)

Cada documento:
    {
      "_id": "PTGS2", "gene_id": 5743,
      "interaction_count": 5123, "chemical_count": 980,
      "actions": [ {"action": "increases^expression", "count": 410}, ... ],
      "top_chemicals": [
        {"name": "Acetaminophen", "mesh_id": "D000082", "cas": "103-90-2",
         "count": 47, "in_druggraph": true, "drugbank_id": "DB00316"}, ...
      ]
    }

USO:
    python load_ctd_interactions.py                 # descarga + carga
    python load_ctd_interactions.py --file ruta.gz  # usa un .gz ya descargado
    python load_ctd_interactions.py --all-genes      # no filtra por Neo4j (más grande)

Variables de entorno (defaults para docker-compose local):
    MONGO_URI (mongodb://localhost:27017)   MONGO_DB (druggraph)
    NEO4J_URI (bolt://localhost:7687)       NEO4J_USER (neo4j)
    NEO4J_PASSWORD (druggraph123)

Dependencias: pip install pymongo neo4j
"""

import os
import sys
import gzip
import csv
import time
import argparse
import logging
from collections import Counter, defaultdict
from urllib.request import urlopen

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ctd")

CTD_URL = "https://ctdbase.org/reports/CTD_chem_gene_ixns.csv.gz"
DEFAULT_GZ = "/tmp/CTD_chem_gene_ixns.csv.gz"
COLLECTION = "ctd_gene_interactions"
META_COLLECTION = "ctd_meta"

TOP_CHEMICALS = 25
TOP_ACTIONS = 15
HUMAN_ORGANISM = "Homo sapiens"


# ── Conexiones ──────────────────────────────────────────────────────────────────

def get_mongo():
    from pymongo import MongoClient
    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    name = os.environ.get("MONGO_DB", "druggraph")
    return MongoClient(uri)[name]


def get_neo4j_driver():
    from neo4j import GraphDatabase
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    pwd = os.environ.get("NEO4J_PASSWORD", "druggraph123")
    return GraphDatabase.driver(uri, auth=(user, pwd))


# ── Preparación: genes de Neo4j y mapa CAS→DrugBank ──────────────────────────────

def neo4j_gene_set(driver) -> set:
    """Genes (gene_name) presentes en los Target de Neo4j."""
    cypher = """
        MATCH (t:Target)
        WHERE t.gene_name IS NOT NULL AND t.gene_name <> ''
        RETURN DISTINCT t.gene_name AS gene
    """
    with driver.session() as session:
        genes = {r["gene"] for r in session.run(cypher)}
    return genes


def primary_drugbank_id(raw):
    """
    El campo `drugbank-id` de DrugBank puede ser str, dict {value, primary} o
    una lista mixta. Devuelve el ID primario como string limpio (ej. 'DB00945').
    """
    if isinstance(raw, str):
        return raw if raw.startswith("DB") else None
    if isinstance(raw, dict):
        v = raw.get("value")
        return v if isinstance(v, str) and v.startswith("DB") else None
    if isinstance(raw, list):
        # Preferir el marcado primary=true
        for item in raw:
            if isinstance(item, dict) and str(item.get("primary")).lower() == "true":
                v = item.get("value")
                if isinstance(v, str) and v.startswith("DB"):
                    return v
        # Si no, el primer DB... que aparezca
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get("value"), str) and item["value"].startswith("DB"):
                return item["value"]
            if isinstance(item, str) and item.startswith("DB"):
                return item
    return None


def cas_to_drugbank(db) -> dict:
    """Mapa CAS → drugbank_id (string primario) desde la colección drugs de Mongo."""
    mapping = {}
    for d in db.drugs.find({"cas-number": {"$ne": None}}, {"cas-number": 1, "drugbank-id": 1}):
        cas = d.get("cas-number")
        dbid = primary_drugbank_id(d.get("drugbank-id"))
        if cas and dbid:
            mapping[cas] = dbid
    return mapping


# ── Descarga ────────────────────────────────────────────────────────────────────

def download(url: str, dest: str):
    if os.path.exists(dest) and os.path.getsize(dest) > 1_000_000:
        log.info("Usando archivo existente: %s (%.1f MB)", dest, os.path.getsize(dest) / 1e6)
        return
    log.info("Descargando %s …", url)
    t0 = time.time()
    with urlopen(url, timeout=120) as resp, open(dest, "wb") as f:
        total = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
    log.info("Descargado %.1f MB en %.1fs", total / 1e6, time.time() - t0)


# ── Procesamiento ────────────────────────────────────────────────────────────────

def process(gz_path: str, gene_filter: set | None, cas_map: dict) -> dict:
    """
    Lee el .gz línea a línea, filtra a humano (+ genes Neo4j si gene_filter)
    y agrega por gen. Devuelve { gene: doc }.
    """
    # Agregadores por gen
    gene_id: dict = {}
    inter_count: Counter = Counter()
    actions: dict = defaultdict(Counter)            # gene -> Counter(action)
    chem_count: dict = defaultdict(Counter)         # gene -> Counter(chem_name)
    chem_meta: dict = {}                            # chem_name -> (mesh, cas)

    rows_total = 0
    rows_kept = 0
    t0 = time.time()

    with gzip.open(gz_path, "rt", encoding="utf-8", errors="replace") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            # ChemicalName,ChemicalID,CasRN,GeneSymbol,GeneID,GeneForms,Organism,OrganismID,Interaction,InteractionActions,PubMedIDs
            if len(row) < 11:
                continue
            rows_total += 1
            if rows_total % 2_000_000 == 0:
                log.info("  %d filas leídas, %d conservadas (%.0fs)…", rows_total, rows_kept, time.time() - t0)

            organism = row[6]
            if organism != HUMAN_ORGANISM:
                continue
            gene = row[3]
            if not gene or (gene_filter is not None and gene not in gene_filter):
                continue

            chem_name = row[0]
            mesh = row[1]
            cas = row[2]
            gid = row[4]
            ixn_actions = row[9]

            rows_kept += 1
            if gene not in gene_id and gid:
                try:
                    gene_id[gene] = int(gid)
                except ValueError:
                    pass
            inter_count[gene] += 1
            for act in ixn_actions.split("|"):
                act = act.strip()
                if act:
                    actions[gene][act] += 1
            chem_count[gene][chem_name] += 1
            if chem_name not in chem_meta:
                chem_meta[chem_name] = (mesh, cas)

    log.info("Lectura completa: %d filas, %d conservadas (humano + filtro gen) en %.0fs",
             rows_total, rows_kept, time.time() - t0)

    # Construir documentos
    docs = {}
    for gene, cnt in inter_count.items():
        top_chems = []
        for chem_name, c in chem_count[gene].most_common(TOP_CHEMICALS):
            mesh, cas = chem_meta.get(chem_name, ("", ""))
            dbid = cas_map.get(cas) if cas else None
            top_chems.append({
                "name": chem_name,
                "mesh_id": mesh,
                "cas": cas,
                "count": c,
                "in_druggraph": dbid is not None,
                "drugbank_id": dbid,
            })
        docs[gene] = {
            "_id": gene,
            "gene_id": gene_id.get(gene),
            "interaction_count": cnt,
            "chemical_count": len(chem_count[gene]),
            "actions": [{"action": a, "count": n} for a, n in actions[gene].most_common(TOP_ACTIONS)],
            "top_chemicals": top_chems,
        }
    return docs


# ── Carga a MongoDB ──────────────────────────────────────────────────────────────

def load_to_mongo(db, docs: dict):
    coll = db[COLLECTION]
    coll.drop()
    if docs:
        BATCH = 2000
        items = list(docs.values())
        for i in range(0, len(items), BATCH):
            coll.insert_many(items[i:i + BATCH], ordered=False)
    # Nota: la única consulta es find({_id:{$in}}) (índice _id automático);
    # no se crean índices sobre chemical_count/interaction_count porque no se usan.

    total_ixns = sum(d["interaction_count"] for d in docs.values())
    db[META_COLLECTION].update_one(
        {"_id": "ctd_gene_interactions"},
        {"$set": {
            "source": CTD_URL,
            "loaded_at": time.time(),
            "gene_count": len(docs),
            "total_interactions": total_ixns,
        }},
        upsert=True,
    )
    log.info("Cargados %d genes (%d interacciones agregadas) en '%s'",
             len(docs), total_ixns, COLLECTION)


# ── Main ─────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Carga CTD chemical-gene interactions a MongoDB.")
    ap.add_argument("--file", default=DEFAULT_GZ, help="Ruta al .csv.gz (se descarga si no existe).")
    ap.add_argument("--all-genes", action="store_true", help="No filtrar por genes de Neo4j.")
    args = ap.parse_args()

    db = get_mongo()
    log.info("MongoDB OK (%d fármacos)", db.drugs.estimated_document_count())

    gene_filter = None
    if not args.all_genes:
        driver = get_neo4j_driver()
        gene_filter = neo4j_gene_set(driver)
        driver.close()
        log.info("Genes diana en Neo4j: %d", len(gene_filter))

    cas_map = cas_to_drugbank(db)
    log.info("Mapa CAS→DrugBank: %d entradas", len(cas_map))

    download(CTD_URL, args.file)
    docs = process(args.file, gene_filter, cas_map)
    load_to_mongo(db, docs)

    # Muestra
    sample = sorted(docs.values(), key=lambda d: d["interaction_count"], reverse=True)[:5]
    log.info("Top genes por nº de interacciones:")
    for d in sample:
        log.info("  %s: %d interacciones, %d químicos | top: %s",
                 d["_id"], d["interaction_count"], d["chemical_count"],
                 ", ".join(c["name"] for c in d["top_chemicals"][:3]))


if __name__ == "__main__":
    main()
