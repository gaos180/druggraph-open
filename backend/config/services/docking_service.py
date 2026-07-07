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


_BACKEND_DIR = os.path.dirname(os.path.dirname(RECEPTOR_DIR))  # backend/


def ensure_receptor(uniprot: str, name: str = "") -> str:
    """
    Garantiza un receptor preparado para una diana por UniProt: si no existe, lo prepara desde
    **AlphaFold** (caja ciega en el centroide) llamando a scripts/prepare_receptor.py **por
    subprocess** — obligatorio, porque OpenBabel co-cargado con vina/meeko en el mismo proceso
    segfaultea. Permite acoplar contra dianas ELEGIDAS (p. ej. las predichas), no solo curadas.

    Ojo: caja ciega (sin bolsillo validado) → docking EXPLORATORIO, menor confianza que un receptor
    curado (como NDM-1).
    """
    import subprocess
    import sys
    uniprot = (uniprot or "").strip().upper()
    if not uniprot:
        raise DockingUnavailable("Falta UniProt para preparar el receptor.")
    tdir = os.path.join(RECEPTOR_DIR, uniprot)
    if os.path.exists(os.path.join(tdir, "receptor.pdbqt")) and os.path.exists(os.path.join(tdir, "box.json")):
        return uniprot

    cmd = [sys.executable, "-m", "scripts.prepare_receptor",
           "--uniprot", uniprot, "--target", uniprot, "--name", name or uniprot]
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings"}
    proc = subprocess.run(cmd, cwd=_BACKEND_DIR, env=env, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0 or not os.path.exists(os.path.join(tdir, "box.json")):
        raise DockingUnavailable(
            f"No se pudo preparar el receptor {uniprot}: {(proc.stderr or proc.stdout)[-300:]}")
    return uniprot


def _protonate(smiles: str, ph: float) -> str:
    """Ajusta el estado de protonación del SMILES al pH dado (dimorphite-dl, solo RDKit)."""
    try:
        from dimorphite_dl import protonate_smiles
        out = protonate_smiles(smiles, ph_min=ph, ph_max=ph, precision=1.0)
        if out and Chem.MolFromSmiles(out[0]):
            return out[0]
    except Exception as exc:
        log.debug("protonación pH %s falló: %s", ph, exc)
    return smiles


def prepare_ligand_pdbqt(smiles: str, ph: float | None = None) -> str:
    """SMILES → PDBQT (embebido 3D + Meeko). Con `ph`, ajusta la protonación al pH. ValueError si inválido."""
    if ph is not None:
        smiles = _protonate(smiles, ph)
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


def dock(smiles: str, target: str, exhaustiveness: int = 8, n_poses: int = 5,
         ph: float | None = None) -> dict:
    """
    Acopla un ligando (SMILES) al receptor `target` preparado. Con `ph`, ajusta la protonación del
    ligando a ese pH antes de acoplar (permite reintentar a distinto pH). Devuelve afinidad top +
    poses. Degrada con available=False si faltan deps o el receptor.
    """
    if not DOCKING_OK:
        return {"available": False,
                "reason": "Docking no disponible: instala vina + meeko + openbabel (requirements-ml.txt)."}
    try:
        rec_path, box = _receptor_paths(target)
    except DockingUnavailable as exc:
        return {"available": False, "reason": str(exc)}

    try:
        lig_pdbqt = prepare_ligand_pdbqt(smiles, ph=ph)
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
        "ph": ph,
        "affinity_kcal_mol": poses[0] if poses else None,
        "poses_kcal_mol": poses,
        "box": {"center": box["center"], "box_size": box["box_size"]},
        "source": box.get("source", "curated"),
        "blind": bool(box.get("blind", False)),
        "note": ("Docking CIEGO a estructura AlphaFold (sitio no validado) — exploratorio, baja "
                 "confianza." if box.get("blind") else
                 "Afinidad de docking rígido in silico (kcal/mol, más negativo = mejor); hipótesis, "
                 "no medida experimental. Protocolo validado con EF/ROC vs. decoys."),
    }


def dock_many(smiles_list, target: str, exhaustiveness: int = 8, on_progress=None) -> dict:
    """
    Acopla muchos ligandos a `target` calculando los mapas de Vina UNA sola vez (mucho más
    rápido que dock() por ligando). Devuelve {smiles: afinidad|None}. Usado por el cribado
    batch (run_docking_screen) y la validación (eval_docking).
    """
    if not DOCKING_OK:
        raise DockingUnavailable("vina/meeko/openbabel no disponibles.")
    from vina import Vina
    rec_path, box = _receptor_paths(target)
    v = Vina(sf_name="vina", verbosity=0)
    v.set_receptor(rec_path)
    v.compute_vina_maps(center=box["center"], box_size=box["box_size"])
    res: dict = {}
    for i, smi in enumerate(smiles_list):
        try:
            v.set_ligand_from_string(prepare_ligand_pdbqt(smi))
            v.dock(exhaustiveness=exhaustiveness, n_poses=1)
            res[smi] = round(float(v.energies(n_poses=1)[0][0]), 2)
        except Exception as exc:
            log.debug("dock_many skip (%s): %s", smi[:30], exc)
            res[smi] = None
        if on_progress and (i + 1) % 20 == 0:
            on_progress(i + 1, len(smiles_list))
    return res


def screen_results(target: str, limit: int = 50) -> list[dict]:
    """Lee los resultados del cribado batch (Mongo `docking_results`) rankeados por afinidad."""
    try:
        from config.services.mongo import get_db
        rows = list(get_db().docking_results.find({"target": target})
                    .sort("affinity_kcal_mol", 1).limit(max(1, min(limit, 500))))
    except Exception as exc:
        log.debug("screen_results error: %s", exc)
        return []
    return [{"drug_id": r.get("drug_id"), "name": r.get("name", ""),
             "affinity_kcal_mol": r.get("affinity_kcal_mol"), "smiles": r.get("smiles", "")}
            for r in rows]


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
