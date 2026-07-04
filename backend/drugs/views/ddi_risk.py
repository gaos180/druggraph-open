"""
ddi_risk.py — Riesgo de interacción fármaco-fármaco PREDICHO (Tier 2.3).

Complementa el DDI documentado (lookup DrugBank) con una estimación de riesgo basada en
mecanismos, SIN modelos de ML:

  - Farmacocinético (PK): enzimas CYP450 que ambos fármacos tocan → posible competencia
    metabólica / inhibición-inducción cruzada.
  - Farmacodinámico (PD): dianas moleculares compartidas (efectos aditivos/antagónicos) y
    proximidad de sus módulos en el interactoma STRING.

    GET /api/drugs/ddi/risk/?drug_a=DB..&drug_b=DB..
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .tools._common import _get_drug_targets, _get_drug_info
from .tools.toxicity import _CYPS, ANTITARGETS

log = logging.getLogger(__name__)

HIGH_IMPACT_CYPS = {"CYP3A4", "CYP2D6", "CYP2C9", "CYP2C19"}


def _genes(drug_id: str) -> set[str]:
    return {t["gene_name"].upper() for t in _get_drug_targets(drug_id) if t.get("gene_name")}


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ddi_risk_view(request):
    drug_a = request.GET.get("drug_a", "").strip().upper()
    drug_b = request.GET.get("drug_b", "").strip().upper()
    if not drug_a or not drug_b:
        return Response({"error": "Se requieren 'drug_a' y 'drug_b'."}, status=400)
    if drug_a == drug_b:
        return Response({"error": "Indica dos fármacos distintos."}, status=400)

    genes_a, genes_b = _genes(drug_a), _genes(drug_b)
    if not genes_a or not genes_b:
        return Response({"error": "Uno de los fármacos no tiene dianas en la red."}, status=404)

    shared = genes_a & genes_b
    shared_cyps = shared & _CYPS
    shared_targets = sorted(shared - _CYPS)
    union = genes_a | genes_b
    jaccard = round(len(shared) / len(union), 4) if union else 0.0

    signals = []

    # ── PK: CYP compartido ────────────────────────────────────────────────────
    pk_score = 0
    for cyp in sorted(shared_cyps):
        high = cyp in HIGH_IMPACT_CYPS
        pk_score += 3 if high else 1
        signals.append({
            "type": "PK",
            "level": "high" if high else "medium",
            "gene": cyp,
            "message": f"Ambos fármacos interaccionan con {cyp}: posible competencia "
                       f"metabólica o inhibición/inducción cruzada"
                       + (" (CYP de alto impacto clínico)." if high else "."),
        })
    pk_score = min(6, pk_score)

    # ── PD: dianas compartidas ────────────────────────────────────────────────
    pd_score = 0
    if shared_targets:
        pd_score = min(4, len(shared_targets) * 2)
        anti = [g for g in shared_targets if g in ANTITARGETS]
        signals.append({
            "type": "PD",
            "level": "high" if anti else "medium",
            "gene": ", ".join(shared_targets[:8]),
            "message": f"Comparten {len(shared_targets)} diana(s) molecular(es): posible efecto "
                       f"farmacodinámico aditivo o antagónico"
                       + (f". Incluye anti-target(s) de riesgo: {', '.join(anti)}." if anti else "."),
        })

    # ── PD: proximidad de red (opcional, si STRING está cargada) ──────────────
    proximity = None
    try:
        from config.services.proximity_service import closest_proximity, ProximityUnavailable
        try:
            prox = closest_proximity(sorted(genes_a), sorted(genes_b))
            dc = prox.get("d_c_symmetric")
            proximity = {"d_c_symmetric": dc, "available": prox.get("available", False)}
            if dc is not None and dc <= 1.5 and not shared_targets:
                signals.append({
                    "type": "PD",
                    "level": "medium",
                    "gene": None,
                    "message": f"Los módulos de dianas están muy cerca en el interactoma "
                               f"(d_c={dc}): efectos sobre procesos relacionados.",
                })
        except ProximityUnavailable:
            proximity = {"available": False, "reason": "Red STRING no cargada."}
    except Exception as exc:
        log.debug("proximidad no disponible en ddi_risk: %s", exc)

    risk_score = min(10, pk_score + pd_score)
    if   risk_score == 0: risk_level = "sin_señales"
    elif risk_score <= 3: risk_level = "bajo"
    elif risk_score <= 6: risk_level = "moderado"
    else:                 risk_level = "alto"

    return Response({
        "drug_a": _get_drug_info(drug_a),
        "drug_b": _get_drug_info(drug_b),
        "risk_score": risk_score,
        "risk_level": risk_level,
        "shared_cyps": sorted(shared_cyps),
        "shared_targets": shared_targets,
        "jaccard": jaccard,
        "proximity": proximity,
        "signals": signals,
        "disclaimer": "Estimación mecanística in-silico (PK/PD); no sustituye una base de "
                      "datos clínica de interacciones ni criterio farmacológico.",
    })
