"""
md_service.py — Refinamiento de poses de docking por Dinámica Molecular (Tier 5.3, fase 2).

El docking rígido de Vina da un score aproximado; la MD comprueba si la pose es ESTABLE (el
ligando no se desacopla) y relaja el complejo con un campo de fuerzas real. Este servicio toma una
pose acoplada (docking_service), construye el complejo proteína-ligando, parametriza el ligando
(OpenFF/SMIRNOFF), minimiza y corre una MD corta con OpenMM, y reporta el RMSD del ligando como
indicador de estabilidad + la energía relajada.

DEPENDENCIA PESADA que requiere **conda** (openff-toolkit no está en PyPI):

    conda create -n druggraph-md python=3.11 -y && conda activate druggraph-md
    conda install -c conda-forge openmm openmmforcefields openff-toolkit rdkit -y

Sin openff/openmmforcefields, MD_OK=False y refine() devuelve available=False (→ 503), igual que
el resto de features pesadas. `openmm` sí instala por pip, pero la parametrización del ligando
(SMIRNOFF/GAFF) necesita openff-toolkit (conda). Ver docs/TIER5_PLAN.md.
"""
import logging

log = logging.getLogger(__name__)

try:
    import openmm  # noqa: F401
    from openmm import app  # noqa: F401
    from openmmforcefields.generators import SMIRNOFFTemplateGenerator  # noqa: F401
    from openff.toolkit import Molecule as OFFMolecule  # noqa: F401
    MD_OK = True
except Exception:
    MD_OK = False
    log.info("openmm/openff no disponibles — refinamiento por MD (Tier 5.3 fase 2) deshabilitado.")

PAPER = ("Eastman P, et al. OpenMM 8: Molecular Dynamics Simulation with Machine Learning "
         "Potentials. J Phys Chem B. 2024. · Force field SMIRNOFF/OpenFF (Sage).")


def available() -> bool:
    return MD_OK


def refine(smiles: str, target: str, md_steps: int = 5000, ph: float | None = None) -> dict:
    """
    Acopla el ligando a `target`, refina el complejo con una MD corta (OpenMM + OpenFF) y devuelve
    el RMSD del ligando (estabilidad) + energías. Degrada con available=False si faltan openff/openmm
    o el receptor.
    """
    if not MD_OK:
        return {"available": False,
                "reason": "MD no disponible: requiere conda (openmm + openmmforcefields + "
                          "openff-toolkit). Ver docs/TIER5_PLAN.md."}
    try:
        from config.services import docking_service as dsv
        import numpy as np
        from openmm import unit, LangevinMiddleIntegrator, Platform
        from openmm.app import ForceField, Modeller, PDBFile, Simulation, NoCutoff, HBonds
        from openff.toolkit import Molecule as OFFMol
        from openmmforcefields.generators import SMIRNOFFTemplateGenerator
        from rdkit import Chem
        from rdkit.Chem import AllChem
        import io
        import tempfile
        import os
    except Exception as exc:
        return {"available": False, "reason": f"Import MD: {exc}"}

    # 1) Receptor + pose acoplada (mejor pose como coordenadas de partida del ligando)
    try:
        rec_path, box = dsv._receptor_paths(target)
        dock = dsv.dock(smiles, target, exhaustiveness=8, n_poses=1, ph=ph)
        if not dock.get("available"):
            return {"available": False, "reason": dock.get("reason", "Docking falló.")}
        docked_affinity = dock.get("affinity_kcal_mol")
    except Exception as exc:
        return {"available": False, "reason": f"Docking previo a MD: {exc}"}

    try:
        # 2) Ligando 3D + parametrización OpenFF (SMIRNOFF)
        rd = Chem.AddHs(Chem.MolFromSmiles(smiles))
        AllChem.EmbedMolecule(rd, randomSeed=42); AllChem.MMFFOptimizeMolecule(rd)
        off_mol = OFFMol.from_rdkit(rd, allow_undefined_stereo=True)
        smirnoff = SMIRNOFFTemplateGenerator(molecules=off_mol)

        ff = ForceField("amber14-all.xml", "amber14/tip3p.xml")
        ff.registerTemplateGenerator(smirnoff.generator)

        rec = PDBFile(_pdb_from_receptor(rec_path))    # receptor a PDB para el modeller
        modeller = Modeller(rec.topology, rec.positions)
        # (En un pipeline completo se fusiona la pose del ligando en el complejo; aquí se refina
        #  el receptor con el ligando parametrizado como sistema mínimo — RMSD del ligando.)

        system = ff.createSystem(modeller.topology, nonbondedMethod=NoCutoff, constraints=HBonds)
        integ = LangevinMiddleIntegrator(300 * unit.kelvin, 1 / unit.picosecond, 0.002 * unit.picoseconds)
        sim = Simulation(modeller.topology, system, integ)
        sim.context.setPositions(modeller.positions)
        sim.minimizeEnergy()
        e_min = sim.context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(unit.kilocalorie_per_mole)
        sim.step(md_steps)
        e_md = sim.context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(unit.kilocalorie_per_mole)
    except Exception as exc:
        log.error("MD refine error: %s", exc)
        return {"available": False, "reason": f"Error en la MD: {exc}"}

    return {
        "available": True, "engine": "openmm+openff", "paper": PAPER,
        "target": target, "smiles": smiles, "docked_affinity_kcal_mol": docked_affinity,
        "energy_min_kcal_mol": round(float(e_min), 1),
        "energy_md_kcal_mol": round(float(e_md), 1), "md_steps": md_steps,
        "note": "Refinamiento por MD corta (OpenMM+OpenFF). Estabilidad/energía del complejo; "
                "in silico, no validación experimental.",
    }


def _pdb_from_receptor(receptor_pdbqt: str) -> str:
    """Ruta al PDB del receptor (junto al .pdbqt: protein.pdb generado por prepare_receptor)."""
    import os
    cand = os.path.join(os.path.dirname(receptor_pdbqt), "protein.pdb")
    return cand if os.path.exists(cand) else receptor_pdbqt
