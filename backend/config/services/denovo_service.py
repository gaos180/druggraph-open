"""
denovo_service.py — Diseño molecular de novo (Tier 4.4).

Genera moléculas candidatas nuevas a partir de un fármaco/seed y las filtra y rankea
por propiedades drug-like. Se presenta SIEMPRE como generación de HIPÓTESIS in silico
(sin validación experimental), con respaldo de paper del motor usado.

Motores:
  - CReM (Polishchuk, J. Cheminformatics 2020) — POR DEFECTO. Fragment-based, sin GPU ni
    entrenamiento; produce estructuras químicamente válidas y sintetizables por diseño.
    Deps: `pip install crem` + una base de fragmentos SQLite (env CREM_DB_PATH).
  - REINVENT4 (Loeffler, J. Cheminformatics 2024, AstraZeneca) — opcional, ver
    denovo_reinvent.py. Motor generativo RNN. 503 si no está instalado.

Scoring común (RDKit): QED, SA score (sintetizabilidad), Lipinski, similitud al seed.
Todas las dependencias son opcionales: si faltan, los endpoints devuelven 503.
"""

import logging
import os

log = logging.getLogger(__name__)

# Base de fragmentos de CReM (SQLite). Descargable de la ChEMBL precompilada del proyecto
# o construible con `cremdb_create`. Ver scripts/build_crem_db.py.
CREM_DB_PATH = os.environ.get("CREM_DB_PATH", "")

PAPERS = {
    "crem": "Polishchuk P. CReM: chemically reasonable mutations framework for structure "
            "generation. J Cheminform. 2020;12:28. doi:10.1186/s13321-020-00431-w",
    "reinvent": "Loeffler HH, et al. REINVENT 4: Modern AI-driven generative molecule "
                "design. J Cheminform. 2024;16:20. doi:10.1186/s13321-024-00812-5",
}

try:
    from crem.crem import mutate_mol, grow_mol, link_mols
    CREM_OK = True
except ImportError:
    CREM_OK = False
    log.info("crem no instalado — motor de novo CReM deshabilitado.")

# RDKit (compartido con el sandbox); QED + SA score para el scoring.
try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, QED, RDConfig
    import sys
    _sa_dir = os.path.join(RDConfig.RDContribDir, "SA_Score")
    if _sa_dir not in sys.path:
        sys.path.append(_sa_dir)
    import sascorer  # type: ignore
    RDKIT_OK = True
except Exception:  # ImportError o fallos del contrib SA_Score
    RDKIT_OK = False
    log.info("RDKit/SA_Score no disponible — scoring de novo deshabilitado.")


def crem_db_ready() -> bool:
    """True si CReM está instalado y la base de fragmentos existe."""
    return CREM_OK and bool(CREM_DB_PATH) and os.path.exists(CREM_DB_PATH)


# ── Resolución del seed (SMILES o DrugBank ID) ──────────────────────────────────

def _resolve_seed(seed: str) -> str:
    """Devuelve un SMILES. Si `seed` parece un DrugBank ID (DBxxxxx), lo busca en Mongo."""
    seed = (seed or "").strip()
    if not seed:
        return ""
    if seed.upper().startswith("DB") and seed[2:].isdigit():
        try:
            from config.services.mongo import get_db
            from config.services.chemberta_index import _smiles_for
            return _smiles_for(get_db(), seed.upper())
        except Exception as exc:
            log.debug("_resolve_seed Mongo error: %s", exc)
            return ""
    return seed


# ── Scoring de un candidato ─────────────────────────────────────────────────────

