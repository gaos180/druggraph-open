#!/usr/bin/env python3
"""
load_string_network.py — Carga la red PPI de STRING (humano) en Neo4j.

Fuente: STRING v12.0  https://stringdb-downloads.org/
        9606.protein.links.v12.0.txt.gz   (protein1 protein2 combined_score)
        9606.protein.info.v12.0.txt.gz    (string_protein_id → preferred_name)

Motivo: la propagación de efectos en cadena (cascada) necesita recorrer la red
PPI muchas veces; la API de STRING (1 req/s) lo hace inviable. Aquí se carga la
red localmente en Neo4j para correr propagación con GDS (Personalized PageRank /
Random Walk) de forma instantánea.

MODELO EN NEO4J:
    (:Gene {name})  -[:STRING_ASSOC {score}]->  (:Gene {name})
    score ∈ [umbral, 999]; aristas no dirigidas (se guarda una sola dirección,
    GDS las proyecta como UNDIRECTED). Los :Gene se cruzan con los :Target
    existentes por gene_name al sembrar la propagación.

USO:
    python load_string_network.py                       # umbral 700
    python load_string_network.py --min-score 400
    python load_string_network.py --links ruta.gz --info ruta.gz

Variables de entorno: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD (defaults docker).

Dependencias: pip install neo4j
"""

import os
import gzip
import time
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("string")

DEF_LINKS = "/home/gabriel/string_data/9606.protein.links.v12.0.txt.gz"
DEF_INFO  = "/home/gabriel/string_data/9606.protein.info.v12.0.txt.gz"
DEFAULT_MIN_SCORE = 700


def get_driver():
    from neo4j import GraphDatabase
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    pwd = os.environ.get("NEO4J_PASSWORD", "druggraph123")
    return GraphDatabase.driver(uri, auth=(user, pwd))


def load_info(path: str) -> dict:
    """ENSP id → símbolo de gen (preferred_name)."""
    mapping = {}
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                mapping[parts[0]] = parts[1]
    return mapping


def parse_edges(links_path: str, ensp2gene: dict, min_score: int):
    """
    Genera aristas (gene_a, gene_b, score) no dirigidas y deduplicadas
    (gene_a < gene_b lexicográfico), quedándose con el mejor score por par.
    """
    best: dict = {}
    rows = 0
    kept = 0
    t0 = time.time()
    with gzip.open(links_path, "rt", encoding="utf-8", errors="replace") as fh:
        header = True
        for line in fh:
            if header:
                header = False
                continue
            rows += 1
            if rows % 4_000_000 == 0:
                log.info("  %d aristas leídas, %d pares conservados (%.0fs)…", rows, len(best), time.time() - t0)
            p1, p2, sc = line.split()
            score = int(sc)
            if score < min_score:
                continue
            g1 = ensp2gene.get(p1)
            g2 = ensp2gene.get(p2)
            if not g1 or not g2 or g1 == g2:
                continue
            a, b = (g1, g2) if g1 < g2 else (g2, g1)
            key = (a, b)
            prev = best.get(key)
            if prev is None or score > prev:
                best[key] = score
                kept += 1
    log.info("Lectura: %d aristas, %d pares únicos (score>=%d) en %.0fs",
             rows, len(best), min_score, time.time() - t0)
    return best


def load_to_neo4j(driver, edges: dict):
    genes = set()
    for a, b in edges:
        genes.add(a); genes.add(b)

    with driver.session() as s:
        log.info("Limpiando red STRING previa…")
        # borrar relaciones y nodos :Gene previos en lotes
        while True:
            r = s.run("MATCH ()-[r:STRING_ASSOC]->() WITH r LIMIT 50000 DELETE r RETURN count(r) AS c").single()["c"]
            if r == 0:
                break
        s.run("MATCH (g:Gene) WHERE NOT (g)--() DELETE g")
        s.run("CREATE CONSTRAINT gene_name IF NOT EXISTS FOR (g:Gene) REQUIRE g.name IS UNIQUE")

        # Nodos
        log.info("Creando %d nodos :Gene…", len(genes))
        gene_list = list(genes)
        for i in range(0, len(gene_list), 10000):
            s.run("UNWIND $names AS n MERGE (:Gene {name: n})", names=gene_list[i:i + 10000])

        # Aristas
        log.info("Creando %d aristas :STRING_ASSOC…", len(edges))
        batch = []
        done = 0
        edge_items = [{"a": a, "b": b, "s": sc} for (a, b), sc in edges.items()]
        BATCH = 10000
        for i in range(0, len(edge_items), BATCH):
            chunk = edge_items[i:i + BATCH]
            s.run(
                """
                UNWIND $edges AS e
                MATCH (a:Gene {name: e.a}), (b:Gene {name: e.b})
                CREATE (a)-[:STRING_ASSOC {score: e.s}]->(b)
                """,
                edges=chunk,
            )
            done += len(chunk)
            if done % 50000 == 0:
                log.info("  %d/%d aristas…", done, len(edge_items))

        # Tag de cuántos :Gene coinciden con :Target
        matched = s.run(
            "MATCH (g:Gene) WHERE EXISTS { MATCH (t:Target) WHERE t.gene_name = g.name } RETURN count(g) AS c"
        ).single()["c"]
        log.info("Nodos :Gene que cruzan con :Target existentes: %d", matched)


def main():
    ap = argparse.ArgumentParser(description="Carga la red PPI de STRING (humano) en Neo4j.")
    ap.add_argument("--links", default=DEF_LINKS)
    ap.add_argument("--info", default=DEF_INFO)
    ap.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE)
    args = ap.parse_args()

    log.info("Cargando mapeo ENSP→gen desde %s", args.info)
    ensp2gene = load_info(args.info)
    log.info("  %d proteínas mapeadas", len(ensp2gene))

    edges = parse_edges(args.links, ensp2gene, args.min_score)

    driver = get_driver()
    try:
        load_to_neo4j(driver, edges)
    finally:
        driver.close()
    log.info("Listo. Red STRING cargada en Neo4j (:Gene)-[:STRING_ASSOC]->(:Gene).")


if __name__ == "__main__":
    main()
