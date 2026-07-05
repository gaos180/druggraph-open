"""
repurposing.py — Candidatos de reposicionamiento por similitud de red de targets.

GET /api/tools/repurposing/<drug_id>/ — ranking de fármacos por Jaccard del conjunto
de dianas moleculares, con perfil GO del fármaco consultado.
"""
import logging
import math

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.services.neo4j_service import get_driver
from config.services.gprofiler_service import run_enrichment
from ._common import _get_drug_targets, _get_drug_info

log = logging.getLogger(__name__)


def _specificity_weights(session, genes: set[str]) -> dict[str, float]:
    """Peso de especificidad por gen diana = **contenido de información / IDF**.

        w(g) = log2( (N + 1) / (n_g + 1) )

    con N = nº de fármacos con alguna diana (tamaño del "corpus") y n_g = nº de fármacos
    que tienen a g como diana ("frecuencia de documento"). Es la famosa medida de
    contenido de información IC(t) = −log p(t): compartir una diana promiscua (CYP3A4,
    atacada por cientos de fármacos) aporta poca información y pesa ~0; compartir una
    diana rara y específica pesa mucho. Es el criterio estándar en la literatura para
    ponderar features compartidas por especificidad:
      · Resnik (1995), Lin (1998), Schlicker et al. (2006) — IC en similitud semántica GO.
      · IDF log(N/df) para descontar dianas/ATC promiscuas en perfiles de fármaco
        (p.ej. Vanunu/"weighted drug-target interactome", cosine IDF-ponderado).
    (Nota: la base del log se cancela dentro del cociente del Jaccard ponderado; lo que
    cambia el ranking es la FORMA log(N/n), no la base. Suavizado +1 al estilo IDF
    probabilístico para acotar n_g = N → peso 0.)
    """
    if not genes:
        return {}
    rows = session.run(
        """
        MATCH (d:Drug)-[:TARGETS]->(t:Target)
        WHERE t.gene_name IS NOT NULL AND toUpper(t.gene_name) IN $genes
        RETURN toUpper(t.gene_name) AS gene, count(DISTINCT d) AS drugs
        """,
        genes=list(genes),
    )
    counts = {r["gene"]: r["drugs"] for r in rows}
    # N = nº de fármacos con al menos una diana (corpus). Se consulta una sola vez.
    n_total = session.run(
        "MATCH (d:Drug) WHERE (d)-[:TARGETS]->(:Target) RETURN count(d) AS n"
    ).single()["n"] or 1
    return {
        g: math.log2((n_total + 1) / (counts.get(g, 0) + 1))
        for g in genes
    }


def _weighted_jaccard(inter: set[str], union: set[str], w: dict[str, float]) -> float:
    num = sum(w.get(g, 1.0) for g in inter)
    den = sum(w.get(g, 1.0) for g in union)
    return num / den if den else 0.0


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def repurposing_view(request, drug_id: str):
    """
    GET /api/tools/repurposing/<drug_id>/

    Encuentra fármacos candidatos para reposicionamiento basándose en
    similitud de red de targets (Jaccard del conjunto de dianas moleculares).
    """
    targets_a = _get_drug_targets(drug_id)
    if not targets_a:
        return Response({'error': 'Fármaco sin targets en la red'}, status=404)

    genes_a = {t['gene_name'].upper() for t in targets_a if t['gene_name']}
    if not genes_a:
        return Response({'error': 'Fármaco sin genes de target identificados'}, status=404)

    drug_info = _get_drug_info(drug_id)

    # Obtener todos los fármacos que comparten al menos un target
    driver = get_driver()
    with driver.session() as session:
        res = session.run(
            """
            MATCH (a:Drug {drugbank_id: $drug_id})-[]->(t:Target)<-[]-(b:Drug)
            WHERE b.drugbank_id <> $drug_id
            WITH b, collect(DISTINCT coalesce(t.gene_name,'')) AS shared_genes
            RETURN
              b.drugbank_id AS drugbank_id,
              b.name        AS name,
              shared_genes
            ORDER BY size(shared_genes) DESC
            LIMIT 100
            """,
            drug_id=drug_id
        )
        candidates_raw = [dict(r) for r in res]

    # Pasada 1: reunir los genes diana de cada candidato y el universo de genes.
    prelim = []
    all_genes: set[str] = set(genes_a)
    for c in candidates_raw:
        targets_b = _get_drug_targets(c['drugbank_id'])
        genes_b   = {t['gene_name'].upper() for t in targets_b if t['gene_name']}
        if not genes_b:
            continue
        prelim.append((c, genes_b))
        all_genes |= genes_b

    # Pesos de especificidad (una sola consulta para todo el universo de genes).
    with driver.session() as session:
        weights = _specificity_weights(session, all_genes)

    # Pasada 2: Jaccard simple + Jaccard ponderado por especificidad (ranking principal).
    candidates = []
    for c, genes_b in prelim:
        intersection = genes_a & genes_b
        union        = genes_a | genes_b
        jaccard      = len(intersection) / len(union) if union else 0.0
        jaccard_w    = _weighted_jaccard(intersection, union, weights)

        if jaccard < 0.05:
            continue

        candidates.append({
            'drugbank_id':       c['drugbank_id'],
            'name':              c['name'],
            'jaccard':           round(jaccard, 4),
            'jaccard_weighted':  round(jaccard_w, 4),
            'shared_count':      len(intersection),
            'shared_genes':      sorted(intersection),
            'targets_a':         len(genes_a),
            'targets_b':         len(genes_b),
        })

    # Ordena por el Jaccard ponderado (prioriza dianas específicas sobre hubs promiscuos).
    candidates.sort(key=lambda x: (x['jaccard_weighted'], x['jaccard']), reverse=True)

    # Enriquecimiento GO de targets del fármaco A
    go_results = []
    if genes_a:
        try:
            go_results = run_enrichment(list(genes_a), sources=['GO:BP', 'KEGG'])[:20]
        except Exception as e:
            log.warning('Enriquecimiento GO falló para %s: %s', drug_id, e)

    return Response({
        'drug':       drug_info,
        'targets':    targets_a,
        'candidates': candidates[:50],
        'go_profile': go_results,
    })
