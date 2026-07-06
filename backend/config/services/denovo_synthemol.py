"""
denovo_synthemol.py — Motor generativo SyntheMol (Tier 4.4c, opcional).

SyntheMol (Swanson K, et al. Nature Machine Intelligence 2024; Stanford; MIT license) genera
moléculas de novo con **síntesis garantizada por construcción**: en lugar de mutar un seed,
recorre un espacio químico combinatorio de bloques de construcción comprables (Enamine REAL:
137 656 bloques × 70 reacciones ≈ 30·10⁹ moléculas) aplicando reacciones reales, guiado por un
predictor de bioactividad (Chemprop / RandomForest sobre features RDKit) mediante Monte Carlo
Tree Search (MCTS) o RL. Toda molécula generada es sintetizable a partir de precursores
disponibles — la ventaja frente a CReM/REINVENT4, que no garantizan una ruta de síntesis.

A diferencia de los otros motores, SyntheMol NO parte del seed: optimiza el score del predictor.
El `seed` (si se pasa) se usa como referencia para reportar similitud/novedad de los candidatos.

Dependencia OPCIONAL y pesada (`synthemol` + chemprop + torch + biblioteca de bloques + un
predictor entrenado). Si falta cualquiera, generate() devuelve available=False (→ 503), igual
que el resto de motores pesados. Ver scripts/build_synthemol_space.py para el setup.
"""

import csv
import logging
import os
import subprocess
import tempfile

log = logging.getLogger(__name__)

# Biblioteca de bloques de construcción (CSV con columnas `smiles`, `reagent_id`).
SYNTHEMOL_BUILDING_BLOCKS = os.environ.get("SYNTHEMOL_BUILDING_BLOCKS", "")
# Predictor de bioactividad que guía la búsqueda (checkpoint Chemprop o modelo sklearn).
SYNTHEMOL_SCORE_MODEL = os.environ.get("SYNTHEMOL_SCORE_MODEL", "")
# Tipo de predictor: chemprop | chemprop_rdkit | mlp_rdkit | random_forest.
SYNTHEMOL_SCORE_TYPE = os.environ.get("SYNTHEMOL_SCORE_TYPE", "chemprop")
# Espacio químico: real (Enamine) | wuxi. Reacciones opcionales (por defecto las del paquete).
SYNTHEMOL_CHEMICAL_SPACE = os.environ.get("SYNTHEMOL_CHEMICAL_SPACE", "real")
SYNTHEMOL_REACTIONS = os.environ.get("SYNTHEMOL_REACTIONS", "")
# Rollouts de la búsqueda. Bajo por defecto: este equipo tiene poca RAM (ver docs/DATASET_STATE).
SYNTHEMOL_N_ROLLOUT = int(os.environ.get("SYNTHEMOL_N_ROLLOUT", "200"))

try:
    import synthemol  # noqa: F401  (solo comprobamos disponibilidad)
    SYNTHEMOL_OK = True
except ImportError:
    SYNTHEMOL_OK = False
    log.info("synthemol no instalado — motor de novo SyntheMol deshabilitado.")


def space_ready() -> bool:
    """True si SyntheMol está instalado y existen la biblioteca de bloques y el predictor."""
    return (SYNTHEMOL_OK
            and bool(SYNTHEMOL_BUILDING_BLOCKS) and os.path.exists(SYNTHEMOL_BUILDING_BLOCKS)
            and bool(SYNTHEMOL_SCORE_MODEL) and os.path.exists(SYNTHEMOL_SCORE_MODEL))


