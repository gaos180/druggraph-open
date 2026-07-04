"""
chemberta_index.py — Poblado idempotente de embeddings ChemBERTa + índice vectorial Neo4j.

Lógica reutilizada por:
  - scripts/populate_chemberta_embeddings.py (ejecución manual/batch).
  - el arranque del backend (drugs.apps.DrugsConfig.ready → autostart en segundo plano),
    de modo que la similitud por embedding queda SIEMPRE lista al correr el server, sin
    pasos manuales. Es idempotente: solo procesa los :Drug que aún no tienen `d.chemberta`,
    así que tras la primera carga los arranques siguientes son un no-op rápido.

Requiere torch+transformers (opcionales) — si faltan, no hace nada (degradación elegante).
"""

import logging
import os
import threading

from config.services import chemberta_service
from config.services.chemberta_service import EMBED_DIM

log = logging.getLogger(__name__)

_autostart_lock = threading.Lock()
_autostart_done = False


def ensure_vector_index(session):
    session.run(
        f"""
        CREATE VECTOR INDEX drug_chemberta IF NOT EXISTS
        FOR (d:Drug) ON (d.chemberta)
        OPTIONS {{ indexConfig: {{
            `vector.dimensions`: {EMBED_DIM},
            `vector.similarity_function`: 'cosine'
        }} }}
        """
    )


def count_status() -> dict:
    """Cuenta :Drug totales, con embedding y pendientes (rápido, sin cargar el modelo)."""
    from config.services.neo4j_service import _session
    with _session() as session:
        total = session.run("MATCH (d:Drug) WHERE d.drugbank_id IS NOT NULL RETURN count(d) AS c").single()["c"]
        with_emb = session.run("MATCH (d:Drug) WHERE d.chemberta IS NOT NULL RETURN count(d) AS c").single()["c"]
    return {"total": total, "with_embedding": with_emb, "pending": total - with_emb}


def _smiles_for(db, drugbank_id: str) -> str:
    doc = db.drugs.find_one({"drugbank-id": drugbank_id}, {"calculated-properties": 1}) \
        or db.drugs.find_one({"drugbank-id.value": drugbank_id}, {"calculated-properties": 1})
    if not doc:
        return ""
    for p in doc.get("calculated-properties") or []:
        if isinstance(p, dict) and str(p.get("kind", "")).upper() == "SMILES":
            return (p.get("value") or "").strip()
    return ""


def populate_missing(limit: int = 0, batch: int = 100) -> dict:
    """
    Calcula embeddings SOLO para los :Drug sin `d.chemberta` y asegura el índice vectorial.
    Idempotente. Devuelve {done, skipped, remaining}.
    """
    if not chemberta_service.EMBEDDINGS_OK:
        log.info("ChemBERTa no disponible (torch/transformers no instalados) — se omite el poblado.")
        return {"done": 0, "skipped": 0, "remaining": 0, "available": False}

    from config.services.neo4j_service import _session
    from config.services.mongo import get_db

    db = get_db()
    with _session() as session:
        ensure_vector_index(session)
        rows = session.run(
            "MATCH (d:Drug) WHERE d.drugbank_id IS NOT NULL AND d.chemberta IS NULL "
            "RETURN d.drugbank_id AS id ORDER BY id"
        ).data()
        ids = [r["id"] for r in rows]
        if limit:
            ids = ids[:limit]

        if not ids:
            log.info("ChemBERTa: todos los fármacos ya tienen embedding (nada que hacer).")
            return {"done": 0, "skipped": 0, "remaining": 0, "available": True}

        log.info("ChemBERTa: poblando %d embeddings pendientes…", len(ids))
        done = skipped = 0
        pending: list = []
        for dbid in ids:
            smiles = _smiles_for(db, dbid)
            if not smiles:
                skipped += 1
                continue
            vec = chemberta_service.embed(smiles)
            if not vec:
                skipped += 1
                continue
            pending.append({"id": dbid, "vec": vec})
            if len(pending) >= batch:
                _flush(session, pending); done += len(pending); pending = []
        if pending:
            _flush(session, pending); done += len(pending)

        remaining = session.run(
            "MATCH (d:Drug) WHERE d.drugbank_id IS NOT NULL AND d.chemberta IS NULL RETURN count(d) AS c"
        ).single()["c"]

    log.info("ChemBERTa: %d embeddings nuevos, %d sin SMILES, %d aún pendientes.", done, skipped, remaining)
    return {"done": done, "skipped": skipped, "remaining": remaining, "available": True}


def _flush(session, batch):
    session.run(
        """
        UNWIND $rows AS r
        MATCH (d:Drug {drugbank_id: r.id})
        CALL db.create.setNodeVectorProperty(d, 'chemberta', r.vec)
        """,
        rows=batch,
    )


def autostart_in_background():
    """
    Lanza el poblado idempotente en un hilo daemon (no bloquea el arranque del server).
    Controlado por la env var CHEMBERTA_AUTOSTART (default '1'; '0' para desactivar).
    Solo actúa una vez por proceso.
    """
    global _autostart_done
    if os.environ.get("CHEMBERTA_AUTOSTART", "1").lower() in ("0", "false", "no"):
        return
    if not chemberta_service.EMBEDDINGS_OK:
        return  # torch/transformers no instalados → nada que activar

    with _autostart_lock:
        if _autostart_done:
            return
        _autostart_done = True

    def _run():
        try:
            populate_missing()
        except Exception as exc:
            log.warning("ChemBERTa autostart falló (no crítico): %s", exc)

    t = threading.Thread(target=_run, name="chemberta-autostart", daemon=True)
    t.start()
    log.info("ChemBERTa: autostart lanzado en segundo plano.")
