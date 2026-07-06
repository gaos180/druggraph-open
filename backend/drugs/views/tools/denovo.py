"""
denovo.py — Diseño molecular de novo (Tier 4.4).

POST /api/tools/denovo/
    body: { seed: <SMILES|DrugBank ID>, mode?: 'grow'|'mutate'|'link',
            engine?: 'crem'|'synthemol'|'reinvent', n?: int }
    → candidatos generados + QED/SA/similitud + disclaimer in-silico + cita del paper.

Requiere el motor correspondiente (CReM + base de fragmentos, SyntheMol + bloques/predictor, o
REINVENT4). Degrada con 503 si el motor/deps no están disponibles. Nota: SyntheMol ignora `mode`
(no parte del seed; hace búsqueda combinatoria optimizando un predictor de bioactividad).
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.services import denovo_service

log = logging.getLogger(__name__)

MAX_SEED_LENGTH = 500
VALID_MODES = ("grow", "mutate", "link")
VALID_ENGINES = ("crem", "synthemol", "reinvent", "pharma")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def denovo_view(request):
    seed = (request.data.get("seed") or "").strip()
    if not seed or len(seed) > MAX_SEED_LENGTH:
        return Response({"error": "El campo 'seed' (SMILES o DrugBank ID) es obligatorio y ≤ 500 caracteres."},
                        status=400)

    mode = (request.data.get("mode") or "mutate").lower()
    engine = (request.data.get("engine") or "crem").lower()
    if mode not in VALID_MODES:
        return Response({"error": f"mode debe ser uno de {VALID_MODES}."}, status=400)
    if engine not in VALID_ENGINES:
        return Response({"error": f"engine debe ser uno de {VALID_ENGINES}."}, status=400)

    try:
        n = int(request.data.get("n", 20))
    except (TypeError, ValueError):
        n = 20

    try:
        result = denovo_service.generate(seed=seed, mode=mode, engine=engine, n=n)
    except Exception as exc:
        log.error("denovo_view error: %s", exc)
        return Response({"error": "Error generando moléculas de novo."}, status=500)

    if not result.get("available"):
        return Response(result, status=503)
    return Response(result)
