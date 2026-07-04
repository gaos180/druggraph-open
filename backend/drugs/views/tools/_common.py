"""
_common.py — Helpers compartidos por las herramientas analíticas (DEG, repurposing,
toxicidad): lectura de targets de un fármaco (Neo4j) e info básica (MongoDB).
"""

import logging

from config.services.neo4j_service import get_driver
from config.services.mongo import get_db

log = logging.getLogger(__name__)


def _get_drug_targets(drug_id: str) -> list[dict]:
    """Devuelve los targets de un fármaco desde Neo4j."""
    driver = get_driver()
    with driver.session() as session:
        res = session.run(
            """
            MATCH (d:Drug {drugbank_id: $drug_id})-[r]->(t:Target)
            RETURN
              coalesce(t.drugbank_target_id, '') AS target_id,
              coalesce(t.name,      '')  AS name,
              coalesce(t.gene_name, '')  AS gene_name,
              coalesce(t.uniprot_id,'')  AS uniprot_id,
              type(r) AS rel_type
            """,
            drug_id=drug_id
        )
        return [dict(r) for r in res]


def _get_drug_info(drug_id: str) -> dict:
    """Datos básicos de un fármaco desde MongoDB (con fallback a Neo4j)."""
    try:
        db   = get_db()
        doc  = db.drugs.find_one({'drugbank-id': drug_id},
                                  {'name': 1, 'drugbank-id': 1, 'description': 1, '_id': 0})
        if doc:
            return {'name': doc.get('name', drug_id), 'drugbank_id': drug_id}
    except Exception as e:
        log.debug('_get_drug_info MongoDB error para %s: %s', drug_id, e)
    # Fallback a Neo4j
    driver = get_driver()
    with driver.session() as session:
        res = session.run(
            "MATCH (d:Drug {drugbank_id: $id}) RETURN d.name AS name LIMIT 1",
            id=drug_id
        )
        rec = res.single()
        if rec:
            return {'name': rec['name'] or drug_id, 'drugbank_id': drug_id}
    return {'name': drug_id, 'drugbank_id': drug_id}
