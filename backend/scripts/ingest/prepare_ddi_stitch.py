"""Normalizador de fuentes DDI crudas → CSV que consume `step04_ddi_open.py`.

No toca ninguna base de datos: es una transformación fichero→fichero.

FUENTES SOPORTADAS
------------------
* **TWOSIDES** (nSIDES / Tatonetti Lab, licencia CC0 — uso libre).
  El volcado crudo identifica los fármacos con **STITCH stereo/flat-CIDs**
  (`CIDs########` = estéreo, `CIDm########` = plano/mezclado). Este script los
  convierte a PubChem CID entero (quita el prefijo `CIDs`/`CIDm` y los ceros a la
  izquierda) y emite el CSV en **modo CID**:
        cid_a,cid_b,description,severity
  `description` = nombre del evento adverso (columna de condición) o, si no hay,
  el texto fijo "DDI reportada por farmacovigilancia".
  Descarga (no automática, puede pesar): https://nsides.io /
  https://tatonettilab.org/resources/nsides/

* **DDInter 2.0** (`--source ddinter`, licencia CC BY-NC-SA — solo académico).
  Se resuelve por **nombre**, así que emite el CSV en **modo nombre**:
        name_a,name_b,description,severity
  `severity` = nivel de interacción (Major/Moderate/Minor) si la columna existe.
  Descarga: http://ddinter.scbdd.com/

DETECCIÓN DE COLUMNAS
---------------------
Por defecto se autodetectan las columnas. Para TWOSIDES se buscan dos columnas cuyos
valores tengan forma de STITCH-CID (`CID[ms]\\d+`); para DDInter, dos columnas de
nombre de fármaco. Puedes forzarlas con --col-a/--col-b (y --col-event/--col-severity).
Autodetecta el separador (TSV/CSV) y soporta ficheros .gz.

USO
---
    # TWOSIDES (STITCH-CID → PubChem CID) → modo CID
    python -m scripts.ingest.prepare_ddi_stitch \\
        --twosides data/raw/twosides.tsv.gz --out data/ddi_twosides.csv

    # columnas explícitas si el header no es reconocible
    python -m scripts.ingest.prepare_ddi_stitch --twosides data/raw/twosides.tsv \\
        --col-a stitch_id1 --col-b stitch_id2 --col-event condition_name \\
        --out data/ddi_twosides.csv

    # DDInter (resuelve por nombre) → modo nombre
    python -m scripts.ingest.prepare_ddi_stitch --source ddinter \\
        --twosides data/raw/ddinter_downloads.csv --out data/ddinter.csv
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import re
import sys

from scripts.ingest._common import log

try:  # barra de progreso opcional
    from tqdm import tqdm
except Exception:  # pragma: no cover
    tqdm = None

# STITCH chemical id: CIDs######## (estéreo) / CIDm######## (plano). Los dígitos,
# sin ceros a la izquierda, son el PubChem CID.
_STITCH_RE = re.compile(r"^CID[ms]?(\d+)$", re.IGNORECASE)

# Candidatos de nombre de columna por rol (se prueban en orden, case-insensitive).
_CID_A_CANDIDATES = ("stitch_id1", "stitch_id_1", "drug1_stitch", "cid_1", "cid1",
                     "chem1", "chemical1", "stitch1")
_CID_B_CANDIDATES = ("stitch_id2", "stitch_id_2", "drug2_stitch", "cid_2", "cid2",
                     "chem2", "chemical2", "stitch2")
_NAME_A_CANDIDATES = ("drug_a", "drug1", "drug_1", "name_a", "drug1_concept_name",
                      "drug_1_concept_name")
_NAME_B_CANDIDATES = ("drug_b", "drug2", "drug_2", "name_b", "drug2_concept_name",
                      "drug_2_concept_name")
_EVENT_CANDIDATES = ("condition_concept_name", "condition_name", "event_name",
                     "side_effect_name", "condition_meddra_name", "event",
                     "side_effect")
_SEVERITY_CANDIDATES = ("level", "severity", "interaction_level", "prr",
                        "mean_reporting_frequency")

_DEFAULT_DESC = "DDI reportada por farmacovigilancia"


# ── Utilidades ──────────────────────────────────────────────────────────────────
def _open_text(path: str):
    """Abre texto, transparente a gzip por extensión."""
    if path.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def _sniff_reader(fh):
    """Devuelve un csv.DictReader con el separador detectado (\\t por defecto)."""
    sample = fh.read(8192)
    fh.seek(0)
    delimiter = "\t"
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="\t,;")
        delimiter = dialect.delimiter
    except Exception:
        # heurística simple: más tabs que comas ⇒ TSV
        if sample.count(",") > sample.count("\t"):
            delimiter = ","
    return csv.DictReader(fh, delimiter=delimiter), delimiter


def stitch_to_cid(raw) -> str | None:
    """`CIDs00012345`/`CIDm12345`/`12345` → '12345' (o None si no hay dígitos)."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    m = _STITCH_RE.match(s)
    if m:
        s = m.group(1)
    digits = re.sub(r"\D", "", s)
    if not digits:
        return None
    return str(int(digits))


