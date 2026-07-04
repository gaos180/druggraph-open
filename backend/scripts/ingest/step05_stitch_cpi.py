"""ETL paso 5 — interacciones químico-proteína (CPI) de STITCH → Neo4j.

Complementa las dianas curadas de DrugCentral (`:Drug-[:TARGETS]->:Target`) con
dianas **predichas/soportadas por STITCH** para los fármacos de nuestro catálogo.

Fuente: STITCH v5.0  http://stitch.embl.de/
        9606.protein_chemical.links.detailed.v5.0.tsv.gz
        columnas: chemical  protein  experimental prediction database textmining combined_score
        - chemical → STITCH CID (`CIDm########`/`CIDs########`) = PubChem CID.
        - protein  → `9606.ENSP########` (STRING/Ensembl protein id).
        - combined_score ∈ [0, 1000].
Licencia STITCH: CC BY 4.0 (atribución).

MAPEOS
------
* fármaco: STITCH CID → PubChem CID entero → `mongo_id` vía el índice
  `external-identifiers` (resource == "PubChem CID"). Reutiliza el índice de step04.
* proteína: `9606.ENSP…` → símbolo de gen mediante el **mismo crosswalk que
  `load_string_network.py`** (fichero `9606.protein.info.v12.0.txt.gz`,
  string_protein_id → preferred_name). Con el símbolo se reengancha a un :Target
  YA existente por `gene_name` (así se reutiliza su `drugbank_target_id` = UniProt
  cuando lo tiene, sin duplicar claves de :Target).
  - Sin crosswalk (o ENSP no mapeado) el gen queda vacío: con `--create-missing`
    se materializa un :Target sintético keyed por ENSP (`drugbank_target_id =
    'STITCH-ENSP:<ensp>'`) para no perder la arista; si no, la fila se descarta.
    Prerequisito recomendado: descargar el info de STRING (ver load_string_network.py).

RELACIÓN CREADA (idempotente, MERGE):
    (:Drug)-[:STITCH_TARGET {score, source:'STITCH', ensp}]->(:Target)

USO
---
    # con crosswalk ENSP→gen (recomendado): reengancha a :Target existentes
    python -m scripts.ingest.step05_stitch_cpi \\
        --links data/raw/9606.protein_chemical.links.detailed.v5.0.tsv.gz \\
        --info  /home/gabriel/string_data/9606.protein.info.v12.0.txt.gz \\
        --min-score 700

    # sin :Target existente, materializar dianas sintéticas por ENSP
    python -m scripts.ingest.step05_stitch_cpi --links … --info … --create-missing
"""
from __future__ import annotations

import argparse
import gzip
import io

from scripts.ingest._common import log, mongo_db, neo4j_driver, chunked
from scripts.ingest.step04_ddi_open import _cid_index, _norm_cid

try:  # barra de progreso opcional
    from tqdm import tqdm
except Exception:  # pragma: no cover
    tqdm = None

DEFAULT_MIN_SCORE = 700


