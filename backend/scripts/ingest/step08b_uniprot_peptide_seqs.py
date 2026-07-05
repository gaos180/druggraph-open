"""ETL paso 8b (enriquecedor) — secuencias de aminoácidos de péptidos desde UniProt.

DrugCentral NO trae la secuencia peptídica de los fármacos biotech/péptido, así que el
paso 8 (ToxinPred) no podía exportar ningún FASTA.  Este script intenta resolver cada
fármaco peptídico SIN secuencia a una entrada de UniProt **por nombre** y, cuando la
coincidencia es plausible, guarda la secuencia madura en el documento Mongo.

Estrategia (conservadora, para no asignar secuencias equivocadas):
  1. Busca en UniProtKB por `protein_name` el nombre del fármaco (Homo sapiens, reviewed
     primero; si no hay, reviewed de cualquier organismo como respaldo).
  2. Descarta entradas de receptor (`... receptor`).
  3. Prefiere el PÉPTIDO/CADENA MADURA: entre las *features* (`Peptide`/`Chain`) de la
     entrada, toma la que su descripción coincida EXACTAMENTE (normalizada) con el nombre
     del fármaco.  Así se obtiene el péptido real (p.ej. oxitocina = CYIQNCPLG de 9 aa),
     no el precursor de 125 aa.
  4. Respaldo: si ninguna feature coincide pero el nombre recomendado de la proteína
     coincide EXACTAMENTE con el fármaco y la secuencia canónica es corta (≤ 100 aa, i.e.
     realmente un péptido/proteína pequeña), usa la secuencia canónica.

La coincidencia exige igualdad EXACTA de nombre normalizado (no subcadena) para no confundir
`glucagon` con `glucagon-like peptide 1`, ni el péptido con su receptor.  Los análogos
sintéticos (insulina aspart, desmopresina, bivalirudina, abarelix…) NO tienen entrada
propia en UniProt → quedarán como "no resueltos".  Esa cobertura parcial es esperable.

Campos que añade al documento Mongo `drugs`:
    `peptide_sequence`   = str  (secuencia de aminoácidos, mayúsculas)
    `peptide_seq_source` = str  (p.ej. "UniProt:P01178 (Peptide Oxytocin 20-28)")

Idempotente: salta los documentos que ya tengan `peptide_sequence`; escribe con `$set`.

IMPORTANTE — esto SOLO consigue la secuencia para armar el FASTA.  La *predicción* de
toxicidad de ToxinPred sigue requiriendo el envío externo del FASTA a su web
(https://webs.iiitd.edu.in/raghava/toxinpred/); no existe API pública.

Uso (desde backend/, con el venv activo):
    python -m scripts.ingest.step08b_uniprot_peptide_seqs --limit 30   # prueba
    python -m scripts.ingest.step08b_uniprot_peptide_seqs              # completo
"""
from __future__ import annotations

import argparse
import re
import time

import requests

from scripts.ingest._common import log, mongo_db

UNIPROT_SEARCH = "https://rest.uniprot.org/uniprotkb/search"

# Mismos campos que step08 revisa para "ya tiene secuencia" (evitamos duplicar trabajo).
_SEQ_FIELDS = ("sequence", "peptide-sequence", "peptide_sequence", "aa_sequence")

# Umbral de longitud para el respaldo por secuencia canónica (proteína/péptido pequeño).
_CANONICAL_MAX_LEN = 100

# Rate-limit amable con la API pública de UniProt.
_SLEEP = 0.34  # ~3 req/s


