"""
chemprop_service.py — GNN Chemprop (D-MPNN) multi-tarea de toxicidad (Tier 4.6).

Chemprop (Heid et al., J. Chem. Inf. Model. 2024; Yang et al. 2019, MIT) es un GNN de paso de
mensajes dirigido (D-MPNN) que APRENDE la representación molecular del grafo, en vez de usar un
fingerprint fijo. Implementa la recomendación #1 del roadmap (docs/TIER4_ACTIVATION.md §5), a
partir del repo `Antibiotics_Chemprop`. Aquí se sirve un modelo multi-tarea sobre los 12 ensayos
de Tox21: un solo modelo cubre las 12 toxicidades. Complementa al ADMET por RandomForest (4.3) —
GNN aprendido vs. features RDKit fijos — y puede usarse como score model de SyntheMol (4.4).

Predicción vía el CLI `chemprop predict` por subprocess (robusto entre versiones de chemprop),
igual que el motor SyntheMol. Dependencia OPCIONAL y pesada (`chemprop` + torch). Si falta el
paquete o el modelo entrenado, loaded()/model_ready() es False y predict() devuelve available=False
(→ 503), como el resto de features pesadas. Entrenar con scripts/train_chemprop.py.
"""

import csv
import logging
import os
import subprocess
import sys
import tempfile

log = logging.getLogger(__name__)


def chemprop_bin() -> str:
    """Ruta al CLI `chemprop` del mismo entorno que el Python actual (no depende del PATH)."""
    cand = os.path.join(os.path.dirname(sys.executable), "chemprop")
    return cand if os.path.exists(cand) else "chemprop"

MODEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "models", "chemprop",
)

# Los 12 ensayos de Tox21 (orden = columnas objetivo del entrenamiento y de la salida).
TOX21_TASKS = [
    "NR-AR", "NR-AR-LBD", "NR-AhR", "NR-Aromatase", "NR-ER", "NR-ER-LBD",
    "NR-PPAR-gamma", "SR-ARE", "SR-ATAD5", "SR-HSE", "SR-MMP", "SR-p53",
]

# Etiquetas legibles para la UI/reportería.
TASK_LABELS = {
    "NR-AR": "Receptor de andrógenos", "NR-AR-LBD": "Receptor de andrógenos (LBD)",
    "NR-AhR": "Receptor de aril-hidrocarburos", "NR-Aromatase": "Aromatasa",
    "NR-ER": "Receptor de estrógenos", "NR-ER-LBD": "Receptor de estrógenos (LBD)",
    "NR-PPAR-gamma": "PPAR-γ", "SR-ARE": "Respuesta antioxidante (ARE)",
    "SR-ATAD5": "Daño al ADN (ATAD5)", "SR-HSE": "Choque térmico (HSE)",
    "SR-MMP": "Potencial mitocondrial (MMP)", "SR-p53": "Vía de estrés p53",
}

PAPER = ("Heid E, et al. Chemprop: A Machine Learning Package for Chemical Property "
         "Prediction. J Chem Inf Model. 2024;64(1):9-17. doi:10.1021/acs.jcim.3c01250")

try:
    import chemprop  # noqa: F401  (solo comprobamos disponibilidad)
    CHEMPROP_OK = True
except ImportError:
    CHEMPROP_OK = False
    log.info("chemprop no instalado — GNN de toxicidad (Tier 4.6) deshabilitado.")


def _model_path() -> str:
    """Ruta al checkpoint entrenado (models/chemprop/tox21/**/*.pt|*.ckpt), o ''."""
    base = os.path.join(MODEL_DIR, "tox21")
    if not os.path.isdir(base):
        return ""
    for root, _dirs, files in os.walk(base):
        for f in files:
            if f.endswith((".pt", ".ckpt")):
                return os.path.join(root, f)
    return ""


def model_ready() -> bool:
    return CHEMPROP_OK and bool(_model_path())


# alias por consistencia con admet_service.loaded()
def loaded() -> bool:
    return model_ready()


def predict(smiles: str) -> dict:
    """
    Predice las 12 probabilidades de toxicidad Tox21 para un SMILES con el GNN Chemprop.
    Degrada con available=False si chemprop o el modelo no están.
    """
    smiles = (smiles or "").strip()
    if not smiles:
        return {"available": False, "reason": "SMILES vacío."}
    if not CHEMPROP_OK:
        return {"available": False,
                "reason": "chemprop no instalado (pip install chemprop, requirements-ml.txt)."}
    model = _model_path()
    if not model:
        return {"available": False,
                "reason": "Modelo Chemprop no entrenado (ver scripts/train_chemprop.py)."}

    try:
        probs = _run_predict(smiles, model)
    except Exception as exc:
        log.error("chemprop predict error: %s", exc)
        return {"available": False, "reason": f"Error ejecutando Chemprop: {exc}"}

    predictions = []
    for task in TOX21_TASKS:
        p = probs.get(task)
        predictions.append({
            "assay": task,
            "label": TASK_LABELS.get(task, task),
            "probability": None if p is None else round(float(p), 4),
        })
    # Orden por probabilidad desc (los None al final) para destacar las toxicidades más probables.
    predictions.sort(key=lambda d: (d["probability"] is None, -(d["probability"] or 0)))

    return {
        "available": True,
        "engine": "chemprop-dmpnn",
        "paper": PAPER,
        "smiles": smiles,
        "predictions": predictions,
        "disclaimer": "Predicción in silico de un GNN entrenado en Tox21 (MoleculeNet); "
                      "no sustituye ensayos de toxicidad experimentales.",
    }


def _run_predict(smiles: str, model_path: str) -> dict:
    """Lanza `chemprop predict` sobre un SMILES y devuelve {tarea: prob}."""
    with tempfile.TemporaryDirectory(prefix="chemprop_") as tmp:
        in_csv = os.path.join(tmp, "in.csv")
        out_csv = os.path.join(tmp, "out.csv")
        with open(in_csv, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["smiles"])
            w.writerow([smiles])

        cmd = [
            chemprop_bin(), "predict",
            "-i", in_csv,
            "--model-paths", model_path,
            "-o", out_csv,
            "-s", "smiles",
            "--accelerator", "cpu",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "sin salida").strip()[-500:])

        with open(out_csv, newline="") as fh:
            reader = csv.DictReader(fh)
            row = next(reader, None)
        if not row:
            raise RuntimeError("chemprop no devolvió predicciones.")
        # Las columnas de salida son las tareas (mismos nombres) además de 'smiles'.
        out = {}
        for task in TOX21_TASKS:
            val = row.get(task)
            try:
                out[task] = float(val) if val not in (None, "") else None
            except (TypeError, ValueError):
                out[task] = None
        return out