def generate(seed: str = "", n: int = 20) -> dict:
    """
    Ejecuta una búsqueda corta de SyntheMol y devuelve los mejores candidatos, puntuados con
    el scoring compartido (QED/SA/Lipinski/similitud al seed). Degrada con available=False si
    SyntheMol, la biblioteca de bloques o el predictor no están disponibles.
    """
    from config.services.denovo_service import PAPERS, RDKIT_OK, _score_candidate

    if not space_ready():
        return {"available": False,
                "reason": "SyntheMol no disponible: instala `synthemol`, descarga la biblioteca "
                          "de bloques y entrena/define un predictor. Configura "
                          "SYNTHEMOL_BUILDING_BLOCKS y SYNTHEMOL_SCORE_MODEL "
                          "(ver scripts/build_synthemol_space.py)."}
    if not RDKIT_OK:
        return {"available": False, "reason": "RDKit no disponible."}

    seed_smiles = _resolve_seed(seed)
    seed_fp = None
    if seed_smiles:
        try:
            from rdkit import Chem
            from config.services.sandbox_service._chemistry import _MORGAN_GEN
            seed_mol = Chem.MolFromSmiles(seed_smiles)
            if seed_mol is not None:
                seed_fp = _MORGAN_GEN.GetFingerprint(seed_mol)
        except Exception as exc:
            log.debug("SyntheMol seed fp error: %s", exc)

    try:
        rows = _run_synthemol(n_candidates=n)
    except Exception as exc:
        log.error("SyntheMol run error: %s", exc)
        return {"available": False, "reason": f"Error ejecutando SyntheMol: {exc}"}

    seen: set[str] = set()
    candidates: list[dict] = []
    for smi, model_score in rows:
        sc = _score_candidate(smi, seed_fp)
        if sc is None or sc["smiles"] in seen:
            continue
        seen.add(sc["smiles"])
        if model_score is not None:
            sc["model_score"] = model_score  # score del predictor que guió la búsqueda
        candidates.append(sc)

    # Ranking por QED (consistente con los demás motores); los None al final.
    candidates.sort(key=lambda c: (c["qed"] is None, -(c["qed"] or 0)))

    return {
        "available": True,
        "engine": "synthemol",
        "paper": PAPERS["synthemol"],
        "seed_smiles": seed_smiles,
        "mode": f"combinatorial_search ({SYNTHEMOL_CHEMICAL_SPACE})",
        "generated": len(rows),
        "candidates": candidates[:n],
        "disclaimer": "Moléculas generadas in silico (hipótesis). Sintetizables por construcción "
                      "según las reacciones/bloques del espacio químico, pero NO han sido "
                      "sintetizadas ni validadas experimentalmente.",
    }


def _resolve_seed(seed: str) -> str:
    """Reutiliza la resolución de seed de denovo_service (SMILES o DrugBank ID)."""
    from config.services.denovo_service import _resolve_seed as _rs
    return _rs(seed)


def _run_synthemol(n_candidates: int) -> list[tuple[str, float | None]]:
    """
    Lanza el CLI `synthemol` en un directorio temporal y parsea el CSV de salida.

    Devuelve [(smiles, model_score|None), ...]. La firma exacta del CLI varía entre la versión
    MCTS (2024) y la RL (2026); usa las banderas documentadas y, si el binario cambió, la
    excepción se propaga y generate() degrada a 503 con el motivo.
    """
    with tempfile.TemporaryDirectory(prefix="synthemol_") as tmp:
        cmd = [
            "synthemol",
            "--save_dir", tmp,
            "--building_blocks_path", SYNTHEMOL_BUILDING_BLOCKS,
            "--score_model_paths", SYNTHEMOL_SCORE_MODEL,
            "--score_types", SYNTHEMOL_SCORE_TYPE,
            "--n_rollout", str(SYNTHEMOL_N_ROLLOUT),
            "--chemical_spaces", SYNTHEMOL_CHEMICAL_SPACE,
        ]
        if SYNTHEMOL_REACTIONS:
            cmd += ["--reaction_to_building_blocks_path", SYNTHEMOL_REACTIONS]

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "sin salida").strip()[:500])

        return _parse_output_csv(tmp, n_candidates)


def _parse_output_csv(save_dir: str, limit: int) -> list[tuple[str, float | None]]:
    """Localiza el CSV de moléculas en save_dir y extrae (smiles, score)."""
    csv_path = None
    for root, _dirs, files in os.walk(save_dir):
        for f in files:
            if f.endswith(".csv"):
                csv_path = os.path.join(root, f)
                break
        if csv_path:
            break
    if not csv_path:
        raise RuntimeError("SyntheMol no produjo CSV de salida.")

    rows: list[tuple[str, float | None]] = []
    with open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        cols = reader.fieldnames or []
        smi_col = next((c for c in cols if c.lower() in ("smiles", "smile")), None)
        score_col = next((c for c in cols if "score" in c.lower()), None)
        if not smi_col:
            raise RuntimeError(f"CSV de SyntheMol sin columna smiles (columnas: {cols}).")
        for r in reader:
            smi = (r.get(smi_col) or "").strip()
            if not smi:
                continue
            score = None
            if score_col:
                try:
                    score = round(float(r[score_col]), 4)
                except (TypeError, ValueError):
                    score = None
            rows.append((smi, score))
    # SyntheMol ya rankea por score desc; recorta a un múltiplo para dejar margen al filtrado.
    return rows[: max(limit * 3, limit)]
