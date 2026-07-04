"""
admet_service.py — Predicción ADMET/toxicidad con modelos supervisados propios (Tier 4.3).

A diferencia del resto de la plataforma (inferencia de terceros o heurísticas), aquí
ENTRENAMOS modelos scikit-learn sobre datasets públicos de MoleculeNet (Tox21, BBBP, ESOL)
y los servimos desde el SMILES. Cada endpoint reporta su métrica de test (ROC-AUC para
clasificación, RMSE para regresión) para transmitir la incertidumbre.

Featurización compartida entre entrenamiento (scripts/train_admet_models.py) e inferencia:
descriptores RDKit + fingerprint Morgan. Deps: scikit-learn + joblib (+ RDKit ya presente).
Si faltan las deps o los modelos entrenados, ADMET_OK/loaded() es False → 503.
"""

import json
import logging
import os

log = logging.getLogger(__name__)

MODEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "models", "admet",
)
METRICS_PATH = os.path.join(MODEL_DIR, "metrics.json")

# Registro de endpoints ADMET entrenables. `column` es la etiqueta en el CSV de origen.
ENDPOINTS = {
    "bbbp": {
        "label": "Penetración barrera hematoencefálica (BBBP)",
        "task": "classification", "dataset": "bbbp", "column": "p_np",
        "positive": "penetra la BHE",
    },
    "esol": {
        "label": "Solubilidad acuosa (ESOL, logS)",
        "task": "regression", "dataset": "delaney", "column": "measured log solubility in mols per litre",
        "unit": "log mol/L",
    },
    "tox21_nr_ar": {
        "label": "Actividad receptor de andrógenos (Tox21 NR-AR)",
        "task": "classification", "dataset": "tox21", "column": "NR-AR",
        "positive": "activo (posible toxicidad)",
    },
    "tox21_sr_p53": {
        "label": "Vía de estrés p53 (Tox21 SR-p53)",
        "task": "classification", "dataset": "tox21", "column": "SR-p53",
        "positive": "activo (estrés genotóxico)",
    },
}

FP_NBITS = 1024

try:
    import numpy as np
    import joblib
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor  # noqa: F401
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdFingerprintGenerator
    _MORGAN_GEN = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=FP_NBITS)
    ADMET_OK = True
except ImportError:
    ADMET_OK = False
    log.info("scikit-learn/joblib/RDKit no disponibles — ADMET supervisado deshabilitado.")

_models: dict = {}
_metrics: dict | None = None


# ── Featurización (compartida entrenamiento/inferencia) ─────────────────────────

# Descriptores RDKit fijos (el orden importa: define la dimensión del vector).
_DESCRIPTORS = [
    ("mol_weight", lambda m: Descriptors.MolWt(m)),
    ("logp", lambda m: Descriptors.MolLogP(m)),
    ("tpsa", lambda m: Descriptors.TPSA(m)),
    ("h_donors", lambda m: Descriptors.NumHDonors(m)),
    ("h_acceptors", lambda m: Descriptors.NumHAcceptors(m)),
    ("rotatable_bonds", lambda m: Descriptors.NumRotatableBonds(m)),
    ("aromatic_rings", lambda m: Descriptors.NumAromaticRings(m)),
    ("fraction_csp3", lambda m: Descriptors.FractionCSP3(m)),
    ("heavy_atoms", lambda m: float(m.GetNumHeavyAtoms())),
    ("qed", lambda m: Descriptors.qed(m)),
]


def featurize(smiles: str):
    """SMILES → vector (descriptores RDKit + fingerprint Morgan) o None si inválido."""
    if not ADMET_OK or not smiles:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    desc = []
    for _, fn in _DESCRIPTORS:
        try:
            desc.append(float(fn(mol)))
        except Exception:
            desc.append(0.0)
    fp = _MORGAN_GEN.GetFingerprint(mol)
    fp_arr = np.zeros((FP_NBITS,), dtype="float32")
    from rdkit import DataStructs
    DataStructs.ConvertToNumpyArray(fp, fp_arr)
    return np.concatenate([np.array(desc, dtype="float32"), fp_arr])


# ── Carga de modelos + inferencia ───────────────────────────────────────────────

def _load():
    """Carga perezosa de modelos joblib + metrics.json."""
    global _metrics
    if _metrics is None and os.path.exists(METRICS_PATH):
        try:
            with open(METRICS_PATH) as fh:
                _metrics = json.load(fh)
        except Exception:
            _metrics = {}
    for name in ENDPOINTS:
        if name in _models:
            continue
        path = os.path.join(MODEL_DIR, f"{name}.joblib")
        if os.path.exists(path):
            try:
                _models[name] = joblib.load(path)
            except Exception as exc:
                log.warning("No se pudo cargar el modelo ADMET %s: %s", name, exc)


def loaded() -> bool:
    """True si hay al menos un modelo entrenado disponible."""
    if not ADMET_OK:
        return False
    _load()
    return len(_models) > 0


def predict(smiles: str) -> dict:
    """
    Predice todos los endpoints ADMET disponibles para un SMILES.
    Devuelve {available, smiles, predictions:[{endpoint, label, task, value|proba, model_metric}]}.
    """
    if not ADMET_OK:
        return {"available": False, "reason": "scikit-learn/RDKit no disponibles."}
    _load()
    if not _models:
        return {"available": False, "reason": "Modelos ADMET no entrenados. Ejecuta train_admet_models.py."}

    feats = featurize(smiles)
    if feats is None:
        return {"available": False, "reason": "SMILES inválido."}

    X = feats.reshape(1, -1)
    metrics = _metrics or {}
    predictions = []
    for name, meta in ENDPOINTS.items():
        model = _models.get(name)
        if model is None:
            continue
        m = metrics.get(name, {})
        try:
            if meta["task"] == "classification":
                proba = float(model.predict_proba(X)[0][1])
                predictions.append({
                    "endpoint": name, "label": meta["label"], "task": "classification",
                    "proba": round(proba, 4), "positive_meaning": meta.get("positive"),
                    "model_auc": m.get("roc_auc"), "n_train": m.get("n_train"),
                })
            else:
                value = float(model.predict(X)[0])
                predictions.append({
                    "endpoint": name, "label": meta["label"], "task": "regression",
                    "value": round(value, 4), "unit": meta.get("unit"),
                    "model_rmse": m.get("rmse"), "n_train": m.get("n_train"),
                })
        except Exception as exc:
            log.warning("Predicción ADMET %s falló: %s", name, exc)

    return {"available": True, "smiles": smiles, "predictions": predictions}
