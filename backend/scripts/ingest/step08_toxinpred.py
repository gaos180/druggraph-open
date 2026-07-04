"""ETL paso 8 (enriquecedor) — toxicidad de péptidos con ToxinPred (modo por lote).

ToxinPred (Raghava Lab, IIIT-Delhi) predice la toxicidad de PÉPTIDOS a partir de su
secuencia de aminoácidos. NO existe una API pública estable, por lo que este script
NO inventa un endpoint: implementa un flujo honesto en dos modos que rodea al servidor
web / binario de ToxinPred.

    https://webs.iiitd.edu.in/raghava/toxinpred/   (predicción online por lote)

Campo que añade al documento Mongo `drugs`:
    `toxinpred` = { prediction: "Toxin"|"Non-Toxin", score: float|None,
                    sequence: str, source: "ToxinPred" }

────────────────────────────────────────────────────────────────────────────────
REQUIERE INPUT EXTERNO. El documento de DrugCentral NO trae la secuencia peptídica,
así que el operador debe aportarla. Flujo recomendado:

  1) `--mode export`  → escribe un FASTA con los fármacos peptídicos candidatos
     (type == "biotech" o los que ya tengan una secuencia en el documento). El
     encabezado es `>DC<id>|<name>` para poder re-emparejar después.
        Si un candidato no tiene secuencia en el documento, se lista aparte para que
        el operador la complete manualmente (p.ej. desde UniProt/fuente del péptido).

  2) El operador sube ese FASTA a ToxinPred (o corre su binario) y descarga el CSV
     de resultados.

  3) `--mode annotate --csv toxinpred_out.csv` → lee el CSV y escribe el campo
     `toxinpred` en cada fármaco peptídico, emparejando por ID (`DC…`) o por nombre.

El parser de CSV es tolerante: los nombres de columna son configurables por flag y se
buscan sin distinguir mayúsculas. Por defecto asume columnas típicas de ToxinPred
(`ID`, `Sequence`, `Prediction`, `Score`/`SVM Score`/`ML Score`).

Idempotente: `update_one($set)` por fármaco.

Uso (desde backend/, con el venv activo):
    # 1. exportar candidatos a FASTA (para subir a ToxinPred)
    python -m scripts.ingest.step08_toxinpred --mode export --out peptidos.fasta

    # 2. anotar desde el CSV de ToxinPred
    python -m scripts.ingest.step08_toxinpred --mode annotate --csv toxinpred_out.csv
    python -m scripts.ingest.step08_toxinpred --mode annotate --csv out.csv \\
        --id-col ID --seq-col Sequence --pred-col Prediction --score-col "ML Score" --match id
"""
from __future__ import annotations

import argparse
import csv

from scripts.ingest._common import log, mongo_db

# Posibles campos donde el documento podría traer ya la secuencia peptídica.
_SEQ_FIELDS = ("sequence", "peptide-sequence", "peptide_sequence", "aa_sequence")

# Aliases de columnas del CSV de ToxinPred (búsqueda case-insensitive).
_ID_ALIASES = ("id", "peptide id", "name", "seq_id", "#")
_SEQ_ALIASES = ("sequence", "seq", "peptide")
_PRED_ALIASES = ("prediction", "result", "class", "toxicity")
_SCORE_ALIASES = ("score", "ml score", "svm score", "prediction score", "hybrid score")


# ── modo export ────────────────────────────────────────────────────────────────
def _peptide_candidates(db, limit=None):
    """Fármacos peptídicos candidatos: type biotech o con secuencia en el documento."""
    q = {"$or": [{"type": {"$ne": "small molecule"}},
                 *[{f: {"$exists": True, "$ne": ""}} for f in _SEQ_FIELDS]]}
    proj = {"name": 1, "type": 1, "drugbank-id": 1, **{f: 1 for f in _SEQ_FIELDS}}
    cur = db.drugs.find(q, proj)
    if limit:
        cur = cur.limit(limit)
    return list(cur)


def _doc_sequence(doc: dict) -> str | None:
    for f in _SEQ_FIELDS:
        val = doc.get(f)
        if isinstance(val, str) and val.strip():
            return "".join(val.split()).upper()
    return None


def run_export(out_path: str, limit: int | None = None):
    db = mongo_db()
    cands = _peptide_candidates(db, limit=limit)
    with_seq = [d for d in cands if _doc_sequence(d)]
    without_seq = [d for d in cands if not _doc_sequence(d)]

    with open(out_path, "w", encoding="utf-8") as fh:
        for doc in with_seq:
            seq = _doc_sequence(doc)
            name = (doc.get("name") or "").replace("|", "/")
            fh.write(f">{doc['_id']}|{name}\n{seq}\n")

    log.info("Exportados %d péptidos con secuencia a %s.", len(with_seq), out_path)
    if without_seq:
        log.warning(
            "%d fármacos peptídicos SIN secuencia en el documento (no exportables). "
            "Completa su secuencia (UniProt/fuente) antes de someterlos a ToxinPred. "
            "Ejemplos: %s",
            len(without_seq),
            ", ".join(f"{d['_id']}={d.get('name')}" for d in without_seq[:10]),
        )
    return len(with_seq)


