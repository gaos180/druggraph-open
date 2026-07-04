"""ETL paso 3 — MongoDB `drugs` → grafo Neo4j.

Proyecta los documentos de fármaco al mismo modelo de grafo que consumía DrugGraph:
    (:Drug {drugbank_id, name, type, groups, smiles})
    (:Target {drugbank_target_id, uniprot_id, name, organism, gene_name})
    (:Category {name})
    (:Drug)-[:TARGETS {actions, known_action, role}]->(:Target)
    (:Drug)-[:IN_CATEGORY]->(:Category)

Las DDIs (:INTERACTS_WITH) las carga step04. Los :Gene / STRING_ASSOC / REGULATES los
cargan los scripts heredados (load_string_network.py, load_kegg_regulatory.py), ya open.

Uso:  python -m scripts.ingest.step03_build_graph
"""
from __future__ import annotations

from scripts.ingest._common import log, mongo_db, neo4j_driver, chunked

# Cypher idempotente por lotes (UNWIND). Un solo tipo de relación base TARGETS: la app
# agrupa por type(r) y usa r.actions como semántica (igual que sobre DrugBank).
_DRUG_CYPHER = """
UNWIND $rows AS row
MERGE (d:Drug {drugbank_id: row.drugbank_id})
  SET d.name   = row.name,
      d.type   = row.type,
      d.groups = row.groups,
      d.smiles = row.smiles
WITH d, row
CALL {
    WITH d, row
    UNWIND row.targets AS t
    MERGE (tg:Target {drugbank_target_id: t.target_key})
      SET tg.name       = t.name,
          tg.uniprot_id = t.uniprot_id,
          tg.gene_name  = t.gene_name,
          tg.organism   = t.organism
    MERGE (d)-[r:TARGETS]->(tg)
      SET r.actions      = t.actions,
          r.known_action = t.known_action,
          r.role         = t.role
}
CALL {
    WITH d, row
    UNWIND row.categories AS c
    MERGE (cat:Category {name: c})
    MERGE (d)-[:IN_CATEGORY]->(cat)
}
"""


def _target_key(t: dict) -> str:
    """Clave estable de :Target: UniProt si existe, si no un id sintético DrugCentral."""
    if t.get("uniprot_id"):
        return t["uniprot_id"]
    if t.get("position"):
        return f"DCT{t['position']}"
    return f"NAME:{(t.get('name') or 'unknown')[:80]}"


def _rows_from_docs(docs):
    for doc in docs:
        targets = []
        for t in doc.get("targets", []):
            targets.append({
                "target_key": _target_key(t),
                "name": t.get("name") or "",
                "uniprot_id": t.get("uniprot_id") or "",
                "gene_name": t.get("gene_name") or "",
                "organism": t.get("organism") or "Homo sapiens",
                "actions": t.get("actions") or [],
                "known_action": t.get("known_action") or "unknown",
                "role": t.get("target_class") or "",
            })
        categories = sorted({
            c.get("category") for c in doc.get("categories", []) if c.get("category")
        })
        yield {
            "drugbank_id": doc["drugbank-id"],
            "name": doc.get("name") or "",
            "type": doc.get("type") or "small molecule",
            "groups": doc.get("groups") or [],
            "smiles": doc.get("smiles"),
            "targets": targets,
            "categories": categories,
        }


def run(batch: int = 300):
    db = mongo_db()
    driver = neo4j_driver()

    log.info("Asegurando constraints/índices en Neo4j…")
    with driver.session() as s:
        s.run("CREATE CONSTRAINT drug_id IF NOT EXISTS FOR (d:Drug) REQUIRE d.drugbank_id IS UNIQUE")
        s.run("CREATE CONSTRAINT target_id IF NOT EXISTS FOR (t:Target) REQUIRE t.drugbank_target_id IS UNIQUE")
        s.run("CREATE CONSTRAINT category_name IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE")
        s.run("CREATE INDEX drug_name IF NOT EXISTS FOR (d:Drug) ON (d.name)")
        s.run("CREATE INDEX target_uniprot IF NOT EXISTS FOR (t:Target) ON (t.uniprot_id)")

    cursor = db.drugs.find(
        {},
        {"drugbank-id": 1, "name": 1, "type": 1, "groups": 1, "smiles": 1,
         "targets": 1, "categories": 1},
    )

    total = 0
    for group in chunked(_rows_from_docs(cursor), batch):
        with driver.session() as s:
            s.run(_DRUG_CYPHER, rows=group)
        total += len(group)
        log.info("  … %d fármacos proyectados al grafo", total)

    log.info("Grafo construido: %d :Drug. Ahora corre populate_targets.py --uniprot.", total)
    return total


if __name__ == "__main__":
    run()
