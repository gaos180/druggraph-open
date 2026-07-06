#!/usr/bin/env python3
"""
build_synthemol_space.py — Prepara el espacio químico y el predictor para SyntheMol (Tier 4.4c).

SyntheMol (Swanson K, et al. Nat Mach Intell 2024; https://github.com/swansonk14/SyntheMol)
genera moléculas de novo con síntesis garantizada recorriendo un espacio combinatorio de
bloques comprables + reacciones reales, guiado por un predictor de bioactividad. Necesita:

  1) `pip install synthemol` (trae chemprop, chemfunc, RDKit, torch).
  2) BIBLIOTECA DE BLOQUES (CSV con columnas `smiles`, `reagent_id`). Descárgala del repo de
     SyntheMol / Enamine REAL Space (137 656 bloques, 70 reacciones) o WuXi GalaXi:
        https://github.com/swansonk14/SyntheMol  (sección "Data")
     Luego:  export SYNTHEMOL_BUILDING_BLOCKS=/ruta/building_blocks.csv
  3) PREDICTOR entrenado que guía la búsqueda hacia la propiedad objetivo. Este script EXPORTA
     un CSV de entrenamiento (`smiles,activity`) desde el catálogo de DrugGraph usando una
     etiqueta binaria a tu elección, y te imprime los comandos de Chemprop/SyntheMol para
     entrenarlo. Luego:  export SYNTHEMOL_SCORE_MODEL=/ruta/models/chemprop
                         export SYNTHEMOL_SCORE_TYPE=chemprop

USO (desde backend/, con el venv activo):
    python -m scripts.build_synthemol_space --label chembl_moa --out /tmp/synthemol_train.csv

Etiquetas soportadas (`--label`):
    chembl_moa   : 1 si el fármaco tiene mecanismo de acción de ChEMBL (proxy de "bioactivo
                   caracterizado"), 0 en caso contrario. Es un EJEMPLO de andamiaje: cámbialo
                   por tu endpoint real (p. ej. actividad antibacteriana como en el paper).

Tras entrenar el predictor y descargar los bloques, define las 3 env vars antes de arrancar el
backend y el motor `synthemol` quedará disponible en POST /api/tools/denovo/.
"""

import argparse
import csv
import logging
import os

import django

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("synthemol_space")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()


def export_training_csv(out_path: str, label: str) -> tuple[int, int]:
    """
    Escribe un CSV `smiles,activity` desde Mongo `drugs`. Devuelve (n_filas, n_positivos).
    La etiqueta es un EJEMPLO — sustitúyela por tu objetivo real de bioactividad.
    """
    from config.services.mongo import get_db

    db = get_db()
    proj = {"calculated-properties": 1, "chembl": 1, "mechanism_of_action": 1, "drugbank-id": 1}
    n = pos = 0
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["smiles", "activity"])
        for doc in db.drugs.find({}, proj):
            smi = _smiles_of(doc)
            if not smi:
                continue
            y = _label_of(doc, label)
            if y is None:
                continue
            w.writerow([smi, y])
            n += 1
            pos += int(y == 1)
    return n, pos


def _smiles_of(doc: dict) -> str:
    for p in (doc.get("calculated-properties") or []):
        if isinstance(p, dict) and str(p.get("kind", "")).upper() == "SMILES":
            return (p.get("value") or "").strip()
    return ""


def _label_of(doc: dict, label: str):
    if label == "chembl_moa":
        moa = doc.get("mechanism_of_action") or (doc.get("chembl") or {}).get("mechanism_of_action")
        return 1 if moa else 0
    raise SystemExit(f"Etiqueta desconocida: {label!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/synthemol_train.csv",
                    help="CSV de entrenamiento (smiles,activity) para el predictor")
    ap.add_argument("--label", default="chembl_moa",
                    help="etiqueta binaria a exportar (ejemplo de andamiaje)")
    args = ap.parse_args()

    n, pos = export_training_csv(args.out, args.label)
    log.info("Exportadas %d filas (%d positivas) a %s", n, pos, args.out)

    print("\n── Siguientes pasos para habilitar el motor SyntheMol ─────────────────────")
    print("  1) pip install synthemol            # trae chemprop + chemfunc + torch")
    print("  2) Descarga la biblioteca de bloques (Enamine REAL / WuXi) del repo SyntheMol:")
    print("     https://github.com/swansonk14/SyntheMol  (sección Data)")
    print("     export SYNTHEMOL_BUILDING_BLOCKS=/ruta/building_blocks.csv")
    print("  3) Entrena el predictor de bioactividad con el CSV exportado:")
    print(f"     chemprop_train --data_path {args.out} --dataset_type classification \\")
    print("                    --save_dir models/chemprop")
    print("     export SYNTHEMOL_SCORE_MODEL=models/chemprop")
    print("     export SYNTHEMOL_SCORE_TYPE=chemprop")
    print("  4) (opcional) SYNTHEMOL_CHEMICAL_SPACE=real|wuxi, SYNTHEMOL_N_ROLLOUT=200")
    print("  Con esas env vars, POST /api/tools/denovo/ {engine:'synthemol'} queda operativo.\n")
    print("  NOTA: la búsqueda MCTS/RL es intensiva en RAM/CPU; en este equipo mantén "
          "SYNTHEMOL_N_ROLLOUT bajo (ver docs/DATASET_STATE.md).\n")


if __name__ == "__main__":
    main()
