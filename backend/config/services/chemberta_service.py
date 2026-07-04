"""
chemberta_service.py — Embeddings moleculares aprendidos (ChemBERTa) — Tier 3.2.

ChemBERTa es un transformer preentrenado sobre SMILES (ZINC). Su embedding captura
similitud química/bioactiva que va más allá de la similitud de subestructura de los
fingerprints clásicos (evidencia 2025). Aquí se usa para similitud molecular por
vecino más cercano (coseno) contra los fármacos de la base.

Dependencias OPCIONALES y pesadas: `torch` + `transformers`. Si no están instaladas,
EMBEDDINGS_OK es False y los endpoints devuelven 503 (degradación elegante, como GDS/BLAST).

Modelo: seyonec/ChemBERTa-zinc-base-v1 (se descarga la primera vez, ~150 MB).
Configurable con la env var CHEMBERTA_MODEL.
"""

import logging
import os
import threading

log = logging.getLogger(__name__)

MODEL_NAME = os.environ.get("CHEMBERTA_MODEL", "seyonec/ChemBERTa-zinc-base-v1")
EMBED_DIM = 768
MAX_TOKENS = 256

try:
    import torch
    from transformers import AutoTokenizer, AutoModel
    EMBEDDINGS_OK = True
except ImportError:
    EMBEDDINGS_OK = False
    log.info("torch/transformers no instalados — embeddings ChemBERTa deshabilitados.")

_model = None
_tokenizer = None
_load_lock = threading.Lock()


def _ensure_model():
    """Carga perezosa del modelo/tokenizer (una sola vez, thread-safe)."""
    global _model, _tokenizer
    if _model is not None:
        return
    with _load_lock:
        if _model is not None:
            return
        log.info("Cargando modelo ChemBERTa '%s'…", MODEL_NAME)
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModel.from_pretrained(MODEL_NAME)
        _model.eval()


def embed(smiles: str) -> list[float] | None:
    """
    Devuelve el embedding (mean-pooling del último hidden state) de un SMILES,
    como lista de floats de dimensión EMBED_DIM. None si no es posible.
    """
    if not EMBEDDINGS_OK or not smiles:
        return None
    _ensure_model()
    try:
        with torch.no_grad():
            enc = _tokenizer(
                smiles, return_tensors="pt", truncation=True, max_length=MAX_TOKENS,
            )
            out = _model(**enc)
            # mean pooling ponderado por la máscara de atención
            hidden = out.last_hidden_state          # (1, T, H)
            mask = enc["attention_mask"].unsqueeze(-1).float()  # (1, T, 1)
            summed = (hidden * mask).sum(dim=1)
            counts = mask.sum(dim=1).clamp(min=1e-9)
            vec = (summed / counts).squeeze(0)      # (H,)
            return vec.tolist()
    except Exception as exc:
        log.error("ChemBERTa embed error: %s", exc)
        return None
