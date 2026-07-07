"""
homology_service.py — Homología de dianas entre especies (Tier 6, uso veterinario).

Las dianas del grafo son humanas. Para saber si un fármaco podría funcionar en OTRAS especies (uso
veterinario), este servicio busca los ORTÓLOGOS de las dianas del fármaco en las especies elegidas
(UniProt por gen + organismo) y mide la **% de identidad de secuencia** (alineamiento global
BLOSUM62 con Biopython). Alta conservación de la diana ⇒ es más probable que el fármaco funcione en
esa especie (el sitio de unión suele estar conservado).

Deps: `requests` + `biopython`. Degrada con available=False si biopython falta.
"""
import logging

log = logging.getLogger(__name__)

# Especies frecuentes (veterinaria + modelos), con su NCBI organism_id.
SPECIES = [
    {"organism_id": 9615, "name": "Perro", "sci": "Canis lupus familiaris"},
    {"organism_id": 9685, "name": "Gato", "sci": "Felis catus"},
    {"organism_id": 9796, "name": "Caballo", "sci": "Equus caballus"},
    {"organism_id": 9913, "name": "Vaca", "sci": "Bos taurus"},
    {"organism_id": 9823, "name": "Cerdo", "sci": "Sus scrofa"},
    {"organism_id": 9940, "name": "Oveja", "sci": "Ovis aries"},
    {"organism_id": 9986, "name": "Conejo", "sci": "Oryctolagus cuniculus"},
    {"organism_id": 9031, "name": "Pollo", "sci": "Gallus gallus"},
    {"organism_id": 10090, "name": "Ratón", "sci": "Mus musculus"},
    {"organism_id": 10116, "name": "Rata", "sci": "Rattus norvegicus"},
    {"organism_id": 7955, "name": "Pez cebra", "sci": "Danio rerio"},
]
_SPECIES_BY_ID = {s["organism_id"]: s for s in SPECIES}

# Umbrales de identidad → probabilidad de que la diana esté conservada (y el fármaco funcione).
HIGH, MEDIUM = 70.0, 40.0

try:
    from Bio.Align import PairwiseAligner, substitution_matrices
    _ALIGNER = PairwiseAligner()
    _ALIGNER.mode = "global"
    _ALIGNER.open_gap_score = -10
    _ALIGNER.extend_gap_score = -0.5
    _ALIGNER.substitution_matrix = substitution_matrices.load("BLOSUM62")
    BIO_OK = True
except Exception:
    BIO_OK = False
    log.info("biopython no disponible — homología cross-especies deshabilitada.")

_SEQ_CACHE: dict = {}


def _uniprot_seq(gene: str, organism_id: int) -> tuple[str, str] | None:
    """(accession, secuencia) del ortólogo por gen+organismo (reviewed primero, luego sin revisar)."""
    key = (gene.upper(), organism_id)
    if key in _SEQ_CACHE:
        return _SEQ_CACHE[key]
    import requests
    for rev in (" AND reviewed:true", ""):
        try:
            r = requests.get("https://rest.uniprot.org/uniprotkb/search",
                             params={"query": f"gene:{gene} AND organism_id:{organism_id}{rev}",
                                     "fields": "accession,sequence", "format": "json", "size": 1},
                             timeout=45).json().get("results", [])
            if r:
                val = (r[0]["primaryAccession"], r[0]["sequence"]["value"])
                _SEQ_CACHE[key] = val
                return val
        except Exception as exc:
            log.debug("uniprot %s/%s error: %s", gene, organism_id, exc)
    _SEQ_CACHE[key] = None
    return None


def _identity(a: str, b: str) -> float:
    aln = _ALIGNER.align(a, b)[0]
    s1, s2 = str(aln[0]), str(aln[1])
    ident = sum(1 for x, y in zip(s1, s2) if x == y and x != "-")
    return round(100.0 * ident / max(len(a), len(b)), 1)


def _verdict(identity: float | None) -> str:
    if identity is None:
        return "sin ortólogo"
    if identity >= HIGH:
        return "conservada"
    if identity >= MEDIUM:
        return "parcial"
    return "divergente"


def conservation(genes: list[str], species_ids: list[int]) -> dict:
    """
    Para cada gen (diana humana) y especie elegida, calcula la % de identidad del ortólogo.
    Devuelve la tabla por diana + un resumen por especie (media de identidad + veredicto).
    """
    if not BIO_OK:
        return {"available": False, "reason": "biopython no disponible."}
    species = [_SPECIES_BY_ID[i] for i in species_ids if i in _SPECIES_BY_ID] or SPECIES[:4]
    genes = [g for g in dict.fromkeys(g.upper() for g in genes if g)][:8]
    if not genes:
        return {"available": False, "reason": "Sin dianas con gen para comparar."}

    targets = []
    for g in genes:
        human = _uniprot_seq(g, 9606)
        row = {"gene": g, "human_uniprot": human[0] if human else None, "by_species": {}}
        for sp in species:
            if not human:
                row["by_species"][sp["organism_id"]] = {"found": False, "identity": None, "verdict": "sin humano"}
                continue
            orth = _uniprot_seq(g, sp["organism_id"])
            if not orth:
                row["by_species"][sp["organism_id"]] = {"found": False, "identity": None, "verdict": "sin ortólogo"}
                continue
            ident = _identity(human[1], orth[1])
            row["by_species"][sp["organism_id"]] = {"found": True, "ortholog": orth[0],
                                                    "identity": ident, "verdict": _verdict(ident)}
        targets.append(row)

    summary = []
    for sp in species:
        vals = [t["by_species"][sp["organism_id"]]["identity"] for t in targets
                if t["by_species"][sp["organism_id"]]["identity"] is not None]
        mean = round(sum(vals) / len(vals), 1) if vals else None
        n_cons = sum(1 for v in vals if v >= HIGH)
        summary.append({"organism_id": sp["organism_id"], "name": sp["name"], "sci": sp["sci"],
                        "mean_identity": mean, "n_conserved": n_cons, "n_targets": len(genes),
                        "likely_works": bool(mean is not None and mean >= HIGH),
                        "verdict": _verdict(mean)})

    return {"available": True, "species": species, "genes": genes,
            "targets": targets, "summary": summary,
            "note": "Identidad de secuencia como proxy de conservación de la diana; ≥70% ⇒ probable "
                    "que el fármaco funcione (uso veterinario). No sustituye validación experimental."}


def homology_for_drug(drug_id: str, species_ids: list[int]) -> dict:
    """Homología de las dianas documentadas de un fármaco del catálogo, en las especies elegidas."""
    genes = []
    try:
        from config.services.neo4j_service import _session
        with _session() as s:
            genes = [r["g"] for r in s.run(
                "MATCH (d:Drug {drugbank_id:$id})-[:TARGETS]->(t:Target) "
                "WHERE t.gene_name IS NOT NULL RETURN DISTINCT t.gene_name AS g LIMIT 8",
                id=(drug_id or "").strip().upper()).data()]
    except Exception as exc:
        log.debug("homology_for_drug targets error: %s", exc)
    if not genes:
        return {"available": False, "reason": f"'{drug_id}' sin dianas con gen en el grafo."}
    res = conservation(genes, species_ids)
    res["drug_id"] = drug_id
    return res
