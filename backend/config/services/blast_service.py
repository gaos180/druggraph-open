"""
blast_service.py — Servicio de búsqueda por homología de secuencia (BLAST).

Permite al usuario ingresar una secuencia de aminoácidos y encontrar:
  1. Targets homólogos en la base de datos DrugGraph (vía blastp).
  2. Los fármacos que afectan a esos targets (vía Neo4j).
  3. Filtrado opcional por organismo.

Caso de uso típico:
  "Tengo una proteína de S. aureus, ¿qué fármacos conocidos atacan
   proteínas homólogas a esta secuencia?"

Ubicación sugerida: config/blast_service.py

Requisitos:
  - BLAST+ instalado (blastp en el PATH).
  - Índice construido con build_blast_db.py.
  - settings.BLAST_DB_PATH y settings.BLAST_MAP_PATH configurados.
"""

import os
import json
import shutil
import logging
import subprocess
import tempfile

from django.conf import settings

from config.services.neo4j_service import _session

log = logging.getLogger(__name__)

# ── Configuración ──────────────────────────────────────────────────────────────

VALID_AA = set("ACDEFGHIKLMNPQRSTVWYBJOUXZ*")

MAX_SEQUENCE_LENGTH = 5000     # longitud máx. de secuencia de consulta
MIN_SEQUENCE_LENGTH = 10       # mínimo razonable para blastp
DEFAULT_MAX_HITS    = 50       # máx. hits devueltos por blastp
DEFAULT_EVALUE      = 1e-3     # umbral de e-value por defecto
BLAST_TIMEOUT_SEC   = 60       # timeout del subprocess

# Columnas de salida tabular (outfmt 6) que pedimos a blastp
BLAST_OUTFMT_COLS = [
    "sseqid",     # subject id = drugbank_target_id (por nuestro FASTA)
    "pident",     # % identidad
    "length",     # longitud del alineamiento
    "mismatch",
    "gapopen",
    "qstart", "qend",
    "sstart", "send",
    "evalue",
    "bitscore",
]
_OUTFMT_SPEC = "6 " + " ".join(BLAST_OUTFMT_COLS)


# ── Carga del mapa de metadata (lazy, cacheado en memoria) ──────────────────────

_target_map: dict | None = None


def _load_target_map() -> dict:
    """Carga (y cachea) el .map.json generado por build_blast_db.py."""
    global _target_map
    if _target_map is None:
        map_path = getattr(settings, "BLAST_MAP_PATH", "")
        if not map_path or not os.path.exists(map_path):
            log.warning("BLAST_MAP_PATH no configurado o inexistente: %s", map_path)
            _target_map = {}
        else:
            with open(map_path, encoding="utf-8") as f:
                _target_map = json.load(f)
    return _target_map


# ── Validación de secuencia ─────────────────────────────────────────────────────

def parse_and_validate_sequence(raw: str) -> tuple[str, str | None]:
    """
    Acepta una secuencia en texto plano o formato FASTA (con o sin cabecera >).
    Retorna (sequence_clean, error). Si error no es None, la secuencia es inválida.
    """
    if not raw or not raw.strip():
        return "", "Secuencia vacía."

    lines = raw.strip().splitlines()
    # Descartar líneas de cabecera FASTA
    seq_lines = [l for l in lines if not l.startswith(">")]
    seq = "".join(seq_lines).upper()
    seq = "".join(seq.split())  # quitar espacios internos

    if not seq:
        return "", "No se encontró secuencia (¿solo había cabecera FASTA?)."

    invalid = set(seq) - VALID_AA
    if invalid:
        return "", f"Caracteres inválidos en la secuencia: {', '.join(sorted(invalid))}"

    if len(seq) < MIN_SEQUENCE_LENGTH:
        return "", f"Secuencia demasiado corta (mín. {MIN_SEQUENCE_LENGTH} aminoácidos)."

    if len(seq) > MAX_SEQUENCE_LENGTH:
        return "", f"Secuencia demasiado larga (máx. {MAX_SEQUENCE_LENGTH} aminoácidos)."

    return seq, None


# ── Ejecución de blastp ──────────────────────────────────────────────────────────

