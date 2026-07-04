"""
_chemistry.py — Fingerprints moleculares y propiedades fisicoquímicas (RDKit).

RDKit es opcional en tiempo de import: si no está disponible, las funciones de
fingerprint devuelven None y el endpoint responde con un error claro en vez de
tumbar el proceso Django completo.
"""

import logging

log = logging.getLogger(__name__)

# ── Configuración del fingerprint ──────────────────────────────────────────────
FP_RADIUS = 2        # Morgan/ECFP4 (radio 2)
FP_NBITS  = 2048

try:
    from rdkit import Chem
    from rdkit.Chem import DataStructs, Descriptors, MACCSkeys, rdFingerprintGenerator
    from rdkit.Chem.Pharm2D import Generate, Gobbi_Pharm2D
    RDKIT_OK = True
    # Generadores reutilizables (API moderna). El generador Morgan con radio 2 y
    # 2048 bits produce exactamente los mismos bits que el antiguo
    # GetMorganFingerprintAsBitVect, así que los fingerprints ya almacenados en
    # Neo4j siguen siendo compatibles sin repoblar.
    _MORGAN_GEN   = rdFingerprintGenerator.GetMorganGenerator(radius=FP_RADIUS, fpSize=FP_NBITS)
    _ATOMPAIR_GEN = rdFingerprintGenerator.GetAtomPairGenerator()
except ImportError:
    RDKIT_OK = False
    log.warning("RDKit no disponible — la similitud estructural quedará deshabilitada.")


def validate_smiles(smiles: str) -> dict | None:
    """
    Valida un SMILES y devuelve propiedades fisicoquímicas básicas.
    Retorna None si el SMILES es inválido o RDKit no está disponible.
    """
    if not RDKIT_OK or not smiles:
        return None

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None

    return {
        "canonical_smiles":  Chem.MolToSmiles(mol),
        "molecular_weight":  round(Descriptors.MolWt(mol), 3),
        "logp":              round(Descriptors.MolLogP(mol), 3),
        "h_bond_donors":     Descriptors.NumHDonors(mol),
        "h_bond_acceptors":  Descriptors.NumHAcceptors(mol),
        "tpsa":              round(Descriptors.TPSA(mol), 3),
        "rotatable_bonds":   Descriptors.NumRotatableBonds(mol),
        "aromatic_rings":    Descriptors.NumAromaticRings(mol),
        "num_heavy_atoms":   mol.GetNumHeavyAtoms(),
    }


def compute_fingerprint(smiles: str) -> str | None:
    """
    Calcula un fingerprint Morgan (ECFP4) y lo retorna como string compacto,
    listo para guardar en Neo4j como propiedad de nodo.
    """
    if not RDKIT_OK or not smiles:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    fp = _MORGAN_GEN.GetFingerprint(mol)
    return DataStructs.BitVectToFPSText(fp)


def fingerprint_from_text(fp_str: str):
    """Reconstruye un ExplicitBitVect desde el string generado por compute_fingerprint."""
    if not RDKIT_OK or not fp_str:
        return None
    return DataStructs.CreateFromFPSText(fp_str)


def tanimoto_similarity(fp_a_str: str, fp_b_str: str) -> float:
    """Similitud de Tanimoto entre dos fingerprints en formato string FPS."""
    if not RDKIT_OK or not fp_a_str or not fp_b_str:
        return 0.0
    fp_a = fingerprint_from_text(fp_a_str)
    fp_b = fingerprint_from_text(fp_b_str)
    if fp_a is None or fp_b is None:
        return 0.0
    return DataStructs.TanimotoSimilarity(fp_a, fp_b)


# ── Similitud de consenso multi-fingerprint (Tier 1.2) ──────────────────────────
# Combina fingerprints complementarios: Morgan (subestructura), MACCS (claves
# estructurales), atom-pair (topología) y farmacóforo 2D (patrón de interacción).
# Un consenso robustece frente a los sesgos de cada representación individual.

_FP_BUILDERS = {
    "morgan":       lambda m: _MORGAN_GEN.GetFingerprint(m),
    "maccs":        lambda m: MACCSkeys.GenMACCSKeys(m),
    "atompair":     lambda m: _ATOMPAIR_GEN.GetFingerprint(m),
    "pharmacophore": lambda m: Generate.Gen2DFingerprint(m, Gobbi_Pharm2D.factory),
}


def named_similarities(smiles_a: str, smiles_b: str) -> dict:
    """
    Calcula Tanimoto por cada fingerprint y su consenso (media) entre dos SMILES.

    Retorna:
        { "per_fingerprint": {morgan, maccs, atompair, pharmacophore},
          "consensus_score": float,
          "available": bool }
    Cada score es float en [0,1]; si un fingerprint falla, su entrada es None y
    se excluye del consenso.
    """
    if not RDKIT_OK or not smiles_a or not smiles_b:
        return {"per_fingerprint": {}, "consensus_score": 0.0, "available": False}

    mol_a = Chem.MolFromSmiles(smiles_a)
    mol_b = Chem.MolFromSmiles(smiles_b)
    if mol_a is None or mol_b is None:
        return {"per_fingerprint": {}, "consensus_score": 0.0, "available": False}

    per_fp: dict = {}
    for name, build in _FP_BUILDERS.items():
        try:
            score = DataStructs.TanimotoSimilarity(build(mol_a), build(mol_b))
            per_fp[name] = round(float(score), 4)
        except Exception as exc:
            log.warning("Fingerprint %s falló: %s", name, exc)
            per_fp[name] = None

    valid = [v for v in per_fp.values() if v is not None]
    consensus = round(sum(valid) / len(valid), 4) if valid else 0.0
    return {"per_fingerprint": per_fp, "consensus_score": consensus, "available": True}
