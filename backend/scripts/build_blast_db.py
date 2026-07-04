#!/usr/bin/env python3
"""
build_blast_db.py — Construye una base de datos BLAST de proteínas a partir
del NDJSON de targets generado por targets_to_json.py.

Uso:
    python3 build_blast_db.py targets.ndjson ./blast_db/druggraph_targets

Genera:
    ./blast_db/druggraph_targets.fasta   — FASTA de todas las secuencias
    ./blast_db/druggraph_targets.p*      — índice BLAST (phr, pin, psq, ...)
    ./blast_db/druggraph_targets.map.json — mapa id_fasta → metadata del target

REQUISITO: BLAST+ instalado (makeblastdb en el PATH).
    - Ubuntu/Debian:  sudo apt install ncbi-blast+
    - Conda:          conda install -c bioconda blast
    - macOS:          brew install blast

El header de cada secuencia FASTA codifica el drugbank_target_id como ID:
    >BE0000048 P00734|Prothrombin|Humans
de modo que blastp (outfmt 6) devuelve el drugbank_target_id en la columna
'sseqid', listo para mapear a Neo4j sin lookups adicionales.

NOTA sobre el formato BLAST: los IDs no pueden contener espacios. Usamos el
drugbank_target_id (BE0000048) como sseqid, y el resto de metadata va en la
descripción (después del primer espacio) y también en el .map.json para
recuperación robusta.
"""

import sys
import os
import json
import subprocess
import shutil
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Caracteres válidos en una secuencia de aminoácidos (incluye ambiguos y stop)
VALID_AA = set("ACDEFGHIKLMNPQRSTVWYBJOUXZ*")


def _clean_sequence(seq: str) -> str:
    """Limpia una secuencia: mayúsculas, sin espacios ni saltos, solo AA válidos."""
    if not seq:
        return ""
    seq = "".join(seq.split()).upper()
    return "".join(c for c in seq if c in VALID_AA)


def build_fasta(ndjson_path: str, fasta_path: str) -> dict:
    """
    Lee el NDJSON de targets y escribe un FASTA con todas las secuencias de
    aminoácidos. Retorna el mapa { drugbank_target_id: metadata }.

    Si dos targets comparten drugbank_target_id (no debería pasar tras la
    deduplicación), se conserva el primero y se registra una advertencia.
    """
    id_map: dict[str, dict] = {}
    written = 0
    skipped_no_seq = 0
    skipped_dup = 0

    os.makedirs(os.path.dirname(fasta_path) or ".", exist_ok=True)

    with open(ndjson_path, encoding="utf-8") as f_in, \
         open(fasta_path, "w", encoding="utf-8") as f_out:

        for line in f_in:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)

            poly = rec.get("polypeptide", {}) or {}
            seq = _clean_sequence(poly.get("amino_acid_sequence", ""))
            if not seq:
                skipped_no_seq += 1
                continue

            # ID para BLAST: drugbank_target_id (sin espacios garantizado)
            db_tid = rec.get("drugbank_target_id", "") or rec.get("id", "")
            if not db_tid:
                skipped_no_seq += 1
                continue

            if db_tid in id_map:
                skipped_dup += 1
                continue

            uniprot_id = rec.get("uniprot_id", "") or ""
            name       = poly.get("name", "") or rec.get("drugbank", {}).get("name", "")
            organism   = poly.get("organism", "") or rec.get("drugbank", {}).get("organism", "")
            ncbi_tax   = poly.get("ncbi_taxonomy_id", "") or ""
            gene_name  = poly.get("gene_name", "") or ""

            # Descripción FASTA: campos separados por | (sin saltos de línea)
            # Formato: >drugbank_target_id uniprot|name|organism
            safe_name = name.replace("|", "/").replace("\n", " ")
            safe_org  = organism.replace("|", "/").replace("\n", " ")
            desc = f"{uniprot_id}|{safe_name}|{safe_org}"

            f_out.write(f">{db_tid} {desc}\n")
            # Escribir secuencia en líneas de 60 caracteres (convención FASTA)
            for i in range(0, len(seq), 60):
                f_out.write(seq[i:i + 60] + "\n")

            id_map[db_tid] = {
                "drugbank_target_id": db_tid,
                "uniprot_id":         uniprot_id,
                "name":               name,
                "organism":           organism,
                "ncbi_taxonomy_id":   ncbi_tax,
                "gene_name":          gene_name,
                "sequence_length":    len(seq),
            }
            written += 1

    log.info(f"  Secuencias escritas:        {written:,}")
    log.info(f"  Saltadas (sin secuencia):   {skipped_no_seq:,}")
    log.info(f"  Saltadas (id duplicado):    {skipped_dup:,}")
    return id_map


def run_makeblastdb(fasta_path: str, db_prefix: str, title: str = "DrugGraph Targets"):
    """Ejecuta makeblastdb sobre el FASTA generado."""
    if shutil.which("makeblastdb") is None:
        raise RuntimeError(
            "makeblastdb no está en el PATH. Instala BLAST+:\n"
            "  Ubuntu/Debian:  sudo apt install ncbi-blast+\n"
            "  Conda:          conda install -c bioconda blast\n"
            "  macOS:          brew install blast"
        )

    cmd = [
        "makeblastdb",
        "-in", fasta_path,
        "-dbtype", "prot",
        "-out", db_prefix,
        "-title", title,
        "-parse_seqids",   # permite recuperar secuencias por ID con blastdbcmd
    ]
    log.info(f"  Ejecutando: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"makeblastdb falló:\n{result.stderr}")
    log.info("  ✓ Índice BLAST creado correctamente.")
    if result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            log.info(f"    {line}")


def main():
    if len(sys.argv) < 3:
        print("Uso: python3 build_blast_db.py targets.ndjson ./blast_db/druggraph_targets")
        sys.exit(1)

    ndjson_path = sys.argv[1]
    db_prefix   = sys.argv[2]
    fasta_path  = db_prefix + ".fasta"
    map_path    = db_prefix + ".map.json"

    if not os.path.exists(ndjson_path):
        log.error(f"No existe el archivo: {ndjson_path}")
        sys.exit(1)

    log.info(f"Construyendo FASTA desde {ndjson_path}...")
    id_map = build_fasta(ndjson_path, fasta_path)

    if not id_map:
        log.error("No se escribió ninguna secuencia. ¿El NDJSON tiene amino_acid_sequence?")
        sys.exit(1)

    log.info("Construyendo índice BLAST con makeblastdb...")
    run_makeblastdb(fasta_path, db_prefix)

    # Guardar el mapa de metadata
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(id_map, f, ensure_ascii=False)
    log.info(f"  ✓ Mapa de metadata: {map_path} ({len(id_map):,} targets)")

    log.info("")
    log.info("Listo. Configura en Django settings.py:")
    log.info(f'  BLAST_DB_PATH = "{os.path.abspath(db_prefix)}"')
    log.info(f'  BLAST_MAP_PATH = "{os.path.abspath(map_path)}"')


if __name__ == "__main__":
    main()
