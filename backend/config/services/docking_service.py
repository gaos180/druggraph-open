"""
docking_service.py — Cribado estructural por docking con AutoDock Vina (Tier 5.3).

Modalidad structure-based: dada una DIANA (receptor proteico preparado) y un LIGANDO (fármaco del
catálogo o SMILES), estima la afinidad de unión (kcal/mol) por docking molecular. Completa el
pipeline del Tier 5: pharmacóforo (5.1) → de novo pharmaco-guiado (5.2) → docking (5.3).

Pipeline (todo open):
  - Ligando: RDKit (embebido 3D ETKDG+MMFF) → PDBQT con **Meeko**.
  - Receptor: preparado offline (scripts/prepare_receptor.py) con **OpenBabel** → PDBQT rígido + caja.
  - Docking: **AutoDock Vina** (bindings python) sobre la caja del sitio activo.

Los receptores preparados viven en backend/models/docking/<target>/ (receptor.pdbqt + box.json).
Requiere `vina`+`meeko`+`openbabel`+RDKit. Degrada con DockingUnavailable (→503) si falta algo o el
receptor no está preparado. Vina: Trott & Olson 2010; Eberhardt 2021.
"""

import json
import logging
import os

log = logging.getLogger(__name__)

RECEPTOR_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "models", "docking",
)


class DockingUnavailable(RuntimeError):
    """Vina/Meeko/OpenBabel no disponibles o receptor no preparado."""
    pass


try:
    from vina import Vina  # noqa: F401
    from meeko import MoleculePreparation, PDBQTWriterLegacy  # noqa: F401
    from rdkit import Chem  # noqa: F401
    from rdkit.Chem import AllChem  # noqa: F401
    DOCKING_OK = True
except Exception:
    DOCKING_OK = False
    log.info("vina/meeko/rdkit no disponibles — docking (Tier 5.3) deshabilitado.")


def list_targets() -> list[dict]:
    """Receptores preparados disponibles (leyendo los box.json de models/docking/)."""
    out = []
    if not os.path.isdir(RECEPTOR_DIR):
        return out
    for name in sorted(os.listdir(RECEPTOR_DIR)):
        box = os.path.join(RECEPTOR_DIR, name, "box.json")
        rec = os.path.join(RECEPTOR_DIR, name, "receptor.pdbqt")
        if os.path.exists(box) and os.path.exists(rec):
            try:
                meta = json.load(open(box))
            except Exception:
                meta = {}
            out.append({"target": name, "name": meta.get("name", name),
                        "pdb_id": meta.get("pdb_id", ""), "center": meta.get("center"),
                        "box_size": meta.get("box_size")})
    return out


def _receptor_paths(target: str) -> tuple[str, dict]:
    d = os.path.join(RECEPTOR_DIR, target)
    rec = os.path.join(d, "receptor.pdbqt")
    box = os.path.join(d, "box.json")
    if not (os.path.exists(rec) and os.path.exists(box)):
        raise DockingUnavailable(
            f"Receptor '{target}' no preparado (ver scripts/prepare_receptor.py).")
    return rec, json.load(open(box))


def prepare_ligand_pdbqt(smiles: str) -> str:
    """SMILES → PDBQT (embebido 3D + Meeko). Lanza ValueError si el SMILES es inválido."""
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        raise ValueError("SMILES inválido.")
    m = Chem.AddHs(m)
    if AllChem.EmbedMolecule(m, randomSeed=42) != 0:
        raise ValueError("No se pudo generar conformer 3D.")
    try:
        AllChem.MMFFOptimizeMolecule(m)
    except Exception:
        pass
    pdbqt, ok, err = PDBQTWriterLegacy.write_string(MoleculePreparation().prepare(m)[0])
    if not pdbqt:
        raise ValueError(f"Meeko no pudo escribir PDBQT: {err}")
    return pdbqt


def dock(smiles: str, target: str, exhaustiveness: int = 8, n_poses: int = 5) -> dict:
    """
    Acopla un ligando (SMILES) al receptor `target` preparado. Devuelve la afinidad top
    (kcal/mol) y las poses. Degrada con available=False si faltan deps o el receptor.
    """
    if not DOCKING_OK:
        return {"available": False,
                "reason": "Docking no disponible: instala vina + meeko + openbabel (requirements-ml.txt)."}
    try:
        rec_path, box = _receptor_paths(target)
    except DockingUnavailable as exc:
        return {"available": False, "reason": str(exc)}

    try:
        lig_pdbqt = prepare_ligand_pdbqt(smiles)
    except ValueError as exc:
        return {"available": False, "reason": str(exc)}

    try:
        v = Vina(sf_name="vina", verbosity=0)
        v.set_receptor(rec_path)
        v.set_ligand_from_string(lig_pdbqt)
        v.compute_vina_maps(center=box["center"], box_size=box["box_size"])
        v.dock(exhaustiveness=exhaustiveness, n_poses=n_poses)
        energies = v.energies(n_poses=n_poses)
    except Exception as exc:
        log.error("Vina dock error: %s", exc)
        return {"available": False, "reason": f"Error en el docking: {exc}"}

    poses = [round(float(row[0]), 2) for row in energies]
    return {
        "available": True,
        "engine": "autodock-vina",
        "target": target,
        "target_name": box.get("name", target),
        "pdb_id": box.get("pdb_id", ""),
        "smiles": Chem.MolToSmiles(Chem.MolFromSmiles(smiles)),
        "affinity_kcal_mol": poses[0] if poses else None,
        "poses_kcal_mol": poses,
        "box": {"center": box["center"], "box_size": box["box_size"]},
        "note": "Afinidad de docking rígido in silico (kcal/mol, más negativo = mejor); "
                "hipótesis, no medida experimental. Validar el protocolo con EF/ROC vs. decoys.",
    }


def dock_for_drug(drug_id: str, target: str, **kw) -> dict:
    """Acopla un fármaco del catálogo (por ID) al receptor `target`."""
    try:
        from config.services.mongo import get_db
        from config.services.chemberta_index import _smiles_for
        smi = _smiles_for(get_db(), (drug_id or "").strip().upper())
    except Exception as exc:
        log.debug("dock_for_drug resolve error: %s", exc)
        smi = ""
    if not smi:
        return {"available": False, "reason": f"Sin SMILES para '{drug_id}'."}
    res = dock(smi, target, **kw)
    res["drug_id"] = drug_id
    return res
