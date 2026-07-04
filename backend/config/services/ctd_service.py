"""
ctd_service.py — Consulta de interacciones químico-gen de CTD (MongoDB).

Los datos los carga el script standalone `load_ctd_interactions.py` en la
colección `ctd_gene_interactions` (un documento por gen humano presente en
Neo4j). Aquí solo se consulta para enriquecer el análisis de red del sandbox.

CTD aporta evidencia curada de literatura sobre cómo los químicos afectan a los
genes (increases/decreases expression/activity, binding…), extendiendo la
exploración de "qué afecta y qué posiblemente afecta" a los genes diana.
"""

import logging
from config.services.mongo import get_db

log = logging.getLogger(__name__)

COLLECTION = "ctd_gene_interactions"
META_COLLECTION = "ctd_meta"


def is_available() -> bool:
    """True si la colección CTD existe y tiene datos."""
    try:
        db = get_db()
        if COLLECTION not in db.list_collection_names():
            return False
        return db[COLLECTION].estimated_document_count() > 0
    except Exception as exc:
        log.warning("ctd_service.is_available error: %s", exc)
        return False


def meta() -> dict:
    """Metadatos de la carga (fecha, nº de genes, fuente)."""
    try:
        return get_db()[META_COLLECTION].find_one({"_id": "ctd_gene_interactions"}) or {}
    except Exception as e:
        log.debug('ctd_service.meta error: %s', e)
        return {}


def gene_interactions(genes: list[str], max_chemicals_per_gene: int = 12) -> dict:
    """
    Devuelve las interacciones químico-gen de CTD para un conjunto de genes.

    Retorna:
        {
          "available": bool,
          "genes": [
            { "gene", "gene_id", "interaction_count", "chemical_count",
              "actions": [ {action, count} ],
              "top_chemicals": [ {name, mesh_id, cas, count, in_druggraph, drugbank_id} ] }
          ],
          "summary": {
            "genes_with_data": int,
            "total_interactions": int,
            "top_chemicals": [
              { "name", "cas", "drugbank_id", "in_druggraph",
                "gene_count", "total_count", "genes": [str] }
            ]
          }
        }
    """
    genes = [g for g in dict.fromkeys(g for g in genes if g)]  # dedup preservando orden
    if not genes:
        return {"available": is_available(), "genes": [], "summary": None}

    if not is_available():
        return {"available": False, "genes": [], "summary": None}

    db = get_db()
    docs = list(db[COLLECTION].find({"_id": {"$in": genes}}))

    # Normalizar y recortar químicos por gen para la UI
    per_gene = []
    for d in docs:
        per_gene.append({
            "gene": d["_id"],
            "gene_id": d.get("gene_id"),
            "interaction_count": d.get("interaction_count", 0),
            "chemical_count": d.get("chemical_count", 0),
            "actions": d.get("actions", [])[:8],
            "top_chemicals": d.get("top_chemicals", [])[:max_chemicals_per_gene],
        })
    per_gene.sort(key=lambda x: x["interaction_count"], reverse=True)

    # Agregado: químicos que afectan al mayor nº de estos genes
    chem_agg: dict = {}
    for d in docs:
        gene = d["_id"]
        for c in d.get("top_chemicals", []):
            key = c["name"]
            entry = chem_agg.setdefault(key, {
                "name": c["name"],
                "cas": c.get("cas") or "",
                "drugbank_id": c.get("drugbank_id"),
                "in_druggraph": c.get("in_druggraph", False),
                "gene_count": 0,
                "total_count": 0,
                "genes": [],
            })
            entry["gene_count"] += 1
            entry["total_count"] += c.get("count", 0)
            entry["genes"].append(gene)
            if c.get("drugbank_id") and not entry["drugbank_id"]:
                entry["drugbank_id"] = c["drugbank_id"]
                entry["in_druggraph"] = True

    top_chemicals = sorted(
        chem_agg.values(),
        key=lambda x: (x["gene_count"], x["total_count"]),
        reverse=True,
    )[:25]

    return {
        "available": True,
        "genes": per_gene,
        "summary": {
            "genes_with_data": len(per_gene),
            "total_interactions": sum(g["interaction_count"] for g in per_gene),
            "top_chemicals": top_chemicals,
        },
    }
