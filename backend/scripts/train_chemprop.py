#!/usr/bin/env python3
"""
train_chemprop.py — Entrena un GNN Chemprop (D-MPNN) multi-tarea de toxicidad (Tier 4.6).

Implementa la recomendación #1 del roadmap de métodos externos (docs/TIER4_ACTIVATION.md §5):
Chemprop (repo `Antibiotics_Chemprop`; Heid et al., J. Chem. Inf. Model. 2024; Yang et al. 2019)
es un GNN de paso de mensajes (D-MPNN) que aprende la representación molecular en vez de usar
fingerprints fijos. Aquí se entrena en **multi-tarea** sobre los 12 ensayos de Tox21, así un solo
modelo (y una sola llamada de predicción) cubre las 12 toxicidades — complementa al ADMET por
RandomForest (4.3, single-task, features RDKit) con un GNN, y sirve como score model de SyntheMol.

Usa el CLI de chemprop por subprocess (robusto entre versiones), igual que el motor SyntheMol.

USO (desde backend/, con el venv activo; requiere `pip install chemprop`):
    python -m scripts.train_chemprop --epochs 15
    python -m scripts.train_chemprop --data-dir /ruta/csv-locales   # usa Tox21 ya descargado

Guarda el modelo en backend/models/chemprop/tox21/ y las métricas en metrics.json.
"""

import argparse
import csv
import json
import logging
import os
import subprocess

import django

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("chemprop_train")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from config.services.chemprop_service import (  # noqa: E402
    MODEL_DIR, TOX21_TASKS, model_ready, chemprop_bin,
)

TOX21_URL = "https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/tox21.csv.gz"


def _prepare_csv(data_dir: str, out_csv: str) -> int:
    """Descarga Tox21 si falta y escribe un CSV limpio (smiles + 12 tareas) para chemprop."""
    import pandas as pd
    os.makedirs(data_dir, exist_ok=True)
    local = os.path.join(data_dir, "tox21.csv.gz")
    if not os.path.exists(local):
        import requests
        log.info("Descargando Tox21…")
        r = requests.get(TOX21_URL, timeout=120)
        r.raise_for_status()
        with open(local, "wb") as fh:
            fh.write(r.content)
    df = pd.read_csv(local)
    cols = ["smiles"] + TOX21_TASKS
    df = df[cols]

    # chemprop aborta si un SMILES es inválido → filtramos los que RDKit no parsea
    # (Tox21 trae algún complejo metálico, p. ej. de aluminio).
    from rdkit import Chem
    valid = df["smiles"].apply(lambda s: Chem.MolFromSmiles(str(s)) is not None)
    dropped = int((~valid).sum())
    if dropped:
        log.info("Descartados %d SMILES inválidos para RDKit.", dropped)
    df = df[valid]

    df.to_csv(out_csv, index=False, quoting=csv.QUOTE_MINIMAL)
    return len(df)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/moleculenet")
    ap.add_argument("--epochs", type=int, default=15)
    args = ap.parse_args()

    out_dir = os.path.join(MODEL_DIR, "tox21")
    os.makedirs(out_dir, exist_ok=True)
    train_csv = os.path.join(args.data_dir, "tox21_chemprop.csv")

    n = _prepare_csv(args.data_dir, train_csv)
    log.info("Tox21 preparado: %d moléculas, %d tareas.", n, len(TOX21_TASKS))

    cmd = [
        chemprop_bin(), "train",
        "-i", train_csv,
        "-o", out_dir,
        "-s", "smiles",
        "--target-columns", *TOX21_TASKS,
        "-t", "classification",
        "--epochs", str(args.epochs),
        "--num-workers", "0",           # evita fork de dataloaders (más estable en CPU)
        "--split", "SCAFFOLD_BALANCED", # split por scaffold: evaluación honesta (no fugas)
        "--metrics", "roc",
    ]
    log.info("Entrenando Chemprop D-MPNN multi-tarea (%d epochs)…", args.epochs)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        log.error("chemprop train falló:\n%s", (proc.stderr or proc.stdout)[-2000:])
        raise SystemExit(1)

    # chemprop escribe el checkpoint bajo out_dir/model_0/*.pt o /checkpoints/*.ckpt
    ckpt = _find_model(out_dir)
    metrics = {"tasks": TOX21_TASKS, "n_molecules": n, "epochs": args.epochs,
               "model_path": ckpt, "engine": "chemprop-dmpnn"}
    # Extrae el ROC-AUC de test del stdout de chemprop si está.
    for line in (proc.stdout or "").splitlines():
        if "test/roc" in line.lower() or "test_roc" in line.lower():
            metrics["test_log"] = line.strip()
    with open(os.path.join(out_dir, "metrics.json"), "w") as fh:
        json.dump(metrics, fh, indent=2)

    log.info("Modelo Chemprop guardado. model_ready=%s, ckpt=%s", model_ready(), ckpt)


def _find_model(out_dir: str) -> str:
    for root, _dirs, files in os.walk(out_dir):
        for f in files:
            if f.endswith((".pt", ".ckpt")):
                return os.path.join(root, f)
    return ""


if __name__ == "__main__":
    main()