def _pick_column(fieldnames, candidates, forced=None):
    """Elige la primera columna cuyo nombre coincida (case-insensitive) o la forzada."""
    if forced:
        # match tolerante a mayúsculas/espacios
        low = {(c or "").strip().lower(): c for c in (fieldnames or [])}
        key = forced.strip().lower()
        if key in low:
            return low[key]
        raise SystemExit(f"Columna forzada no encontrada: {forced!r}. Disponibles: {fieldnames}")
    low = {(c or "").strip().lower(): c for c in (fieldnames or [])}
    for cand in candidates:
        if cand in low:
            return low[cand]
    return None


def _autodetect_cid_columns(reader, fieldnames):
    """Escanea la primera fila de datos y devuelve las 2 columnas con forma STITCH-CID."""
    try:
        first = next(reader)
    except StopIteration:
        raise SystemExit("El fichero no tiene filas de datos.")
    matches = [c for c in fieldnames if _STITCH_RE.match((first.get(c) or "").strip())]
    return matches[:2], first


# ── Conversión TWOSIDES (modo CID) ──────────────────────────────────────────────
def convert_twosides(path, out_path, col_a=None, col_b=None, col_event=None,
                     col_severity=None):
    fh = _open_text(path)
    reader, delim = _sniff_reader(fh)
    fields = reader.fieldnames or []
    log.info("Separador detectado: %r · columnas: %s", delim, fields)

    a_col = _pick_column(fields, _CID_A_CANDIDATES, col_a)
    b_col = _pick_column(fields, _CID_B_CANDIDATES, col_b)
    first_row = None
    if not (a_col and b_col):
        log.info("Sin columnas de CID reconocidas por nombre; autodetectando por valor…")
        auto, first_row = _autodetect_cid_columns(reader, fields)
        if len(auto) < 2:
            raise SystemExit(
                "No se detectaron 2 columnas con STITCH-CID. Usa --col-a/--col-b.")
        a_col, b_col = auto[0], auto[1]
    ev_col = _pick_column(fields, _EVENT_CANDIDATES, col_event)
    sev_col = _pick_column(fields, _SEVERITY_CANDIDATES, col_severity)
    log.info("Mapeo: cid_a=%s cid_b=%s description=%s severity=%s",
             a_col, b_col, ev_col or "(fijo)", sev_col or "(vacío)")

    written, skipped = 0, 0
    with open(out_path, "w", newline="", encoding="utf-8") as outfh:
        w = csv.writer(outfh)
        w.writerow(["cid_a", "cid_b", "description", "severity"])

        def _emit(row):
            nonlocal written, skipped
            ca = stitch_to_cid(row.get(a_col))
            cb = stitch_to_cid(row.get(b_col))
            if not ca or not cb or ca == cb:
                skipped += 1
                return
            desc = (row.get(ev_col) or "").strip() if ev_col else ""
            sev = (row.get(sev_col) or "").strip() if sev_col else ""
            w.writerow([ca, cb, desc or _DEFAULT_DESC, sev])
            written += 1

        if first_row is not None:  # ya consumida por la autodetección
            _emit(first_row)
        it = tqdm(reader, desc="TWOSIDES", unit=" filas") if tqdm else reader
        for row in it:
            _emit(row)

    fh.close()
    log.info("TWOSIDES → %s: %d pares escritos, %d descartados (CID inválido/auto-par).",
             out_path, written, skipped)
    return written


