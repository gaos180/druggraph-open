"""
neo4j_service.py — Servicio de consultas al grafo Neo4j para DrugGraph.

Ubicación sugerida: config/neo4j_service.py  (junto a config/mongo.py)

Dependencia: pip install neo4j
"""

import logging
from contextlib import contextmanager
from neo4j import GraphDatabase, exceptions as neo4j_exc
from django.conf import settings

log = logging.getLogger(__name__)

# ── Configuración ─────────────────────────────────────────────────────────────
# La conexión se declara en settings.DATABASES["neo4j"] (URI/USER/PASSWORD).

_driver = None


def get_driver():
    """Singleton del driver Neo4j. Se conecta una sola vez por proceso."""
    global _driver
    if _driver is None:
        cfg  = settings.DATABASES_NOSQL["neo4j"]
        uri  = cfg.get("URI",      "bolt://localhost:7687")
        user = cfg.get("USER",     "neo4j")
        pwd  = cfg.get("PASSWORD", "neo4j")
        _driver = GraphDatabase.driver(uri, auth=(user, pwd))
    return _driver


@contextmanager
def _session():
    driver = get_driver()
    session = driver.session()
    try:
        yield session
    finally:
        session.close()


# ── Límites de seguridad ───────────────────────────────────────────────────────
MAX_TARGETS       = 150   # máx. targets/enzimas/etc. por fármaco
MAX_CATEGORIES    = 60    # máx. categorías
MAX_DDI           = 100   # máx. interacciones drug-drug


# ── Consulta principal ────────────────────────────────────────────────────────