def run_blastp(
    sequence: str,
    max_hits: int = DEFAULT_MAX_HITS,
    evalue: float = DEFAULT_EVALUE,
) -> list[dict]:
    """
    Ejecuta blastp con la secuencia dada contra el índice DrugGraph.
    Retorna lista de hits parseados (sin enriquecer todavía).

    Cada hit: { drugbank_target_id, pident, align_length, evalue, bitscore,
                qstart, qend, sstart, send }
    """
    if shutil.which("blastp") is None:
        raise RuntimeError(
            "blastp no está en el PATH. Instala BLAST+ (ncbi-blast+)."
        )

    db_path = getattr(settings, "BLAST_DB_PATH", "")
    if not db_path:
        raise RuntimeError("BLAST_DB_PATH no está configurado en settings.")
    # Verificar que exista el índice (al menos el .phr)
    if not os.path.exists(db_path + ".phr") and not os.path.exists(db_path + ".pdb"):
        raise RuntimeError(
            f"Índice BLAST no encontrado en {db_path}. "
            "Ejecuta build_blast_db.py primero."
        )

    # Escribir la query a un archivo temporal FASTA
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".fasta", delete=False, encoding="utf-8"
    ) as qf:
        qf.write(">query\n")
        qf.write(sequence + "\n")
        query_path = qf.name

    cmd = [
        "blastp",
        "-query", query_path,
        "-db", db_path,
        "-outfmt", _OUTFMT_SPEC,
        "-max_target_seqs", str(max_hits),
        "-evalue", str(evalue),
        "-num_threads", str(getattr(settings, "BLAST_THREADS", 2)),
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=BLAST_TIMEOUT_SEC
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("La búsqueda BLAST excedió el tiempo límite.")
    finally:
        try:
            os.unlink(query_path)
        except OSError:
            pass

    if result.returncode != 0:
        raise RuntimeError(f"blastp falló: {result.stderr.strip()}")

    # Parsear salida tabular
    hits = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        cols = line.split("\t")
        if len(cols) != len(BLAST_OUTFMT_COLS):
            continue
        row = dict(zip(BLAST_OUTFMT_COLS, cols))
        hits.append({
            "drugbank_target_id": row["sseqid"],
            "pident":       round(float(row["pident"]), 2),
            "align_length": int(row["length"]),
            "evalue":       float(row["evalue"]),
            "bitscore":     float(row["bitscore"]),
            "qstart":       int(row["qstart"]),
            "qend":         int(row["qend"]),
            "sstart":       int(row["sstart"]),
            "send":         int(row["send"]),
        })

    return hits


# ── Enriquecimiento con Neo4j: fármacos que afectan cada target ──────────────────

def _get_drugs_for_targets(target_ids: list[str]) -> dict[str, list[dict]]:
    """
    Para una lista de drugbank_target_id, devuelve un dict
    { target_id: [ {drugbank_id, name, rel_types, actions}, ... ] }
    con los fármacos que actúan sobre cada target.
    """
    if not target_ids:
        return {}

    cypher = """
        MATCH (d:Drug)-[r]->(t:Target)
        WHERE t.drugbank_target_id IN $target_ids
        WITH t.drugbank_target_id AS target_id,
             d.drugbank_id        AS drugbank_id,
             d.name               AS drug_name,
             collect(DISTINCT type(r)) AS rel_types,
             collect(DISTINCT r.actions) AS actions_nested
        RETURN target_id, drugbank_id, drug_name, rel_types, actions_nested
        ORDER BY drug_name
    """
    out: dict[str, list[dict]] = {}
    try:
        with _session() as session:
            for row in session.run(cypher, target_ids=target_ids).data():
                tid = row["target_id"]
                # Aplanar actions (lista de listas → set)
                actions = set()
                for a_list in (row.get("actions_nested") or []):
                    if a_list:
                        actions.update(a_list)
                out.setdefault(tid, []).append({
                    "drugbank_id": row["drugbank_id"],
                    "name":        row["drug_name"],
                    "rel_types":   row.get("rel_types") or [],
                    "actions":     sorted(actions),
                })
    except Exception as exc:
        log.error("Error obteniendo fármacos para targets: %s", exc)
    return out


# ── Pipeline completo ────────────────────────────────────────────────────────────

def blast_search(
    raw_sequence: str,
    max_hits: int = DEFAULT_MAX_HITS,
    evalue: float = DEFAULT_EVALUE,
    organism_filter: str | None = None,
    min_identity: float = 0.0,
) -> dict:
    """
    Pipeline completo de búsqueda por secuencia:
      1. Valida la secuencia de entrada.
      2. Ejecuta blastp contra el índice DrugGraph.
      3. Enriquece cada hit con metadata del target (.map.json) y los
         fármacos que lo afectan (Neo4j).
      4. Filtra opcionalmente por organismo y % identidad mínima.

    Retorna:
        {
            "query_length": int,
            "hit_count":    int,
            "hits": [
                {
                    "target": {
                        "drugbank_target_id", "uniprot_id", "name",
                        "organism", "gene_name", "ncbi_taxonomy_id"
                    },
                    "alignment": {
                        "pident", "align_length", "evalue", "bitscore",
                        "qstart", "qend", "sstart", "send"
                    },
                    "drugs": [ {drugbank_id, name, rel_types, actions} ]
                }
            ],
            "organisms": [str],   # organismos presentes en los resultados (para filtro UI)
        }

    Lanza ValueError si la secuencia es inválida.
    """
    sequence, error = parse_and_validate_sequence(raw_sequence)
    if error:
        raise ValueError(error)

    max_hits = max(1, min(max_hits, 200))

    raw_hits = run_blastp(sequence, max_hits=max_hits, evalue=evalue)

    target_map = _load_target_map()

    # Recopilar target_ids únicos para una sola consulta a Neo4j
    target_ids = list({h["drugbank_target_id"] for h in raw_hits})
    drugs_by_target = _get_drugs_for_targets(target_ids)

    hits = []
    organisms_seen = set()

    for h in raw_hits:
        tid  = h["drugbank_target_id"]
        meta = target_map.get(tid, {
            "drugbank_target_id": tid,
            "uniprot_id": "", "name": "", "organism": "",
            "gene_name": "", "ncbi_taxonomy_id": "",
        })

        organism = meta.get("organism", "")

        # Filtros
        if organism_filter and organism != organism_filter:
            continue
        if h["pident"] < min_identity:
            continue

        if organism:
            organisms_seen.add(organism)

        hits.append({
            "target": {
                "drugbank_target_id": tid,
                "uniprot_id":         meta.get("uniprot_id", ""),
                "name":               meta.get("name", ""),
                "organism":           organism,
                "gene_name":          meta.get("gene_name", ""),
                "ncbi_taxonomy_id":   meta.get("ncbi_taxonomy_id", ""),
            },
            "alignment": {
                "pident":       h["pident"],
                "align_length": h["align_length"],
                "evalue":       h["evalue"],
                "bitscore":     h["bitscore"],
                "qstart":       h["qstart"],
                "qend":         h["qend"],
                "sstart":       h["sstart"],
                "send":         h["send"],
            },
            "drugs": drugs_by_target.get(tid, []),
        })

    return {
        "query_length": len(sequence),
        "hit_count":    len(hits),
        "hits":         hits,
        "organisms":    sorted(organisms_seen),
    }
