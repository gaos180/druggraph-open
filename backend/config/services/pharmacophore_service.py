"""
pharmacophore_service.py — Modelado de pharmacóforos 3D ligand-based (Tier 5.1).

Un pharmacóforo es el conjunto de rasgos estérico-electrónicos (donadores/aceptores de H,
hidrofóbicos, aromáticos, ionizables) y su disposición 3D que hace que una molécula interactúe
con su diana. Este módulo construye un pharmacóforo **ligand-based** con RDKit:

  - de UNA molécula: extrae los rasgos con sus posiciones 3D (embebido ETKDG + MMFF) y las
    distancias par a par (la geometría del pharmacóforo).
  - de VARIAS moléculas activas: perfil de CONSENSO — familias de rasgo presentes en ≥50% de los
    activos (patrón multi-ligando estándar).

Implementación PROPIA y 100% open (solo RDKit), pensada para la edición redistribuible. El enfoque
(SBP/LBP/RBP + consenso) está inspirado en el `pharmaco-suite` de Eduardo Cubillos y en la
literatura clásica de pharmacóforos (ver `references` / docs/PHARMACO_SUITE_INTEGRATION.md).

Tier 5.2 (de novo pharmaco-guiado) y 5.3 (docking) se apoyarán en esto — ver docs/TIER5_PLAN.md.
"""

import logging
import os

log = logging.getLogger(__name__)

# Roles legibles de cada familia de rasgo pharmacofórico de RDKit (BaseFeatures.fdef).
FAMILY_INFO = {
    "Donor":          {"label": "Donador de H", "role": "hbond"},
    "Acceptor":       {"label": "Aceptor de H", "role": "hbond"},
    "Aromatic":       {"label": "Anillo aromático", "role": "aromatic"},
    "Hydrophobe":     {"label": "Hidrofóbico", "role": "hydrophobic"},
    "LumpedHydrophobe": {"label": "Hidrofóbico (agrupado)", "role": "hydrophobic"},
    "PosIonizable":   {"label": "Ionizable positivo", "role": "ionic"},
    "NegIonizable":   {"label": "Ionizable negativo", "role": "ionic"},
    "ZnBinder":       {"label": "Quelante de Zn", "role": "metal"},
}

REFERENCES = [
    "Gobbi A, Poppinger D. Genetic optimization of combinatorial libraries. Biotechnol Bioeng. "
    "1998;61:47-54 (definiciones de rasgos pharmacofóricos de RDKit).",
    "Wolber G, Langer T. LigandScout: 3-D pharmacophores. J Chem Inf Model. 2005;45:160-169.",
    "Landrum G. RDKit: Open-source cheminformatics. https://www.rdkit.org",
    "Enfoque SBP/LBP/RBP + consenso inspirado en pharmaco-suite (E. Cubillos); implementación propia.",
]

try:
    from rdkit import Chem, RDConfig
    from rdkit.Chem import ChemicalFeatures, AllChem
    _FDEF = os.path.join(RDConfig.RDDataDir, "BaseFeatures.fdef")
    _FACTORY = ChemicalFeatures.BuildFeatureFactory(_FDEF)
    RDKIT_OK = True
except Exception:  # RDKit ausente o fdef no encontrado
    RDKIT_OK = False
    log.info("RDKit/feature-factory no disponible — pharmacóforos deshabilitados.")


def _embed(smiles: str):
    """Devuelve un mol con conformer 3D (o None si el SMILES es inválido/no embebible)."""
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return None
    m = Chem.AddHs(m)
    if AllChem.EmbedMolecule(m, randomSeed=42) != 0:
        return None
    try:
        AllChem.MMFFOptimizeMolecule(m)
    except Exception:
        pass
    return m


def _features_3d(smiles: str) -> list[dict] | None:
    """Rasgos pharmacofóricos con posición 3D de una molécula."""
    m = _embed(smiles)
    if m is None:
        return None
    out = []
    for f in _FACTORY.GetFeaturesForMol(m):
        fam = f.GetFamily()
        p = f.GetPos()
        out.append({"family": fam, "label": FAMILY_INFO.get(fam, {}).get("label", fam),
                    "role": FAMILY_INFO.get(fam, {}).get("role", "other"),
                    "x": round(p.x, 3), "y": round(p.y, 3), "z": round(p.z, 3)})
    return out


