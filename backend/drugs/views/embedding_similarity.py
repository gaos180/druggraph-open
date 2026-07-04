"""
embedding_similarity.py — Similitud molecular por embedding ChemBERTa (Tier 3.2).

POST /api/drugs/sandbox/embedding-similarity/  body: { smiles, top_n? }
    → fármacos más cercanos por coseno de embeddings ChemBERTa, usando el índice
      vectorial nativo de Neo4j (drug_chemberta). Similitud aprendida, complementaria
      a Tanimoto/fingerprints.

Requiere: torch+transformers (embed) y el índice vectorial poblado con
scripts/populate_chemberta_embeddings.py. Degrada con 503 si falta el modelo.
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.services.neo4j_service import _session
from config.services import chemberta_service

log = logging.getLogger(__name__)

MAX_SMILES_LENGTH = 500


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def embedding_similarity_view(request):
    if not chemberta_service.EMBEDDINGS_OK:
        return Response(
            {"error": "Embeddings ChemBERTa no disponibles (instala torch + transformers).",
             "available": False},
            status=503,
        )

    smiles = (request.data.get("smiles") or "").strip()
    if not smiles or len(smiles) > MAX_SMILES_LENGTH:
        return Response({"error": "El campo 'smiles' es obligatorio y ≤ 500 caracteres."}, status=400)

    top_n = int(request.data.get("top_n", 20))
    top_n = max(1, min(top_n, 50))

    vec = chemberta_service.embed(smiles)
    if not vec:
        return Response({"error": "No se pudo calcular el embedding del SMILES."}, status=400)

    try:
        with _session() as session:
            rows = session.run(
                """
                CALL db.index.vector.queryNodes('drug_chemberta', $k, $vec)
                YIELD node, score
                RETURN node.drugbank_id AS drugbank_id, node.name AS name, score
                """,
                k=top_n, vec=vec,
            ).data()
    except Exception as exc:
        msg = str(exc)
        if "drug_chemberta" in msg or "no such index" in msg.lower():
            return Response(
                {"error": "Índice vectorial no poblado. Ejecuta populate_chemberta_embeddings.py.",
                 "available": False},
                status=503,
            )
        log.error("embedding_similarity_view error: %s", exc)
        return Response({"error": "Error consultando el índice vectorial."}, status=500)

    results = [{
        "drugbank_id": r["drugbank_id"],
        "name": r["name"],
        "score": round(float(r["score"]), 4),
    } for r in rows]

    return Response({"available": True, "method": "chemberta", "results": results})
