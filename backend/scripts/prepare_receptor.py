#!/usr/bin/env python3
"""
prepare_receptor.py — Prepara un receptor para docking con Vina (Tier 5.3).

Descarga (o toma local) una estructura PDB, elimina aguas, prepara el receptor rígido en PDBQT
con **OpenBabel** y define la CAJA de búsqueda alrededor del sitio activo (centroide de un ligando
co-cristalizado, de un metal, o coordenadas explícitas). Guarda receptor.pdbqt + box.json en
backend/models/docking/<target>/, listos para docking_service.dock().

USO (desde backend/, con el venv activo):
    # NDM-1 (metalo-β-lactamasa): caja centrada en los Zn de la cadena A
    python -m scripts.prepare_receptor --pdb-id 3SPU --target ndm1 --center-metal Zn --chain A

    # Caja centrada en un ligando co-cristalizado (código HETATM)
    python -m scripts.prepare_receptor --pdb-id 1HXW --target hivpr --center-ligand RIT --chain A

    # Coordenadas explícitas
    python -m scripts.prepare_receptor --pdb-file mi_prot.pdb --target x --center 12 4 15

Deps: openbabel (openbabel-wheel), gemmi, requests.
"""
import argparse
import json
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("prepare_receptor")

RECEPTOR_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "docking")


def _fetch_pdb(pdb_id: str, dest: str) -> str:
    import requests
    url = f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb"
    log.info("Descargando %s…", url)
    r = requests.get(url, timeout=120); r.raise_for_status()
    with open(dest, "w") as fh:
        fh.write(r.text)
    return dest


def _fetch_alphafold(uniprot: str, dest: str) -> str:
    """Descarga la estructura AlphaFold de un UniProt (vía API, robusta ante versiones)."""
    import requests
    meta = requests.get(f"https://alphafold.ebi.ac.uk/api/prediction/{uniprot.upper()}", timeout=60).json()
    if not meta:
        raise SystemExit(f"Sin estructura AlphaFold para {uniprot}.")
    log.info("Descargando AlphaFold %s…", meta[0]["pdbUrl"])
    r = requests.get(meta[0]["pdbUrl"], timeout=120); r.raise_for_status()
    with open(dest, "w") as fh:
        fh.write(r.text)
    return dest


def _centroid(pdb_in: str) -> list[float]:
    import gemmi
    import numpy as np
    st = gemmi.read_structure(pdb_in)
    pts = np.array([(a.pos.x, a.pos.y, a.pos.z) for m in st for ch in m for r in ch for a in r])
    c = pts.mean(0)
    return [round(float(c[0]), 2), round(float(c[1]), 2), round(float(c[2]), 2)]


def _protein_only(pdb_in: str, pdb_out: str, keep_metal: str | None):
    """Escribe solo ATOM (proteína) + opcionalmente el metal HETATM; descarta aguas/otros."""
    metal = (keep_metal or "").upper()
    with open(pdb_in) as fi, open(pdb_out, "w") as fo:
        for line in fi:
            if line.startswith("ATOM"):
                fo.write(line)
            elif line.startswith("HETATM") and metal and line[76:78].strip().upper() == metal:
                fo.write(line)


def _box_center(pdb_in: str, args) -> list[float]:
    import gemmi
    import numpy as np
    if args.center:
        return [float(v) for v in args.center]
    st = gemmi.read_structure(pdb_in)
    pts = []
    for model in st:
        for chain in model:
            if args.chain and chain.name != args.chain:
                continue
            for res in chain:
                is_lig = args.center_ligand and res.name == args.center_ligand.upper()
                for atom in res:
                    is_metal = args.center_metal and atom.element.name.upper() == args.center_metal.upper()
                    if is_lig or is_metal:
                        pts.append((atom.pos.x, atom.pos.y, atom.pos.z))
        break
    if not pts:
        raise SystemExit("No se encontró el ligando/metal para centrar la caja "
                         "(usa --center x y z explícito).")
    c = np.mean(pts, axis=0)
    return [round(float(c[0]), 2), round(float(c[1]), 2), round(float(c[2]), 2)]


def _receptor_pdbqt(protein_pdb: str, out_pdbqt: str):
    from openbabel import pybel
    mol = next(pybel.readfile("pdb", protein_pdb))
    mol.write("pdbqt", out_pdbqt, overwrite=True, opt={"r": None, "x": None})  # rígido


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdb-id"); ap.add_argument("--pdb-file")
    ap.add_argument("--uniprot", help="prepara desde AlphaFold por UniProt (caja ciega en el centroide)")
    ap.add_argument("--name", default="", help="nombre legible del receptor")
    ap.add_argument("--target", required=True, help="nombre corto del receptor (carpeta)")
    ap.add_argument("--center", nargs=3, help="coordenadas x y z de la caja")
    ap.add_argument("--center-ligand", help="código HETATM del ligando co-cristalizado")
    ap.add_argument("--center-metal", help="elemento del metal del sitio activo (p.ej. Zn)")
    ap.add_argument("--chain", help="restringe a una cadena para centrar la caja")
    ap.add_argument("--box-size", type=float, default=22.0)
    args = ap.parse_args()

    out_dir = os.path.join(RECEPTOR_DIR, args.target)
    os.makedirs(out_dir, exist_ok=True)

    blind = False
    if args.uniprot:
        raw = _fetch_alphafold(args.uniprot, os.path.join(out_dir, "structure.pdb"))
        center = [float(v) for v in args.center] if args.center else _centroid(raw)
        blind = not args.center           # sin sitio validado → docking ciego
    else:
        raw = args.pdb_file or _fetch_pdb(args.pdb_id, os.path.join(out_dir, "structure.pdb"))
        center = _box_center(raw, args)

    protein_pdb = os.path.join(out_dir, "protein.pdb")
    _protein_only(raw, protein_pdb, args.center_metal)
    _receptor_pdbqt(protein_pdb, os.path.join(out_dir, "receptor.pdbqt"))

    box = {"name": args.name or args.target, "pdb_id": (args.pdb_id or "").upper(),
           "uniprot": (args.uniprot or "").upper(), "center": center,
           "box_size": [args.box_size] * 3, "chain": args.chain,
           "source": "alphafold" if args.uniprot else "pdb", "blind": blind}
    with open(os.path.join(out_dir, "box.json"), "w") as fh:
        json.dump(box, fh, indent=2)
    log.info("Receptor '%s' listo: centro %s, caja %s, blind=%s → %s",
             args.target, center, box["box_size"], blind, out_dir)


if __name__ == "__main__":
    main()
