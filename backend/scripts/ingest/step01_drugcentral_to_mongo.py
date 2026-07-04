"""ETL paso 1 — DrugCentral (Postgres staging) → MongoDB `drugs`.

Construye el documento de fármaco con el mismo esquema que consumía DrugGraph sobre
DrugBank (campos heredados `drugbank-id`, `name`, `type`, `groups`, `targets`, …) pero
poblado desde DrugCentral. El ID primario es el ID abierto `DC<struct_id>`.

Uso (desde backend/, con el venv activo y el dump ya restaurado):
    python -m scripts.ingest.step01_drugcentral_to_mongo
    python -m scripts.ingest.step01_drugcentral_to_mongo --limit 200   # prueba rápida

Prerequisito: scripts/ingest/restore_dumps.sh (base 'drugcentral' en el staging).
"""
from __future__ import annotations

import argparse
from collections import defaultdict

from scripts.ingest._common import log, open_id, mongo_db, staging_conn, chunked

DRUGCENTRAL_DB = "drugcentral"

# id_type de la tabla `identifier` que exponemos como cross-refs externos
_EXTERNAL_ID_TYPES = {
    "ChEMBL_ID": "ChEMBL",
    "PUBCHEM_CID": "PubChem CID",
    "KEGG_DRUG": "KEGG Drug",
    "CAS_RN": "CAS",
    "RXNORM": "RxNorm",
    "MESH_SUPPLEMENTAL_RECORD_UI": "MeSH",
    "DRUGBANK_ID": "DrugBank",   # solo referencia cruzada (ID), no dato de DrugBank
    "INN_ID": "INN",
}


def _fetch_all(cur, sql, params=None):
    cur.execute(sql, params or ())
    return cur.fetchall()


def _load_lookup(cur, sql):
    """Ejecuta una consulta struct_id→[filas] y agrupa por struct_id."""
    out = defaultdict(list)
    cur.execute(sql)
    for row in cur.fetchall():
        out[row[0]].append(row[1:])
    return out


def build_documents(limit: int | None = None):
    conn = staging_conn(dbname=DRUGCENTRAL_DB)
    cur = conn.cursor()

    log.info("Cargando tablas auxiliares de DrugCentral…")

    # struct_id → tipo estructural
    types = {r[0]: r[1] for r in _fetch_all(
        cur, "SELECT struct_id, type FROM structure_type")}

    # struct_id → cross-refs [(id_type, identifier)]
    identifiers = _load_lookup(
        cur, "SELECT struct_id, id_type, identifier FROM identifier")

    # struct_id → UNII (subconjunto de identifier)
    unii = {r[0]: r[1] for r in _fetch_all(
        cur, "SELECT struct_id, identifier FROM identifier WHERE id_type = 'UNII'")}

    # struct_id → aprobación (existencia ⇒ 'approved')
    approved = {r[0] for r in _fetch_all(
        cur, "SELECT DISTINCT struct_id FROM approval")}

    # struct_id → clases farmacológicas [(type, name)]
    pharma = _load_lookup(
        cur, "SELECT struct_id, type, name FROM pharma_class")

    # struct_id → ATC [(atc_code, l4_name)]
    atc = _load_lookup(cur, """
        SELECT s.struct_id, s.atc_code, a.l4_name
        FROM struct2atc s LEFT JOIN atc a ON a.code = s.atc_code
    """)

    # struct_id → indicaciones [(relationship_name, concept_name)]
    omop = _load_lookup(cur, """
        SELECT struct_id, relationship_name, concept_name
        FROM omop_relationship
    """)

    # struct_id → dianas (bioactividad). accession/gene pueden venir separados por '|'
    targets = _load_lookup(cur, """
        SELECT struct_id, target_id, target_name, target_class,
               accession, gene, organism, action_type, act_type, act_value, moa
        FROM act_table_full
        WHERE organism = 'Homo sapiens' OR organism IS NULL
    """)

    log.info("Recorriendo `structures`…")
    struct_sql = """
        SELECT id, name, smiles, inchi, inchikey, cas_reg_no, mrdef, cd_molweight, cd_formula
        FROM structures
        ORDER BY id
    """
    if limit:
        struct_sql += f" LIMIT {int(limit)}"

    for (sid, name, smiles, inchi, inchikey, cas, mrdef,
         molweight, formula) in _fetch_all(cur, struct_sql):
        yield _make_doc(
            sid, name, smiles, inchi, inchikey, cas, mrdef, molweight, formula,
            types.get(sid), unii.get(sid), sid in approved,
            identifiers.get(sid, []), pharma.get(sid, []), atc.get(sid, []),
            omop.get(sid, []), targets.get(sid, []),
        )

    cur.close()
    conn.close()


