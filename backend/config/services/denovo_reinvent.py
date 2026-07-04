"""
denovo_reinvent.py — Motor generativo REINVENT4 (Tier 4.4b, opcional).

REINVENT4 (Loeffler HH, et al. J. Cheminformatics 2024; AstraZeneca; Apache-2.0) es un
framework de diseño molecular generativo con un prior RNN preentrenado en ChEMBL. Aquí se
usa para muestrear moléculas de novo desde ese prior; el scoring/filtrado drug-like lo
aplica denovo_service (compartido con CReM).

Dependencia OPCIONAL y pesada (`reinvent` + torch + pesos del prior). Si no está instalada
o no se configura la ruta al prior (env REINVENT_PRIOR_PATH), REINVENT_OK/prior_ready() es
False y generate() devuelve available=False (→ 503), igual que el resto de motores pesados.
"""

import logging
import os

log = logging.getLogger(__name__)

REINVENT_PRIOR_PATH = os.environ.get("REINVENT_PRIOR_PATH", "")

try:
    import reinvent  # noqa: F401  (solo comprobamos disponibilidad)
    REINVENT_OK = True
except ImportError:
    REINVENT_OK = False
    log.info("reinvent no instalado — motor de novo REINVENT4 deshabilitado.")


def prior_ready() -> bool:
    return REINVENT_OK and bool(REINVENT_PRIOR_PATH) and os.path.exists(REINVENT_PRIOR_PATH)


def generate(seed: str = "", n: int = 20) -> dict:
    """
    Muestrea `n` moléculas del prior REINVENT4 y las puntúa con el scoring compartido.
    Degrada con available=False si REINVENT4 o su prior no están disponibles.
    """
    from config.services.denovo_service import PAPERS, RDKIT_OK, _score_candidate

    if not prior_ready():
        return {"available": False,
                "reason": "REINVENT4 no disponible: instala `reinvent` y define "
                          "REINVENT_PRIOR_PATH (requirements-ml.txt)."}
    if not RDKIT_OK:
        return {"available": False, "reason": "RDKit no disponible."}

    try:
        smiles_list = _sample_prior(n)
    except Exception as exc:
        log.error("REINVENT sample error: %s", exc)
        return {"available": False, "reason": f"Error muestreando REINVENT4: {exc}"}

    seen: set[str] = set()
    candidates: list[dict] = []
    for smi in smiles_list:
        sc = _score_candidate(smi, None)
        if sc is None or sc["smiles"] in seen:
            continue
        seen.add(sc["smiles"])
        candidates.append(sc)
    candidates.sort(key=lambda c: (c["qed"] is None, -(c["qed"] or 0)))

    return {
        "available": True,
        "engine": "reinvent",
        "paper": PAPERS["reinvent"],
        "seed_smiles": seed,
        "mode": "sample_prior",
        "generated": len(smiles_list),
        "candidates": candidates[:n],
        "disclaimer": "Moléculas generadas in silico (hipótesis). No han sido sintetizadas "
                      "ni validadas experimentalmente.",
    }


def _sample_prior(n: int) -> list[str]:
    """
    Muestrea SMILES del prior de REINVENT4. La API concreta depende de la versión
    instalada de `reinvent`; se implementa cuando el paquete esté presente en el entorno.
    """
    raise NotImplementedError(
        "Muestreo de REINVENT4 pendiente de cablear a la API del paquete `reinvent` instalado."
    )