def get_drug_graph(drugbank_id: str | None = None, drug_name: str | None = None) -> dict:
    """
    Devuelve la red de interacciones moleculares de un fármaco desde Neo4j.

    Parámetros (al menos uno requerido):
        drugbank_id : str   ej. "DB00001"
        drug_name   : str   ej. "Lepirudin"

    Retorna:
    {
        "drug": { "drugbank_id", "name", "type", "groups" },
        "interactions": [
            {
                "rel_type":         str,   # "TARGETS" | "INHIBITS" | "METABOLIZED_BY" ...
                "rel_base":         str,   # rol estructural: TARGETS/METABOLIZED_BY/...
                "known_action":     str,   # "yes" | "no" | "unknown"
                "actions":         [str],
                "target": {
                    "drugbank_target_id": str,
                    "uniprot_id":         str,
                    "name":               str,
                    "organism":           str,
                    "role":               str,
                }
            }
        ],
        "categories": [
            { "name": str, "mesh_id": str }
        ],
        "drug_interactions": [
            {
                "drugbank_id":  str,
                "name":         str,
                "description":  str,
            }
        ],
        "stats": {
            "total_interactions": int,
            "total_categories":   int,
            "total_ddi":          int,
            "rel_type_counts":   { rel_type: int }
        }
    }
    """
    if not drugbank_id and not drug_name:
        raise ValueError("Se requiere drugbank_id o drug_name")

    # Construir cláusula WHERE para el nodo Drug
    # El campo en Neo4j es drugbank_id (string como "DB00001")
    if drugbank_id:
        drug_match = "MATCH (d:Drug {drugbank_id: $drug_id})"
        params = {"drug_id": drugbank_id}
    else:
        # toLower(d.name) no puede usar el índice RANGE de :Drug(name) → label scan.
        # Sólo se paga en la consulta 1 (resolución del nodo); las consultas 2–4
        # se re-anclan por drugbank_id (indexado) usando el id ya resuelto, así el
        # scan ocurre una vez en lugar de repetirse en las 4 sub-consultas.
        drug_match = "MATCH (d:Drug) WHERE toLower(d.name) = toLower($drug_name)"
        params = {"drug_name": drug_name}

    # Ancla indexada para las consultas de relaciones (siempre por drugbank_id).
    drug_match_by_id = "MATCH (d:Drug {drugbank_id: $drug_id})"

    # ── 1. Datos del nodo Drug ────────────────────────────────────────────────
    cypher_drug = f"""
        {drug_match}
        RETURN d.drugbank_id AS drugbank_id,
               d.name        AS name,
               d.type        AS type,
               d.groups      AS groups
        LIMIT 1
    """

    # ── 2. Todas las relaciones semánticas hacia targets ──────────────────────
    # Recoge CUALQUIER relación saliente del Drug hacia un Target,
    # incluidas las específicas (INHIBITS, ACTIVATES, etc.) y la base (TARGETS).
    # Usamos la relación base (TARGETS/METABOLIZED_BY/etc.) para agrupar,
    # y la semántica (INHIBITS, ACTIVATES, etc.) como etiqueta adicional.
    cypher_interactions = f"""
        {drug_match_by_id}
        MATCH (d)-[r]->(t:Target)
        RETURN type(r)                   AS rel_type,
               r.actions                 AS actions,
               r.known_action            AS known_action,
               r.role                    AS role,
               t.drugbank_target_id      AS target_id,
               t.uniprot_id              AS uniprot_id,
               t.name                    AS target_name,
               t.organism                AS organism
        ORDER BY t.name
        LIMIT {MAX_TARGETS}
    """

    # ── 3. Categorías ─────────────────────────────────────────────────────────
    cypher_categories = f"""
        {drug_match_by_id}
        MATCH (d)-[:IN_CATEGORY]->(c:Category)
        RETURN c.name    AS name,
               c.mesh_id AS mesh_id
        ORDER BY c.name
        LIMIT {MAX_CATEGORIES}
    """

    # ── 4. Drug-drug interactions ─────────────────────────────────────────────
    cypher_ddi = f"""
        {drug_match_by_id}
        MATCH (d)-[r:INTERACTS_WITH]-(d2:Drug)
        RETURN d2.drugbank_id  AS drugbank_id,
               d2.name         AS name,
               r.description   AS description
        ORDER BY d2.name
        LIMIT {MAX_DDI}
    """

    try:
        with _session() as session:
            # Ejecutar las 4 consultas en la misma sesión (transacción implícita)
            drug_result = session.run(cypher_drug, **params).single()
            if not drug_result:
                return {}

            drug_node = {
                "drugbank_id": drug_result["drugbank_id"],
                "name":        drug_result["name"],
                "type":        drug_result["type"],
                "groups":      list(drug_result["groups"] or []),
            }

            # A partir de aquí las sub-consultas se anclan por drugbank_id (índice),
            # tanto si la búsqueda inicial fue por id como por nombre.
            follow_params = {"drug_id": drug_result["drugbank_id"]}

            # Interacciones con targets
            interactions_raw = session.run(cypher_interactions, **follow_params).data()
            interactions = []
            seen_pairs = set()   # (rel_type, target_id) para deduplicar

            for row in interactions_raw:
                key = (row["rel_type"], row["target_id"])
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                interactions.append({
                    "rel_type":    row["rel_type"],
                    "known_action": row.get("known_action") or "unknown",
                    "actions":     list(row.get("actions") or []),
                    "role":        row.get("role") or "",
                    "target": {
                        "drugbank_target_id": row["target_id"]   or "",
                        "uniprot_id":         row["uniprot_id"]  or "",
                        "name":               row["target_name"] or "",
                        "organism":           row["organism"]    or "",
                    },
                })

            # Categorías
            categories = [
                {"name": r["name"], "mesh_id": r.get("mesh_id") or ""}
                for r in session.run(cypher_categories, **follow_params).data()
            ]

            # DDI
            ddi = [
                {
                    "drugbank_id": r["drugbank_id"] or "",
                    "name":        r["name"]        or "",
                    "description": r.get("description") or "",
                }
                for r in session.run(cypher_ddi, **follow_params).data()
            ]

    except neo4j_exc.ServiceUnavailable as exc:
        log.error("Neo4j no disponible: %s", exc)
        raise
    except Exception as exc:
        log.error("Error en consulta Neo4j: %s", exc)
        raise

    # ── Estadísticas ──────────────────────────────────────────────────────────
    rel_counts: dict[str, int] = {}
    for iact in interactions:
        rt = iact["rel_type"]
        rel_counts[rt] = rel_counts.get(rt, 0) + 1

    return {
        "drug":              drug_node,
        "interactions":      interactions,
        "categories":        categories,
        "drug_interactions": ddi,
        "stats": {
            "total_interactions": len(interactions),
            "total_categories":   len(categories),
            "total_ddi":          len(ddi),
            "rel_type_counts":    rel_counts,
        },
    }