def _map_type(structure_type: str | None) -> str:
    if not structure_type:
        return "small molecule"
    st = structure_type.lower()
    if any(k in st for k in ("biologic", "protein", "antibody", "peptide", "vaccine")):
        return "biotech"
    return "small molecule"


def _split_targets(rows: list) -> list:
    """act_table_full → lista de dianas del documento (una por accession)."""
    out = []
    for (target_id, tname, tclass, accession, gene, organism,
         action_type, act_type, act_value, moa) in rows:
        accs = (accession or "").split("|") if accession else [""]
        genes = (gene or "").split("|") if gene else [""]
        for i, acc in enumerate(accs):
            g = genes[i] if i < len(genes) else (genes[0] if genes else "")
            out.append({
                "position": target_id,
                "name": tname or "",
                "gene_name": (g or "").strip(),
                "uniprot_id": (acc or "").strip(),
                "organism": organism or "Homo sapiens",
                "target_class": tclass or "",
                "actions": [action_type] if action_type else [],
                "known_action": "yes" if moa else "unknown",
                "act_type": act_type or "",
                "act_value": float(act_value) if act_value is not None else None,
            })
    # deduplicar por (uniprot_id, name)
    seen, deduped = set(), []
    for t in out:
        key = (t["uniprot_id"], t["name"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)
    return deduped


def _make_doc(sid, name, smiles, inchi, inchikey, cas, mrdef, molweight, formula,
              structure_type, unii, is_approved, identifiers, pharma, atc, omop, targets):
    oid = open_id(sid)

    externals = []
    for id_type, ident in identifiers:
        label = _EXTERNAL_ID_TYPES.get(id_type)
        if label:
            externals.append({"resource": label, "identifier": ident})

    categories = []
    for ptype, pname in pharma:
        if pname:
            categories.append({"category": pname, "kind": ptype})
    for code, l4 in atc:
        if l4:
            categories.append({"category": l4, "kind": "ATC", "code": code})

    indications, contraindications = [], []
    for rel, concept in omop:
        if not concept:
            continue
        if rel == "indication":
            indications.append(concept)
        elif rel == "contraindication":
            contraindications.append(concept)

    groups = ["approved"] if is_approved else ["experimental"]

    calc_props = []
    if smiles:
        calc_props.append({"kind": "SMILES", "value": smiles, "source": "DrugCentral"})
    if inchi:
        calc_props.append({"kind": "InChI", "value": inchi, "source": "DrugCentral"})
    if inchikey:
        calc_props.append({"kind": "InChIKey", "value": inchikey, "source": "DrugCentral"})
    if formula:
        calc_props.append({"kind": "Molecular Formula", "value": formula, "source": "DrugCentral"})

    return {
        "_id": oid,                     # ID abierto como _id de Mongo (estable, sin ObjectId)
        "drugbank-id": oid,             # campo heredado (compat app) — contiene el ID abierto
        "drugcentral_id": str(sid),
        "name": name,
        "type": _map_type(structure_type),
        "groups": groups,
        "description": (mrdef or "").strip() or None,
        "unii": unii,
        "cas-number": cas,
        "average-mass": float(molweight) if molweight is not None else None,
        "smiles": smiles or None,       # atajo plano usado por sandbox/fingerprints
        "inchikey": inchikey or None,
        "calculated-properties": calc_props,
        "external-identifiers": externals,
        "categories": categories,
        "indications": indications,
        "contraindications": contraindications,
        "targets": _split_targets(targets),
        "drug-interactions": [],        # se rellena en step04 (TWOSIDES)
        "_source": "DrugCentral",
    }


def run(limit: int | None = None, batch: int = 500):
    db = mongo_db()
    coll = db.drugs
    log.info("Vaciando colección `drugs` previa…")
    coll.delete_many({"_source": "DrugCentral"})

    total = 0
    for group in chunked(build_documents(limit=limit), batch):
        ops = []
        from pymongo import ReplaceOne
        for doc in group:
            ops.append(ReplaceOne({"_id": doc["_id"]}, doc, upsert=True))
        if ops:
            coll.bulk_write(ops, ordered=False)
            total += len(ops)
            log.info("  … %d fármacos insertados", total)

    log.info("Creando índices base…")
    coll.create_index("name")
    coll.create_index("type")
    coll.create_index("groups")
    coll.create_index("drugbank-id")
    log.info("Listo: %d documentos en `drugs`.", total)
    return total


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="ETL DrugCentral → MongoDB drugs")
    ap.add_argument("--limit", type=int, default=None, help="límite de fármacos (prueba)")
    ap.add_argument("--batch", type=int, default=500)
    args = ap.parse_args()
    run(limit=args.limit, batch=args.batch)
