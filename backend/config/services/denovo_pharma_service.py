"""
denovo_pharma_service.py — De novo guiado por pharmacóforo (Tier 5.2).

Motor de novo propio: un algoritmo genético sobre **SELFIES** (Krenn 2020, MIT — cada cadena
decodifica siempre a un SMILES válido) cuya función de fitness combina:

  - **match al pharmacóforo objetivo**: fracción de familias de rasgo del pharmacóforo (donador/
    aceptor/aromático/hidrofóbico/ionizable) del/los activo(s) semilla que la molécula reproduce.
  - **QED** (drug-likeness) y una penalización por **SA score** (sintetizabilidad).

Es la contraparte generativa del Tier 5.1: en vez de solo describir el pharmacóforo de un fármaco,
diseña moléculas NUEVAS que lo satisfacen. Implementación 100% open (selfies + RDKit), inspirada en
el enfoque LBP-fitness + GA del pharmaco-suite de E. Cubillos, con código propio (ver NOTICE).

Se expone como `engine='pharma'` de denovo_service. 503 si faltan selfies/RDKit.
"""

import logging
import random

log = logging.getLogger(__name__)

PAPER = ("Krenn M, et al. Self-referencing embedded strings (SELFIES). "
         "Mach Learn: Sci Technol. 2020;1:045024. doi:10.1088/2632-2153/aba947")

try:
    import selfies as sf
    _ALPHABET = list(sf.get_semantic_robust_alphabet())
    SELFIES_OK = True
except Exception:
    SELFIES_OK = False
    log.info("selfies no instalado — de novo pharmaco-guiado deshabilitado.")

_RNG = random.Random(42)


def _families_2d(smiles: str) -> set:
    """Familias de rasgo pharmacofórico (2D, rápido) de un SMILES; set vacío si inválido."""
    from config.services.pharmacophore_service import _FACTORY, RDKIT_OK
    if not RDKIT_OK:
        return set()
    from rdkit import Chem
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return set()
    return {f.GetFamily() for f in _FACTORY.GetFeaturesForMol(m)}


def _target_pharmacophore(actives: list[str], min_fraction: float = 0.5) -> set:
    """Familias de consenso presentes en ≥min_fraction de los activos."""
    counts: dict = {}
    n = 0
    for smi in actives:
        fams = _families_2d(smi)
        if not fams:
            continue
        n += 1
        for fam in fams:
            counts[fam] = counts.get(fam, 0) + 1
    if n == 0:
        return set()
    return {fam for fam, c in counts.items() if c / n >= min_fraction}


def _pharma_match(smiles: str, target: set) -> float:
    if not target:
        return 0.0
    return len(_families_2d(smiles) & target) / len(target)


def _mutate(tokens: list[str]) -> list[str]:
    """Muta una lista de símbolos SELFIES (reemplazo/inserción/borrado de un símbolo)."""
    t = list(tokens)
    op = _RNG.random()
    if not t or op < 0.34:                       # reemplazo
        i = _RNG.randrange(len(t)) if t else 0
        sym = _RNG.choice(_ALPHABET)
        if t:
            t[i] = sym
        else:
            t = [sym]
    elif op < 0.67 and len(t) > 1:               # borrado
        del t[_RNG.randrange(len(t))]
    else:                                        # inserción
        t.insert(_RNG.randrange(len(t) + 1), _RNG.choice(_ALPHABET))
    return t


def _crossover(a: list[str], b: list[str]) -> list[str]:
    if not a or not b:
        return a or b
    ca, cb = _RNG.randrange(len(a) + 1), _RNG.randrange(len(b) + 1)
    return a[:ca] + b[cb:]


