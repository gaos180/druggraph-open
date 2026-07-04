#!/usr/bin/env python3
"""
load_omnipath_regulatory.py — Red regulatoria causal con signo desde OmniPath/SIGNOR.

Amplía (o sustituye) la red dirigida con signo de KEGG con las interacciones causales
curadas de OmniPath, que integra SIGNOR, DoRothEA, CollecTRI y muchas otras fuentes.
Cada interacción trae dirección y efecto (estimulación +1 / inhibición -1) por consenso.

Se cargan en Neo4j como:
    (:Gene {name})-[:REGULATES {sign, count, source:'OMNIPATH'}]->(:Gene {name})

Coexiste con las aristas de KEGG (source:'KEGG'): este cargador SOLO borra/gestiona
las aristas con source='OMNIPATH', de modo que ambas fuentes pueden convivir.
`propagation_service.propagate_signed` consume TODAS las aristas :REGULATES, así que
la cascada dirigida se enriquece automáticamente.

USO:
    python load_omnipath_regulatory.py                 # todas las interacciones con signo
    python load_omnipath_regulatory.py --signor-only   # solo las que citan SIGNOR
    python load_omnipath_regulatory.py --limit 2000    # subconjunto (debug)

Variables de entorno: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD (defaults docker).
Dependencias: pip install omnipath neo4j
"""

import os
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("omnipath-reg")


def get_driver():
    from neo4j import GraphDatabase
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    pwd = os.environ.get("NEO4J_PASSWORD", "druggraph123")
    return GraphDatabase.driver(uri, auth=(user, pwd))


def fetch_signed_interactions(signor_only: bool, limit: int) -> list[dict]:
    """Descarga interacciones causales con signo de consenso desde OmniPath."""
    from omnipath.interactions import AllInteractions

    df = AllInteractions.get(organism="human", genesymbols=True)
    # Solo dirigidas y con signo de consenso no ambiguo
    df = df[df["is_directed"] == 1]
    signed = df[(df["consensus_stimulation"] == 1) ^ (df["consensus_inhibition"] == 1)]

    if signor_only:
        signed = signed[signed["sources"].str.contains("SIGNOR", na=False)]

    edges: dict = {}
    for _, r in signed.iterrows():
        a = str(r.get("source_genesymbol") or "").strip()
        b = str(r.get("target_genesymbol") or "").strip()
        if not a or not b or a == b:
            continue
        sign = 1 if r["consensus_stimulation"] == 1 else -1
        key = (a, b)
        prev = edges.get(key)
        count = int(r.get("n_references") or 0) + 1
        if prev is None:
            edges[key] = {"a": a, "b": b, "sign": sign, "count": count}
        else:
            # mismo par: si el signo coincide acumula; si difiere, se queda el de más soporte
            if prev["sign"] == sign:
                prev["count"] += count
            elif count > prev["count"]:
                prev["sign"] = sign
                prev["count"] = count

    items = list(edges.values())
    if limit:
        items = items[:limit]
    return items


def load_to_neo4j(driver, items: list[dict]):
    genes = set()
    for it in items:
        genes.add(it["a"]); genes.add(it["b"])

    with driver.session() as s:
        s.run("CREATE CONSTRAINT gene_name IF NOT EXISTS FOR (g:Gene) REQUIRE g.name IS UNIQUE")

        log.info("Limpiando aristas REGULATES source='OMNIPATH' previas…")
        while s.run(
            "MATCH ()-[r:REGULATES {source:'OMNIPATH'}]->() WITH r LIMIT 50000 "
            "DELETE r RETURN count(r) AS c"
        ).single()["c"] > 0:
            pass

        log.info("Creando %d nodos :Gene (MERGE)…", len(genes))
        gl = list(genes)
        for i in range(0, len(gl), 10000):
            s.run("UNWIND $names AS n MERGE (:Gene {name: n})", names=gl[i:i + 10000])

        log.info("Creando %d aristas :REGULATES (source='OMNIPATH')…", len(items))
        for i in range(0, len(items), 5000):
            s.run(
                """
                UNWIND $edges AS e
                MATCH (a:Gene {name: e.a})
                MATCH (b:Gene {name: e.b})
                CREATE (a)-[:REGULATES {sign: e.sign, count: e.count, source: 'OMNIPATH'}]->(b)
                """,
                edges=items[i:i + 5000],
            )

        pos = s.run("MATCH ()-[r:REGULATES {source:'OMNIPATH'}]->() WHERE r.sign = 1 RETURN count(r) AS c").single()["c"]
        neg = s.run("MATCH ()-[r:REGULATES {source:'OMNIPATH'}]->() WHERE r.sign = -1 RETURN count(r) AS c").single()["c"]
        log.info("Cargadas %d aristas OMNIPATH (%d activación +, %d inhibición -)", len(items), pos, neg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signor-only", action="store_true", help="solo interacciones que citan SIGNOR")
    ap.add_argument("--limit", type=int, default=0, help="máximo de aristas (0 = todas)")
    args = ap.parse_args()

    log.info("Descargando interacciones causales de OmniPath%s…", " (SIGNOR)" if args.signor_only else "")
    items = fetch_signed_interactions(args.signor_only, args.limit)
    log.info("  %d pares dirigidos con signo", len(items))

    if not items:
        log.warning("No hay interacciones que cargar. Abortando.")
        return

    driver = get_driver()
    try:
        load_to_neo4j(driver, items)
    finally:
        driver.close()
    log.info("Listo. Red OmniPath en Neo4j (:Gene)-[:REGULATES {source:'OMNIPATH'}]->(:Gene).")


if __name__ == "__main__":
    main()