# ── Crosswalk ENSP → símbolo de gen ─────────────────────────────────────────────
def load_ensp2gene(info_path: str) -> dict:
    """string_protein_id → preferred_name (símbolo de gen).

    Reproduce `load_string_network.load_info`: las claves conservan el prefijo de
    taxón (`9606.ENSP…`), igual que la columna `protein` de STITCH, así el cruce es
    directo. Se importa la función real si está disponible.
    """
    try:
        from scripts.load_string_network import load_info  # reutiliza el original
        return load_info(info_path)
    except Exception:  # fallback local equivalente
        mapping = {}
        with gzip.open(info_path, "rt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("#"):
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 2:
                    mapping[parts[0]] = parts[1]
        return mapping


def _open_text(path: str):
    if path.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def _bare_ensp(protein: str) -> str:
    """`9606.ENSP00000012345` → `ENSP00000012345` (para propiedad/clave sintética)."""
    return protein.split(".", 1)[1] if "." in protein else protein


# ── Parseo del fichero STITCH ────────────────────────────────────────────────────
def parse_links(links_path, cid2drug, ensp2gene, min_score):
    """Genera filas {drug_id, gene, ensp, score} para las CPI de nuestro catálogo.

    Filtra por combined_score >= min_score y por que el químico esté en el catálogo.
    """
    fh = _open_text(links_path)
    header = fh.readline().rstrip("\n").split("\t")
    # localizar columnas por nombre; fallback posicional (chemical, protein, …, combined_score)
    try:
        c_i = header.index("chemical")
        p_i = header.index("protein")
        s_i = header.index("combined_score")
    except ValueError:
        c_i, p_i, s_i = 0, 1, len(header) - 1

    it = tqdm(fh, desc="STITCH CPI", unit=" líneas") if tqdm else fh
    seen_chem_miss = 0
    for line in it:
        parts = line.rstrip("\n").split("\t")
        if len(parts) <= max(c_i, p_i, s_i):
            continue
        try:
            score = int(parts[s_i])
        except ValueError:
            continue
        if score < min_score:
            continue
        cid = _norm_cid(parts[c_i])
        drug = cid2drug.get(cid) if cid else None
        if not drug:
            seen_chem_miss += 1
            continue
        protein = parts[p_i]
        gene = (ensp2gene.get(protein) or "").strip()
        yield {
            "drug_id": drug[0],           # = drugbank_id en Neo4j
            "gene": gene,
            "ensp": _bare_ensp(protein),
            "score": score,
        }
    fh.close()


# ── Escritura en Neo4j ───────────────────────────────────────────────────────────
_CYPHER = """
UNWIND $rows AS row
MATCH (d:Drug {drugbank_id: row.drug_id})
OPTIONAL MATCH (t:Target)
    WHERE row.gene <> '' AND t.gene_name = row.gene
WITH d, row, collect(DISTINCT t) AS existing
FOREACH (tg IN existing |
    MERGE (d)-[r:STITCH_TARGET]->(tg)
      SET r.score = row.score, r.source = 'STITCH', r.ensp = row.ensp
)
FOREACH (_ IN CASE WHEN size(existing) = 0 AND $createMissing THEN [1] ELSE [] END |
    MERGE (t2:Target {drugbank_target_id: 'STITCH-ENSP:' + row.ensp})
      SET t2.gene_name = row.gene,
          t2.name      = coalesce(t2.name, CASE WHEN row.gene <> '' THEN row.gene ELSE row.ensp END),
          t2.ensp      = row.ensp,
          t2.source    = 'STITCH'
    MERGE (d)-[r2:STITCH_TARGET]->(t2)
      SET r2.score = row.score, r2.source = 'STITCH', r2.ensp = row.ensp
)
"""


def run(links_path: str, info_path: str | None = None,
        min_score: int = DEFAULT_MIN_SCORE, create_missing: bool = False,
        batch: int = 5000):
    db = mongo_db()
    driver = neo4j_driver()

    log.info("Indexando PubChem CID → fármaco desde el catálogo…")
    cid2drug = _cid_index(db)
    log.info("  %d CIDs indexados.", len(cid2drug))
    if not cid2drug:
        log.warning("Ningún fármaco con cross-ref 'PubChem CID'; no habrá cruces. "
                    "¿Corriste step01/step02?")

    ensp2gene = {}
    if info_path:
        log.info("Cargando crosswalk ENSP→gen desde %s…", info_path)
        ensp2gene = load_ensp2gene(info_path)
        log.info("  %d proteínas mapeadas.", len(ensp2gene))
    else:
        log.warning("Sin --info: no hay crosswalk ENSP→gen. Solo se cargarán aristas "
                    "con --create-missing (dianas sintéticas por ENSP).")

    with driver.session() as s:
        s.run("CREATE CONSTRAINT target_id IF NOT EXISTS "
              "FOR (t:Target) REQUIRE t.drugbank_target_id IS UNIQUE")
        # el reenganche por gen recorre :Target por gene_name → conviene indexarlo
        s.run("CREATE INDEX target_gene IF NOT EXISTS FOR (t:Target) ON (t.gene_name)")

    written = 0
    matched_edges = 0
    rows_iter = parse_links(links_path, cid2drug, ensp2gene, min_score)
    for group in chunked(rows_iter, batch):
        # descarta filas sin gen si no se materializan dianas sintéticas
        if not create_missing:
            group = [r for r in group if r["gene"]]
        if not group:
            continue
        with driver.session() as s:
            s.run(_CYPHER, rows=group, createMissing=create_missing)
        written += len(group)
        matched_edges += sum(1 for r in group if r["gene"])
        log.info("  … %d filas CPI procesadas (%d con gen resuelto)", written, matched_edges)

    log.info("STITCH CPI cargadas: %d filas → (:Drug)-[:STITCH_TARGET]->(:Target) "
             "(score>=%d, create_missing=%s).", written, min_score, create_missing)
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Cargar CPI de STITCH (:Drug)-[:STITCH_TARGET]->(:Target).")
    ap.add_argument("--links", required=True,
                    help="9606.protein_chemical.links.detailed.v5.0.tsv.gz (o .tsv)")
    ap.add_argument("--info", default=None,
                    help="9606.protein.info.v12.0.txt.gz — crosswalk ENSP→gen (como load_string_network)")
    ap.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE,
                    help="Umbral de combined_score (0-1000, por defecto 700)")
    ap.add_argument("--create-missing", action="store_true",
                    help="Materializar :Target sintéticos por ENSP cuando no exista uno con ese gen")
    args = ap.parse_args()
    run(links_path=args.links, info_path=args.info, min_score=args.min_score,
        create_missing=args.create_missing)