# ── modo annotate ──────────────────────────────────────────────────────────────
def _col_index(header: list[str], explicit: str | None, aliases: tuple[str, ...]):
    """Devuelve el índice de columna: por nombre explícito o por alias (case-insensitive)."""
    lower = [h.strip().lower() for h in header]
    if explicit:
        want = explicit.strip().lower()
        if want in lower:
            return lower.index(want)
        log.warning("Columna '%s' no está en el CSV; probando aliases.", explicit)
    for alias in aliases:
        if alias in lower:
            return lower.index(alias)
    return None


def _norm_prediction(raw: str) -> str | None:
    """Normaliza el veredicto de ToxinPred a 'Toxin' / 'Non-Toxin'."""
    if not raw:
        return None
    s = raw.strip().lower()
    if "non" in s or "no" == s or s in ("negative", "0"):
        return "Non-Toxin"
    if "toxin" in s or "toxic" in s or s in ("positive", "1", "yes"):
        return "Toxin"
    return raw.strip()


def _match_drug(db, token: str, match: str):
    """Empareja un token del CSV con un documento de fármaco (por ID o por nombre)."""
    token = (token or "").strip()
    if not token:
        return None
    # el encabezado FASTA era '>DC…|name'; toma el primer campo antes de '|' o espacio
    ident = token.split("|", 1)[0].split()[0] if token else token
    if match == "id":
        doc = db.drugs.find_one({"_id": ident}, {"_id": 1})
        if doc:
            return doc["_id"]
        doc = db.drugs.find_one({"drugbank-id": ident}, {"_id": 1})
        return doc["_id"] if doc else None
    # match == "name": nombre exacto case-insensitive
    name = token.split("|", 1)[1] if "|" in token else token
    import re
    doc = db.drugs.find_one(
        {"name": {"$regex": f"^{re.escape(name.strip())}$", "$options": "i"}}, {"_id": 1})
    return doc["_id"] if doc else None


def run_annotate(csv_path: str, id_col=None, seq_col=None, pred_col=None,
                 score_col=None, match: str = "id"):
    db = mongo_db()
    updated = unmatched = 0
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            log.warning("CSV vacío: %s", csv_path)
            return 0
        i_id = _col_index(header, id_col, _ID_ALIASES)
        i_seq = _col_index(header, seq_col, _SEQ_ALIASES)
        i_pred = _col_index(header, pred_col, _PRED_ALIASES)
        i_score = _col_index(header, score_col, _SCORE_ALIASES)
        if i_id is None or i_pred is None:
            log.warning("No se hallaron columnas de ID (%s) y/o predicción (%s) en %s. "
                        "Cabecera: %s", i_id, i_pred, csv_path, header)
            return 0

        for row in reader:
            if not row or len(row) <= i_id:
                continue
            token = row[i_id]
            mongo_id = _match_drug(db, token, match)
            if not mongo_id:
                unmatched += 1
                continue
            score = None
            if i_score is not None and i_score < len(row):
                try:
                    score = float(row[i_score])
                except (TypeError, ValueError):
                    score = None
            payload = {
                "prediction": _norm_prediction(row[i_pred] if i_pred < len(row) else ""),
                "score": score,
                "sequence": (row[i_seq].strip() if (i_seq is not None and i_seq < len(row)) else None),
                "source": "ToxinPred",
            }
            db.drugs.update_one({"_id": mongo_id}, {"$set": {"toxinpred": payload}})
            updated += 1

    log.info("ToxinPred: %d fármacos anotados con toxinpred (%d filas sin emparejar).",
             updated, unmatched)
    return updated


def run(mode: str, out: str = "peptidos.fasta", csv_path: str | None = None,
        id_col=None, seq_col=None, pred_col=None, score_col=None,
        match: str = "id", limit: int | None = None):
    if mode == "export":
        return run_export(out, limit=limit)
    if mode == "annotate":
        if not csv_path:
            log.warning("--mode annotate requiere --csv <ruta al CSV de ToxinPred>.")
            return 0
        return run_annotate(csv_path, id_col=id_col, seq_col=seq_col,
                            pred_col=pred_col, score_col=score_col, match=match)
    log.warning("Modo desconocido: %s", mode)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="ToxinPred (péptidos) — export de FASTA / annotate desde CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--mode", choices=["export", "annotate"], required=True,
                    help="export: FASTA de candidatos · annotate: escribe `toxinpred` desde el CSV")
    ap.add_argument("--out", default="peptidos.fasta", help="[export] ruta del FASTA de salida")
    ap.add_argument("--csv", dest="csv_path", default=None, help="[annotate] CSV de resultados de ToxinPred")
    ap.add_argument("--id-col", default=None, help="[annotate] nombre de la columna ID/encabezado")
    ap.add_argument("--seq-col", default=None, help="[annotate] nombre de la columna de secuencia")
    ap.add_argument("--pred-col", default=None, help="[annotate] nombre de la columna de predicción")
    ap.add_argument("--score-col", default=None, help="[annotate] nombre de la columna de score")
    ap.add_argument("--match", choices=["id", "name"], default="id",
                    help="[annotate] emparejar por ID abierto (DC…) o por nombre")
    ap.add_argument("--limit", type=int, default=None, help="[export] límite de candidatos (prueba)")
    args = ap.parse_args()
    run(mode=args.mode, out=args.out, csv_path=args.csv_path,
        id_col=args.id_col, seq_col=args.seq_col, pred_col=args.pred_col,
        score_col=args.score_col, match=args.match, limit=args.limit)
