#!/usr/bin/env python3
"""
load_kegg_regulatory.py — Red regulatoria dirigida y con signo desde KEGG KGML.

Para dar SIGNO (activación +1 / inhibición -1) y DIRECCIÓN (upstream→downstream)
a la cascada de efectos, se descargan los KGML de las rutas humanas de KEGG y se
extraen las relaciones dirigidas entre genes:

    activation / expression  →  +1   (entry1 ──▶ entry2)
    inhibition / repression  →  -1   (entry1 ──┤ entry2)

Se cargan en Neo4j como:
    (:Gene {name})-[:REGULATES {sign, count, source:'KEGG'}]->(:Gene {name})

A diferencia de STRING (no dirigido, sin signo, para magnitud de difusión), esta
red permite propagar el SENTIDO del efecto: si el fármaco inhibe una diana, qué
genes downstream quedan activados o reprimidos.

USO:
    python load_kegg_regulatory.py
    python load_kegg_regulatory.py --limit 50      # solo primeras 50 rutas (debug)

Variables de entorno: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD (defaults docker).
Dependencias: pip install neo4j requests
"""

import os
import time
import argparse
import logging
import xml.etree.ElementTree as ET
from collections import defaultdict

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("kegg-reg")

KEGG = "https://rest.kegg.jp"
RATE = 0.34  # ~3 req/s (recomendación KEGG)

# Subtipos KGML → signo
SIGN = {
    "activation": +1, "expression": +1,
    "inhibition": -1, "repression": -1,
}
MAX_GROUP = 12  # no expandir complejos/grupos enormes (evita explosión combinatoria)


def get_driver():
    from neo4j import GraphDatabase
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    pwd = os.environ.get("NEO4J_PASSWORD", "druggraph123")
    return GraphDatabase.driver(uri, auth=(user, pwd))


_last = [0.0]
def _rate():
    dt = time.time() - _last[0]
    if dt < RATE:
        time.sleep(RATE - dt)
    _last[0] = time.time()


def kegg_get(path: str) -> str:
    _rate()
    r = requests.get(f"{KEGG}/{path}", timeout=30)
    return r.text if r.status_code == 200 else ""


def load_hsa_symbols() -> dict:
    """hsa:id → símbolo de gen (primer token del 4º campo de list/hsa)."""
    txt = kegg_get("list/hsa")
    mapping = {}
    for line in txt.splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            hsa_id = parts[0]                      # hsa:5743
            names = parts[3].split(";")[0]          # "PTGS2, COX2, ..."
            sym = names.split(",")[0].strip()
            if hsa_id and sym:
                mapping[hsa_id] = sym
    return mapping


def human_pathways() -> list[str]:
    txt = kegg_get("list/pathway/hsa")
    ids = []
    for line in txt.splitlines():
        pid = line.split("\t")[0].replace("path:", "").strip()
        if pid:
            ids.append(pid)
    return ids


def parse_kgml(kgml: str, hsa2sym: dict):
    """Devuelve lista de aristas (g1, g2, sign) de una ruta."""
    try:
        root = ET.fromstring(kgml)
    except ET.ParseError:
        return []

    # entry_id → genes (símbolos)
    entry_genes: dict = {}
    for entry in root.findall("entry"):
        if entry.get("type") != "gene":
            continue
        syms = []
        for hsa in entry.get("name", "").split():
            sym = hsa2sym.get(hsa)
            if sym:
                syms.append(sym)
        if syms and len(syms) <= MAX_GROUP:
            entry_genes[entry.get("id")] = syms

    edges = []
    for rel in root.findall("relation"):
        e1, e2 = rel.get("entry1"), rel.get("entry2")
        g1s = entry_genes.get(e1)
        g2s = entry_genes.get(e2)
        if not g1s or not g2s:
            continue
        sign = 0
        for sub in rel.findall("subtype"):
            s = SIGN.get(sub.get("name"))
            if s is not None:
                sign = s  # último subtipo con signo gana
        if sign == 0:
            continue
        for g1 in g1s:
            for g2 in g2s:
                if g1 != g2:
                    edges.append((g1, g2, sign))
    return edges


def load_to_neo4j(driver, agg: dict):
    """agg: (g1,g2) → {'pos':n,'neg':n}. Carga aristas REGULATES con signo neto."""
    items = []
    for (g1, g2), v in agg.items():
        pos, neg = v["pos"], v["neg"]
        if pos == neg:
            continue  # signo ambiguo → omitir
        sign = 1 if pos > neg else -1
        items.append({"a": g1, "b": g2, "sign": sign, "count": pos + neg})

    genes = set()
    for it in items:
        genes.add(it["a"]); genes.add(it["b"])

    with driver.session() as s:
        log.info("Limpiando red REGULATES previa…")
        while s.run("MATCH ()-[r:REGULATES]->() WITH r LIMIT 50000 DELETE r RETURN count(r) AS c").single()["c"] > 0:
            pass
        s.run("CREATE CONSTRAINT gene_name IF NOT EXISTS FOR (g:Gene) REQUIRE g.name IS UNIQUE")

        log.info("Creando %d nodos :Gene (MERGE)…", len(genes))
        gl = list(genes)
        for i in range(0, len(gl), 10000):
            s.run("UNWIND $names AS n MERGE (:Gene {name: n})", names=gl[i:i + 10000])

        log.info("Creando %d aristas :REGULATES…", len(items))
        for i in range(0, len(items), 5000):
            s.run(
                """
                UNWIND $edges AS e
                MATCH (a:Gene {name: e.a})
                MATCH (b:Gene {name: e.b})
                CREATE (a)-[:REGULATES {sign: e.sign, count: e.count, source: 'KEGG'}]->(b)
                """,
                edges=items[i:i + 5000],
            )

        pos = s.run("MATCH ()-[r:REGULATES]->() WHERE r.sign = 1 RETURN count(r) AS c").single()["c"]
        neg = s.run("MATCH ()-[r:REGULATES]->() WHERE r.sign = -1 RETURN count(r) AS c").single()["c"]
        log.info("Cargadas %d aristas REGULATES (%d activación +, %d inhibición -)", len(items), pos, neg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="máximo de rutas (0 = todas)")
    args = ap.parse_args()

    log.info("Descargando mapeo hsa→símbolo…")
    hsa2sym = load_hsa_symbols()
    log.info("  %d genes humanos", len(hsa2sym))

    pathways = human_pathways()
    if args.limit:
        pathways = pathways[:args.limit]
    log.info("Procesando %d rutas (KGML, rate-limited)…", len(pathways))

    agg: dict = defaultdict(lambda: {"pos": 0, "neg": 0})
    t0 = time.time()
    for i, pid in enumerate(pathways, 1):
        kgml = kegg_get(f"get/{pid}/kgml")
        if not kgml:
            continue
        for g1, g2, sign in parse_kgml(kgml, hsa2sym):
            key = (g1, g2)
            agg[key]["pos" if sign > 0 else "neg"] += 1
        if i % 50 == 0:
            log.info("  %d/%d rutas, %d pares dirigidos (%.0fs)…", i, len(pathways), len(agg), time.time() - t0)

    log.info("Extracción completa: %d pares (g1→g2) en %.0fs", len(agg), time.time() - t0)

    driver = get_driver()
    try:
        load_to_neo4j(driver, agg)
    finally:
        driver.close()
    log.info("Listo. Red regulatoria KEGG en Neo4j (:Gene)-[:REGULATES {sign}]->(:Gene).")


if __name__ == "__main__":
    main()