def _pairwise_distances(feats: list[dict], top: int = 25) -> list[dict]:
    """Distancias par a par entre rasgos (Å), las `top` más cortas."""
    import itertools
    import math
    pairs = []
    for i, j in itertools.combinations(range(len(feats)), 2):
        a, b = feats[i], feats[j]
        d = math.sqrt((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + (a["z"] - b["z"]) ** 2)
        pairs.append({"a": i, "b": j, "family_a": a["family"], "family_b": b["family"],
                      "distance": round(d, 2)})
    pairs.sort(key=lambda p: p["distance"])
    return pairs[:top]


def _counts(feats: list[dict]) -> dict:
    c: dict = {}
    for f in feats:
        c[f["family"]] = c.get(f["family"], 0) + 1
    return c


def build(smiles_list: list[str], min_fraction: float = 0.5) -> dict:
    """
    Construye un pharmacóforo ligand-based.
      - 1 SMILES → rasgos 3D + distancias par a par (geometría).
      - ≥2 SMILES → perfil de consenso (familias en ≥min_fraction de los activos).
    Degrada con available=False si RDKit falta o ningún SMILES es válido.
    """
    if not RDKIT_OK:
        return {"available": False, "reason": "RDKit no disponible."}
    smiles_list = [s for s in (smiles_list or []) if s and s.strip()]
    if not smiles_list:
        return {"available": False, "reason": "Se requiere al menos un SMILES."}

    if len(smiles_list) == 1:
        feats = _features_3d(smiles_list[0])
        if feats is None:
            return {"available": False, "reason": "SMILES inválido o no embebible en 3D."}
        return {
            "available": True, "mode": "single", "n_molecules": 1,
            "features": feats, "feature_counts": _counts(feats),
            "distances": _pairwise_distances(feats),
            "references": REFERENCES,
            "note": "Pharmacóforo 3D in silico (conformer ETKDG+MMFF); modelo de hipótesis.",
        }

    # multi-ligando: consenso por familia de rasgo
    per_mol_families, n_valid = [], 0
    for smi in smiles_list:
        feats = _features_3d(smi)
        if feats is None:
            continue
        n_valid += 1
        per_mol_families.append(set(f["family"] for f in feats))
    if n_valid == 0:
        return {"available": False, "reason": "Ningún SMILES válido/embebible."}

    fam_present: dict = {}
    for fams in per_mol_families:
        for fam in fams:
            fam_present[fam] = fam_present.get(fam, 0) + 1
    consensus = []
    for fam, cnt in sorted(fam_present.items(), key=lambda x: -x[1]):
        frac = cnt / n_valid
        if frac >= min_fraction:
            consensus.append({"family": fam, "label": FAMILY_INFO.get(fam, {}).get("label", fam),
                              "role": FAMILY_INFO.get(fam, {}).get("role", "other"),
                              "present_in": cnt, "fraction": round(frac, 3)})
    return {
        "available": True, "mode": "multi-ligand consensus", "n_molecules": n_valid,
        "min_fraction": min_fraction, "consensus_features": consensus,
        "references": REFERENCES,
        "note": "Perfil de consenso: familias de rasgo presentes en ≥%.0f%% de los activos."
                % (min_fraction * 100),
    }


def pharmacophore_for_drug(drug_id: str) -> dict:
    """Pharmacóforo de un fármaco del catálogo (por DrugBank/open ID)."""
    try:
        from config.services.mongo import get_db
        from config.services.chemberta_index import _smiles_for
        smi = _smiles_for(get_db(), (drug_id or "").strip().upper())
    except Exception as exc:
        log.debug("pharmacophore_for_drug resolve error: %s", exc)
        smi = ""
    if not smi:
        return {"available": False, "reason": f"Sin SMILES para '{drug_id}'."}
    res = build([smi])
    res["drug_id"] = drug_id
    res["seed_smiles"] = smi
    return res
