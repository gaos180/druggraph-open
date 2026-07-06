"""
molecule_analysis_service.py — Análisis molecular integral ("laboratorio"), agrega herramientas.

Corre en una sola llamada las herramientas basadas en SMILES sobre una molécula (SMILES o ID del
catálogo) y devuelve un resultado combinado, para un panel tipo sandbox:

  propiedades · vecinos estructurales · espacio químico · pharmacóforo · ADMET · toxicidad Chemprop
  · dianas predichas (DTI-GNN) · repurposing (Disease-GNN)

Cada sección degrada de forma independiente (campo `available`): si falta una dependencia, esa
sección se marca no-disponible pero el resto responde. El **docking es aparte** (extra opcional,
vía /api/tools/docking/) — y puede apuntar a las dianas predichas aquí.

Si la molécula no está en el catálogo, las secciones de red usan su vecino estructural más cercano
como proxy (se indica en `network.proxy_drug`).
"""
import logging
import os
import sys

log = logging.getLogger(__name__)

_CATALOG = None  # cache: lista de (drug_id, name, fp)


def _resolve(query: str) -> tuple[str, str | None]:
    """Devuelve (smiles, drug_id|None). Acepta SMILES crudo o un ID del catálogo (DCxxxx/DBxxxx)."""
    q = (query or "").strip()
    if not q:
        return "", None
    if q[:2].upper() in ("DC", "DB") and q[2:].isdigit():
        try:
            from config.services.mongo import get_db
            from config.services.chemberta_index import _smiles_for
            return _smiles_for(get_db(), q.upper()), q.upper()
        except Exception:
            return "", None
    return q, None


def _catalog():
    global _CATALOG
    if _CATALOG is None:
        from rdkit import Chem
        from config.services.sandbox_service._chemistry import _MORGAN_GEN
        from config.services.mongo import get_db
        _CATALOG = []
        for d in get_db().drugs.find({"smiles": {"$exists": True, "$ne": ""}},
                                     {"name": 1, "smiles": 1, "drugbank-id": 1}):
            smi = d.get("smiles")
            if not isinstance(smi, str):
                continue
            m = Chem.MolFromSmiles(smi)
            if m is None:
                continue
            dbid = d.get("drugbank-id")
            dbid = dbid.get("value") if isinstance(dbid, dict) else dbid
            _CATALOG.append((str(dbid), d.get("name", ""), _MORGAN_GEN.GetFingerprint(m)))
    return _CATALOG


def _properties(smiles):
    from rdkit import Chem
    from rdkit.Chem import Descriptors, QED, RDConfig
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"available": False}
    try:
        sys.path.append(os.path.join(RDConfig.RDContribDir, "SA_Score"))
        import sascorer
        sa = round(float(sascorer.calculateScore(mol)), 2)
    except Exception:
        sa = None
    return {"available": True, "formula": Chem.rdMolDescriptors.CalcMolFormula(mol),
            "mw": round(Descriptors.MolWt(mol), 1), "logp": round(Descriptors.MolLogP(mol), 2),
            "hbd": Descriptors.NumHDonors(mol), "hba": Descriptors.NumHAcceptors(mol),
            "tpsa": round(Descriptors.TPSA(mol), 1), "rot_bonds": Descriptors.NumRotatableBonds(mol),
            "qed": round(float(QED.qed(mol)), 3), "sa_score": sa,
            "lipinski_ok": int((Descriptors.MolWt(mol) <= 500) + (Descriptors.MolLogP(mol) <= 5)
                               + (Descriptors.NumHDonors(mol) <= 5) + (Descriptors.NumHAcceptors(mol) <= 10))}


def _neighbors(smiles, drug_id, top=8):
    from rdkit import Chem
    from rdkit import DataStructs
    from config.services.sandbox_service._chemistry import _MORGAN_GEN
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return []
    fp = _MORGAN_GEN.GetFingerprint(mol)
    sims = []
    for did, name, dfp in _catalog():
        if did == drug_id:
            continue
        sims.append((round(float(DataStructs.TanimotoSimilarity(fp, dfp)), 3), did, name))
    sims.sort(reverse=True)
    return [{"similarity": s, "drug_id": i, "name": n} for s, i, n in sims[:top]]


def build(query: str, include_network: bool = True) -> dict:
    smiles, drug_id = _resolve(query)
    if not smiles:
        return {"available": False, "reason": "SMILES/ID inválido o sin estructura."}

    out = {"available": True, "query": query, "drug_id": drug_id, "smiles": smiles,
           "properties": _properties(smiles), "neighbors": _neighbors(smiles, drug_id)}

    def _safe(name, fn):
        try:
            out[name] = fn()
        except Exception as exc:
            log.debug("molecule_analysis %s error: %s", name, exc)
            out[name] = {"available": False, "reason": str(exc)[:120]}

    # Secciones del panel base (rápidas). La toxicidad Chemprop y el docking se piden aparte
    # como "extras" opcionales (endpoints propios) por ser lentos.
    _safe("chemical_space", lambda: __import__("config.services.chemical_space_service",
          fromlist=["locate"]).locate(smiles))
    _safe("pharmacophore", lambda: __import__("config.services.pharmacophore_service",
          fromlist=["build"]).build([smiles]))
    _safe("admet", lambda: __import__("config.services.admet_service",
          fromlist=["predict"]).predict(smiles))

    # Red: dianas/repurposing sobre el ID (o el vecino más cercano como proxy).
    if include_network:
        ref = drug_id or (out["neighbors"][0]["drug_id"] if out["neighbors"] else None)
        proxy = None if drug_id else (out["neighbors"][0] if out["neighbors"] else None)
        net = {"reference_drug_id": ref, "proxy_drug": proxy,
               "documented_targets": [], "predicted_targets": [], "repurposing": []}
        if ref:
            try:
                from config.services.neo4j_service import _session
                with _session() as s:
                    net["documented_targets"] = s.run(
                        "MATCH (d:Drug {drugbank_id:$id})-[:TARGETS]->(t:Target) "
                        "RETURN t.name AS name, t.gene_name AS gene, t.uniprot_id AS uniprot LIMIT 15",
                        id=ref).data()
            except Exception as exc:
                log.debug("targets error: %s", exc)
            try:
                from config.services import dti_gnn_service as dti
                r = dti.predict_for_drug(ref, top_n=8)
                net["predicted_targets"] = r.get("predictions", [])
            except Exception as exc:
                log.debug("dti error: %s", exc)
            try:
                from config.services import disease_gnn_service as dg
                r = dg.predict_for_drug(ref, top_n=8)
                net["repurposing"] = r.get("predictions", [])
            except Exception as exc:
                log.debug("disease error: %s", exc)
        out["network"] = net

    return out