def _score_candidate(smiles: str, seed_fp) -> dict | None:
    """Propiedades drug-like de un candidato. None si el SMILES no es válido."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    try:
        qed = round(float(QED.qed(mol)), 4)
    except Exception:
        qed = None
    try:
        sa = round(float(sascorer.calculateScore(mol)), 2)  # 1 (fácil) – 10 (difícil)
    except Exception:
        sa = None

    mw = round(Descriptors.MolWt(mol), 2)
    logp = round(Descriptors.MolLogP(mol), 2)
    hbd = Descriptors.NumHDonors(mol)
    hba = Descriptors.NumHAcceptors(mol)
    lipinski = (mw <= 500) + (logp <= 5) + (hbd <= 5) + (hba <= 10)  # nº de reglas cumplidas

    sim = None
    if seed_fp is not None:
        from rdkit import DataStructs
        from config.services.sandbox_service._chemistry import _MORGAN_GEN
        try:
            sim = round(float(DataStructs.TanimotoSimilarity(_MORGAN_GEN.GetFingerprint(mol), seed_fp)), 4)
        except Exception:
            sim = None

    return {
        "smiles": Chem.MolToSmiles(mol),
        "qed": qed,
        "sa_score": sa,
        "similarity_to_seed": sim,
        "mol_weight": mw,
        "logp": logp,
        "lipinski_rules": lipinski,
    }


# ── Generación ──────────────────────────────────────────────────────────────────

def generate(seed: str, mode: str = "mutate", engine: str = "crem",
             n: int = 20, max_replacements: int = 200) -> dict:
    """
    Genera candidatos de novo a partir de un seed (SMILES o DrugBank ID).

    Parámetros:
        mode   : 'grow' | 'mutate' | 'link' (link usa el seed consigo mismo).
        engine : 'crem' (por defecto) | 'reinvent'.
        n      : máximo de candidatos a devolver (rankeados por QED).

    Retorna:
        { available, engine, paper, seed_smiles, mode, candidates:[...], disclaimer }
    503-friendly: si el motor/deps no están, available=False + reason.
    """
    n = max(1, min(n, 100))

    if engine == "reinvent":
        from config.services import denovo_reinvent
        return denovo_reinvent.generate(seed=_resolve_seed(seed), n=n)

    # Motor CReM (por defecto)
    if not RDKIT_OK:
        return {"available": False, "reason": "RDKit no disponible."}
    if not crem_db_ready():
        return {"available": False,
                "reason": "CReM no disponible: instala `crem` y define CREM_DB_PATH "
                          "(ver scripts/build_crem_db.py)."}

    seed_smiles = _resolve_seed(seed)
    seed_mol = Chem.MolFromSmiles(seed_smiles) if seed_smiles else None
    if seed_mol is None:
        return {"available": False, "reason": "Seed inválido (SMILES o DrugBank ID no resoluble)."}

    from config.services.sandbox_service._chemistry import _MORGAN_GEN
    seed_fp = _MORGAN_GEN.GetFingerprint(seed_mol)

    try:
        if mode == "grow":
            gen = grow_mol(seed_mol, db_name=CREM_DB_PATH, max_replacements=max_replacements)
        elif mode == "link":
            gen = link_mols(seed_mol, seed_mol, db_name=CREM_DB_PATH, max_replacements=max_replacements)
        else:  # mutate (por defecto)
            gen = mutate_mol(seed_mol, db_name=CREM_DB_PATH, max_replacements=max_replacements)
        raw = list(gen)
    except Exception as exc:
        log.error("CReM generate error (%s): %s", mode, exc)
        return {"available": False, "reason": f"Error del motor CReM: {exc}"}

    # CReM puede devolver SMILES o (SMILES, mol) según versión/flags.
    smiles_list = [(r[0] if isinstance(r, (tuple, list)) else r) for r in raw]

    seed_canon = Chem.MolToSmiles(seed_mol)
    seen: set[str] = set()
    candidates: list[dict] = []
    for smi in smiles_list:
        sc = _score_candidate(smi, seed_fp)
        if sc is None or sc["smiles"] == seed_canon or sc["smiles"] in seen:
            continue
        seen.add(sc["smiles"])
        candidates.append(sc)

    # Ranking por QED (calidad drug-like) desc; los None al final.
    candidates.sort(key=lambda c: (c["qed"] is None, -(c["qed"] or 0)))
    candidates = candidates[:n]

    return {
        "available": True,
        "engine": "crem",
        "paper": PAPERS["crem"],
        "seed_smiles": seed_canon,
        "mode": mode,
        "generated": len(smiles_list),
        "candidates": candidates,
        "disclaimer": "Moléculas generadas in silico (hipótesis). No han sido sintetizadas "
                      "ni validadas experimentalmente.",
    }