def _norm(s: str) -> str:
    """Normaliza un nombre para comparación exacta: minúsculas, solo alfanumérico."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _strip_precursor(name: str) -> str:
    """Quita sufijos de precursor para poder comparar el nombre 'maduro'."""
    n = name.lower()
    for w in (" proprotein", " precursor", " prepropeptide", " prohormone", " preprohormone"):
        n = n.replace(w, "")
    return n


def _uniprot_search(name: str, human_only: bool):
    """Busca en UniProtKB por protein_name; devuelve la lista de resultados JSON."""
    query = f'(protein_name:"{name}") AND reviewed:true'
    if human_only:
        query += " AND organism_id:9606"
    try:
        r = requests.get(
            UNIPROT_SEARCH,
            params={
                "query": query,
                "fields": "accession,protein_name,length,sequence,ft_peptide,ft_chain",
                "format": "json",
                "size": 10,
            },
            headers={"Accept": "application/json"},
            timeout=20,
        )
        if r.status_code == 200:
            return r.json().get("results", [])
        log.warning("UniProt search '%s': HTTP %s", name, r.status_code)
    except Exception as exc:  # noqa: BLE001
        log.warning("UniProt search error '%s': %s", name, exc)
    return []


def _rec_name(entry: dict) -> str:
    pd = entry.get("proteinDescription", {})
    rec = pd.get("recommendedName", {})
    if rec:
        return rec.get("fullName", {}).get("value", "")
    subs = pd.get("submissionNames", [])
    if subs:
        return subs[0].get("fullName", {}).get("value", "")
    return ""


def _feature_subseq(entry: dict, full_seq: str, drug_norm: str):
    """Busca una feature Peptide/Chain cuya descripción == nombre del fármaco (normalizado).

    Devuelve (subsecuencia, descripción, tipo, begin, end) o None.
    """
    best = None
    for f in entry.get("features", []):
        ftype = f.get("type")
        if ftype not in ("Peptide", "Chain"):
            continue
        desc = f.get("description", "")
        if _norm(desc) != drug_norm:
            continue
        loc = f.get("location", {})
        b = loc.get("start", {}).get("value")
        e = loc.get("end", {}).get("value")
        if not (b and e) or b > e or e > len(full_seq):
            continue
        sub = full_seq[b - 1:e]
        cand = (sub, desc, ftype, b, e)
        # Prefiere Peptide (madura) sobre Chain si ambos coinciden.
        if best is None or (best[2] == "Chain" and ftype == "Peptide"):
            best = cand
    return best


def _resolve(name: str):
    """Intenta resolver un nombre de fármaco a (secuencia, source_str) o None."""
    drug_norm = _norm(name)
    if not drug_norm:
        return None

    results = _uniprot_search(name, human_only=True)
    if not results:
        time.sleep(_SLEEP)
        results = _uniprot_search(name, human_only=False)

    # Descarta receptores.
    entries = [e for e in results if "receptor" not in _rec_name(e).lower()]

    # 1) Feature madura (Peptide/Chain) con descripción exacta.
    for entry in entries:
        acc = entry.get("primaryAccession", "")
        full_seq = entry.get("sequence", {}).get("value", "") or ""
        if not full_seq:
            continue
        hit = _feature_subseq(entry, full_seq, drug_norm)
        if hit:
            sub, desc, ftype, b, e = hit
            src = f"UniProt:{acc} ({ftype} {desc} {b}-{e})"
            return sub.upper(), src

    # 2) Respaldo: nombre recomendado == fármaco y secuencia canónica corta.
    for entry in entries:
        acc = entry.get("primaryAccession", "")
        full_seq = entry.get("sequence", {}).get("value", "") or ""
        if not full_seq or len(full_seq) > _CANONICAL_MAX_LEN:
            continue
        rec = _rec_name(entry)
        if _norm(_strip_precursor(rec)) == drug_norm:
            return full_seq.upper(), f"UniProt:{acc} (canonical, {len(full_seq)} aa)"

    return None


def _pending_peptides(db, limit=None):
    """Fármacos peptídicos SIN ninguna secuencia (ni previa ni peptide_sequence)."""
    q = {
        "type": {"$ne": "small molecule"},
        "peptide_sequence": {"$exists": False},
        **{f: {"$exists": False} for f in _SEQ_FIELDS if f != "peptide_sequence"},
    }
    proj = {"name": 1, "type": 1, "drugbank-id": 1}
    cur = db.drugs.find(q, proj)
    if limit:
        cur = cur.limit(limit)
    return list(cur)


def run(limit: int | None = None):
    db = mongo_db()
    pend = _pending_peptides(db, limit=limit)
    log.info("Péptidos pendientes de secuencia: %d", len(pend))

    resolved = unresolved = 0
    for doc in pend:
        name = doc.get("name") or ""
        try:
            hit = _resolve(name)
        except Exception as exc:  # noqa: BLE001
            log.warning("Error resolviendo '%s': %s", name, exc)
            hit = None
        time.sleep(_SLEEP)
        if hit:
            seq, src = hit
            db.drugs.update_one(
                {"_id": doc["_id"]},
                {"$set": {"peptide_sequence": seq, "peptide_seq_source": src}},
            )
            resolved += 1
            log.info("  OK  %s | %s -> %s | %s…", doc["_id"], name, src, seq[:15])
        else:
            unresolved += 1
            log.info("  --  %s | %s (no resuelto)", doc["_id"], name)

    log.info(
        "step08b: %d resueltos con secuencia UniProt, %d no resueltos (de %d pendientes).",
        resolved, unresolved, len(pend),
    )
    return resolved


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Resuelve secuencias peptídicas desde UniProt (por nombre) y las guarda en Mongo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--limit", type=int, default=None, help="límite de péptidos a procesar (prueba)")
    args = ap.parse_args()
    run(limit=args.limit)