def generate(seed: str, actives: list[str] | None = None, n: int = 20,
             n_gen: int = 15, pop_size: int = 40, min_fraction: float = 0.5) -> dict:
    """
    GA SELFIES guiado por el pharmacóforo de `actives` (o del seed). Devuelve candidatos
    rankeados por fitness = pharma_match · QED − 0.05·SA, con estructura compatible con denovo.
    """
    from config.services.denovo_service import RDKIT_OK, PAPERS, _score_candidate, _resolve_seed
    if not SELFIES_OK:
        return {"available": False, "reason": "selfies no instalado (pip install selfies)."}
    if not RDKIT_OK:
        return {"available": False, "reason": "RDKit no disponible."}

    seed_smiles = _resolve_seed(seed)
    if actives is None:
        actives = [seed_smiles] if seed_smiles else []
    else:
        actives = [_resolve_seed(a) for a in actives if a]
    actives = [a for a in actives if a]
    if not actives:
        return {"available": False, "reason": "Seed/activos inválidos."}

    target = _target_pharmacophore(actives, min_fraction)
    if not target:
        return {"available": False, "reason": "No se pudo derivar el pharmacóforo objetivo."}

    from rdkit import Chem
    from rdkit import DataStructs
    from config.services.sandbox_service._chemistry import _MORGAN_GEN
    seed_mol = Chem.MolFromSmiles(seed_smiles) if seed_smiles else None
    seed_fp = _MORGAN_GEN.GetFingerprint(seed_mol) if seed_mol else None

    def fitness(smi: str, sc: dict) -> float:
        pm = _pharma_match(smi, target)
        qed = sc.get("qed") or 0.0
        sa = sc.get("sa_score") or 5.0
        return pm * qed - 0.05 * sa

    # población inicial: SELFIES de los activos
    pop: list[list[str]] = []
    for a in actives:
        try:
            pop.append(list(sf.split_selfies(sf.encoder(a))))
        except Exception:
            continue
    if not pop:
        return {"available": False, "reason": "No se pudo codificar ningún activo a SELFIES."}
    while len(pop) < pop_size:
        pop.append(_mutate(_RNG.choice(pop)))

    best: dict[str, dict] = {}   # smiles canónico → score dict (con fitness/pharma_match)
    for _gen in range(n_gen):
        # evaluar
        scored_pop = []
        for toks in pop:
            try:
                smi = sf.decoder("".join(toks))
            except Exception:
                continue
            mol = Chem.MolFromSmiles(smi) if smi else None
            if mol is None or mol.GetNumAtoms() < 5:
                continue
            sc = _score_candidate(smi, seed_fp)
            if sc is None:
                continue
            fit = fitness(sc["smiles"], sc)
            sc["pharma_match"] = round(_pharma_match(sc["smiles"], target), 3)
            sc["fitness"] = round(fit, 4)
            scored_pop.append((fit, toks, sc))
            prev = best.get(sc["smiles"])
            if prev is None or fit > prev["fitness"]:
                best[sc["smiles"]] = sc

        if not scored_pop:
            break
        # selección (elitismo) + reproducción (crossover + mutación)
        scored_pop.sort(key=lambda x: -x[0])
        elite = [toks for _f, toks, _sc in scored_pop[: max(2, pop_size // 4)]]
        new_pop = list(elite)
        while len(new_pop) < pop_size:
            child = _crossover(_RNG.choice(elite), _RNG.choice(elite))
            if _RNG.random() < 0.9:
                child = _mutate(child)
            new_pop.append(child)
        pop = new_pop

    # ranking final + filtro de diversidad (Tanimoto < 0.85)
    cands = sorted(best.values(), key=lambda c: -c["fitness"])
    seed_canon = Chem.MolToSmiles(seed_mol) if seed_mol else None
    selected: list[dict] = []
    fps = []
    for c in cands:
        if c["smiles"] == seed_canon:
            continue
        m = Chem.MolFromSmiles(c["smiles"])
        if m is None:
            continue
        fp = _MORGAN_GEN.GetFingerprint(m)
        if any(DataStructs.TanimotoSimilarity(fp, f) >= 0.85 for f in fps):
            continue
        fps.append(fp)
        selected.append(c)
        if len(selected) >= n:
            break

    return {
        "available": True,
        "engine": "pharma",
        "paper": f"{PAPER} · {PAPERS.get('crem','')}",
        "seed_smiles": seed_canon or seed_smiles,
        "mode": "pharmacophore-guided GA (SELFIES)",
        "target_pharmacophore": sorted(target),
        "generated": len(best),
        "candidates": selected,
        "disclaimer": "Moléculas generadas in silico por GA guiado por pharmacóforo (hipótesis); "
                      "no sintetizadas ni validadas.",
    }