# ── Conversión DDInter (modo nombre) ────────────────────────────────────────────
def convert_ddinter(path, out_path, col_a=None, col_b=None, col_severity=None):
    fh = _open_text(path)
    reader, delim = _sniff_reader(fh)
    fields = reader.fieldnames or []
    log.info("Separador detectado: %r · columnas: %s", delim, fields)

    a_col = _pick_column(fields, _NAME_A_CANDIDATES, col_a)
    b_col = _pick_column(fields, _NAME_B_CANDIDATES, col_b)
    if not (a_col and b_col):
        raise SystemExit(
            "No se reconocen columnas de nombre de fármaco. Usa --col-a/--col-b.")
    sev_col = _pick_column(fields, _SEVERITY_CANDIDATES, col_severity)
    log.info("Mapeo: name_a=%s name_b=%s severity=%s", a_col, b_col, sev_col or "(vacío)")

    written, skipped = 0, 0
    with open(out_path, "w", newline="", encoding="utf-8") as outfh:
        w = csv.writer(outfh)
        w.writerow(["name_a", "name_b", "description", "severity"])
        it = tqdm(reader, desc="DDInter", unit=" filas") if tqdm else reader
        for row in it:
            na = (row.get(a_col) or "").strip()
            nb = (row.get(b_col) or "").strip()
            if not na or not nb or na.lower() == nb.lower():
                skipped += 1
                continue
            sev = (row.get(sev_col) or "").strip() if sev_col else ""
            desc = f"Interacción DDInter ({sev})" if sev else "Interacción DDInter"
            w.writerow([na, nb, desc, sev])
            written += 1

    fh.close()
    log.info("DDInter → %s: %d pares escritos, %d descartados.", out_path, written, skipped)
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Normaliza TWOSIDES/DDInter crudos al CSV de step04_ddi_open.")
    ap.add_argument("--twosides", required=True,
                    help="Ruta al fichero crudo (TWOSIDES por defecto; DDInter con --source ddinter). "
                         "Admite .gz.")
    ap.add_argument("--out", required=True, help="CSV de salida para step04")
    ap.add_argument("--source", choices=["twosides", "ddinter"], default="twosides",
                    help="twosides → salida por CID; ddinter → salida por nombre")
    ap.add_argument("--col-a", default=None, help="Forzar columna del fármaco A")
    ap.add_argument("--col-b", default=None, help="Forzar columna del fármaco B")
    ap.add_argument("--col-event", default=None,
                    help="(TWOSIDES) Forzar columna del evento adverso → description")
    ap.add_argument("--col-severity", default=None, help="Forzar columna de severidad")
    args = ap.parse_args(argv)

    if args.source == "ddinter":
        convert_ddinter(args.twosides, args.out,
                        col_a=args.col_a, col_b=args.col_b, col_severity=args.col_severity)
    else:
        convert_twosides(args.twosides, args.out,
                         col_a=args.col_a, col_b=args.col_b,
                         col_event=args.col_event, col_severity=args.col_severity)
    return 0


if __name__ == "__main__":
    sys.exit(main())
