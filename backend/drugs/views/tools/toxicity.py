"""
toxicity.py — Perfil de toxicidad y off-targets de un fármaco.

GET /api/tools/toxicity/<drug_id>/ — combina alertas por anti-targets documentados
(hERG, CYPs, dopamina, etc.), off-targets predichos topológicamente (Adamic-Adar),
cluster estructural de fármacos similares y una puntuación de riesgo agregada (0-10).
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from config.services.neo4j_service import get_driver
from ._common import _get_drug_targets, _get_drug_info

log = logging.getLogger(__name__)


# Base de datos de anti-targets clínicamente relevantes.
# Cada entrada define la categoría, nivel de riesgo y mensaje explicativo.
ANTITARGETS: dict[str, dict] = {
    'KCNH2':  {'category': 'Cardiotoxicidad',           'level': 'high',
               'icon': '❤',
               'message': 'Inhibición del canal hERG (KCNH2): riesgo de prolongación del intervalo QT y arritmias ventriculares potencialmente fatales (torsades de pointes).'},
    'SCN5A':  {'category': 'Cardiotoxicidad',           'level': 'high',
               'icon': '❤',
               'message': 'Modulación del canal de sodio cardíaco SCN5A: riesgo de arritmias tipo síndrome de Brugada o ensanchamiento del QRS.'},
    'MAOA':   {'category': 'Neurológico',                'level': 'high',
               'icon': '🧠',
               'message': 'Inhibición de MAO-A (MAOA): riesgo de síndrome serotoninérgico con otros serotonérgicos y crisis hipertensivas con alimentos ricos en tiramina.'},
    'DRD2':   {'category': 'Neurológico',                'level': 'medium',
               'icon': '🧠',
               'message': 'Interacción con receptor de dopamina D2 (DRD2): riesgo de efectos extrapiramidales, discinesia tardía y síndrome neuroléptico maligno.'},
    'DRD3':   {'category': 'Neurológico',                'level': 'low',
               'icon': '🧠',
               'message': 'Interacción con receptor de dopamina D3: posibles efectos sobre el sistema de recompensa y comportamiento compulsivo.'},
    'SLC6A4': {'category': 'Neurológico',                'level': 'medium',
               'icon': '🧠',
               'message': 'Interacción con el transportador de serotonina SERT (SLC6A4): riesgo de síndrome serotoninérgico al combinarse con otros serotonérgicos.'},
    'MAOB':   {'category': 'Neurológico',                'level': 'medium',
               'icon': '🧠',
               'message': 'Inhibición de MAO-B (MAOB): riesgo de interacciones con tiramina, puede elevar la presión arterial.'},
    'HRH1':   {'category': 'CNS / Sedación',             'level': 'low',
               'icon': '🧠',
               'message': 'Bloqueo del receptor histamínico H1 (HRH1): sedación, aumento de peso, potenciación del SNC depresor.'},
    'CHRM1':  {'category': 'Anticolinérgico',            'level': 'medium',
               'icon': '🔬',
               'message': 'Antagonismo muscarínico M1 (CHRM1): deterioro cognitivo, boca seca, retención urinaria.'},
    'CHRM2':  {'category': 'Anticolinérgico / Cardíaco', 'level': 'medium',
               'icon': '❤',
               'message': 'Antagonismo muscarínico M2 (CHRM2): taquicardia refleja y efectos cardiovasculares adversos.'},
    'CHRM3':  {'category': 'Anticolinérgico',            'level': 'medium',
               'icon': '🔬',
               'message': 'Antagonismo muscarínico M3 (CHRM3): midriasis, inhibición de secreciones glandulares, estreñimiento.'},
    'PTGS1':  {'category': 'Gastrointestinal',           'level': 'medium',
               'icon': '🔬',
               'message': 'Inhibición de COX-1 (PTGS1): riesgo de úlcera gástrica, sangrado gastrointestinal y alteración de la función plaquetaria.'},
    'CYP3A4': {'category': 'Interacción farmacológica',  'level': 'medium',
               'icon': '⚗',
               'message': 'Interacción con CYP3A4 (metaboliza el ~50% de los fármacos): alto riesgo de interacciones farmacológicas clínicamente significativas.'},
    'CYP2D6': {'category': 'Interacción farmacológica',  'level': 'medium',
               'icon': '⚗',
               'message': 'Interacción con CYP2D6: variabilidad metabólica según genotipo (poor/ultrarapid metabolizer), puede requerir ajuste de dosis.'},
    'CYP2C9': {'category': 'Interacción farmacológica',  'level': 'medium',
               'icon': '⚗',
               'message': 'Interacción con CYP2C9: riesgo de interacciones con anticoagulantes (warfarina), AINEs y antidiabéticos orales.'},
    'CYP2C19':{'category': 'Interacción farmacológica',  'level': 'medium',
               'icon': '⚗',
               'message': 'Interacción con CYP2C19: variabilidad en metabolismo de IBPs y clopidogrel. Importante en polimorfismos étnicos.'},
    'CYP1A2': {'category': 'Interacción farmacológica',  'level': 'low',
               'icon': '⚗',
               'message': 'Interacción con CYP1A2: posibles interacciones con cafeína, teofilina, clozapina y antidepresivos.'},
    'CYP2B6': {'category': 'Interacción farmacológica',  'level': 'low',
               'icon': '⚗',
               'message': 'Interacción con CYP2B6: relevante para bupropion, efavirenz y ciclofosfamida.'},
    'NR1I2':  {'category': 'Interacción farmacológica',  'level': 'medium',
               'icon': '⚗',
               'message': 'Activación del receptor PXR (NR1I2): potente inductor de CYPs y transportadores, puede causar interacciones farmacológicas graves.'},
    'AR':     {'category': 'Disrupción endocrina',       'level': 'medium',
               'icon': '🔬',
               'message': 'Interacción con el receptor androgénico (AR): posible disrupción endocrina y efectos sobre el sistema reproductivo masculino.'},
    'ESR1':   {'category': 'Disrupción endocrina',       'level': 'medium',
               'icon': '🔬',
               'message': 'Interacción con el receptor de estrógeno α (ESR1): posible actividad estrogénica/antiestrogénica, relevante en tumores hormonodependientes.'},
    'ESR2':   {'category': 'Disrupción endocrina',       'level': 'low',
               'icon': '🔬',
               'message': 'Interacción con receptor de estrógeno β (ESR2): posible modulación hormonal leve.'},
    'PPARG':  {'category': 'Metabólico',                 'level': 'medium',
               'icon': '🔬',
               'message': 'Activación de PPARγ: riesgo de retención de líquidos, aumento de peso e insuficiencia cardíaca (clase thiazolidinedionas).'},
    'PPARA':  {'category': 'Metabólico',                 'level': 'low',
               'icon': '🔬',
               'message': 'Activación de PPARα: puede alterar el metabolismo lipídico y la función hepática.'},
    'ABCB1':  {'category': 'Transportador',              'level': 'low',
               'icon': '⚗',
               'message': 'Interacción con P-glicoproteína (ABCB1/MDR1): posible resistencia farmacológica o alteración de biodisponibilidad en barrera hematoencefálica.'},
    'ADRA1A': {'category': 'Cardiovascular',             'level': 'low',
               'icon': '❤',
               'message': 'Bloqueo α1-adrenérgico (ADRA1A): hipotensión ortostática y mareo.'},
    'NR3C1':  {'category': 'Disrupción endocrina',       'level': 'low',
               'icon': '🔬',
               'message': 'Interacción con el receptor glucocorticoide (GR/NR3C1): posibles efectos inmunosupresores o metabólicos no deseados.'},
}

_LEVEL_SCORE = {'high': 3, 'medium': 2, 'low': 1}
_CYPS = {'CYP3A4', 'CYP2D6', 'CYP2C9', 'CYP2C19', 'CYP1A2', 'CYP2B6'}


def _predicted_offtargets(drug_id: str, top_n: int = 30) -> list[dict]:
    """
    Off-targets predichos topológicamente con Cypher Adamic-Adar.
    No requiere GDS — usa vecinos de vecinos en el grafo Drug-Target.
    """
    cypher = """
        MATCH (d:Drug {drugbank_id: $drug_id})
        OPTIONAL MATCH (d)-[]->(ct:Target)
        WITH d, collect(DISTINCT ct) AS currentTargets

        UNWIND currentTargets AS ct
        MATCH (ct)<-[]-(bridge:Drug)-[]->(candidate:Target)
        WHERE bridge <> d AND NOT candidate IN currentTargets AND candidate.gene_name <> ''
        WITH d, candidate, bridge,
             size([(bridge)-[]->(:Target) | 1]) AS bridgeDeg
        WITH candidate,
             sum(1.0 / log(bridgeDeg + 2.718281828)) AS score,
             count(DISTINCT bridge) AS shared_via
        RETURN coalesce(candidate.drugbank_target_id, '') AS target_id,
               coalesce(candidate.name,      '')          AS target_name,
               coalesce(candidate.gene_name, '')          AS gene_name,
               coalesce(candidate.uniprot_id,'')          AS uniprot_id,
               coalesce(candidate.organism,  '')          AS organism,
               score, shared_via
        ORDER BY score DESC
        LIMIT $top_n
    """
    driver = get_driver()
    with driver.session() as session:
        rows = session.run(cypher, drug_id=drug_id, top_n=top_n).data()

    results = []
    for r in rows:
        gene = r['gene_name'].upper()
        anti = ANTITARGETS.get(gene)
        results.append({
            'target_id':   r['target_id'],
            'target_name': r['target_name'],
            'gene_name':   r['gene_name'],
            'uniprot_id':  r['uniprot_id'],
            'organism':    r['organism'],
            'score':       round(float(r['score']), 3),
            'shared_via':  r['shared_via'],
            'is_antitarget':       anti is not None,
            'antitarget_level':    anti['level']    if anti else None,
            'antitarget_category': anti['category'] if anti else None,
            'antitarget_message':  anti['message']  if anti else None,
        })
    return results


def _structural_cluster(drug_id: str, genes_a: set[str], min_jaccard: float = 0.15) -> list[dict]:
    """Cluster estructural: fármacos con Jaccard ≥ min_jaccard del conjunto de targets."""
    driver = get_driver()
    with driver.session() as session:
        res = session.run(
            """
            MATCH (a:Drug {drugbank_id: $drug_id})-[]->(t:Target)<-[]-(b:Drug)
            WHERE b.drugbank_id <> $drug_id
            WITH b, collect(DISTINCT coalesce(t.gene_name,'')) AS shared_genes
            RETURN b.drugbank_id AS drugbank_id, b.name AS name, shared_genes
            ORDER BY size(shared_genes) DESC LIMIT 50
            """,
            drug_id=drug_id
        )
        candidates_raw = res.data()

    cluster = []
    for c in candidates_raw:
        targets_b_res = get_driver().session().run(
            "MATCH (d:Drug {drugbank_id: $id})-[]->(t:Target) RETURN coalesce(t.gene_name,'') AS g",
            id=c['drugbank_id']
        ).data()
        genes_b = {r['g'].upper() for r in targets_b_res if r['g']}
        if not genes_b:
            continue
        inter = genes_a & genes_b
        union = genes_a | genes_b
        j = len(inter) / len(union) if union else 0.0
        if j >= min_jaccard:
            cluster.append({
                'drugbank_id':  c['drugbank_id'],
                'name':         c['name'],
                'jaccard':      round(j, 3),
                'shared_count': len(inter),
            })

    cluster.sort(key=lambda x: x['jaccard'], reverse=True)
    return cluster[:15]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def toxicity_view(request, drug_id: str):
    """
    GET /api/tools/toxicity/<drug_id>/

    Perfil de riesgo de toxicidad y off-targets para un fármaco.
    Combina:
      - Alertas por anti-targets documentados (hERG, CYPs, dopamina, etc.)
      - Off-targets predichos topológicamente (Adamic-Adar)
      - Cluster estructural de fármacos similares
      - Puntuación de riesgo agregada (0-10)
    """
    drug_id = drug_id.strip().upper()
    drug_info = _get_drug_info(drug_id)
    targets   = _get_drug_targets(drug_id)

    if not targets:
        return Response({'error': 'Fármaco sin targets documentados en la red'},
                        status=status.HTTP_404_NOT_FOUND)

    # ── 1. Alertas por anti-targets documentados ─────────────────────────────
    alerts = []
    cyp_interactions = []
    seen_genes = set()

    for t in targets:
        gene = t['gene_name'].upper()
        if not gene or gene in seen_genes:
            continue
        seen_genes.add(gene)

        anti = ANTITARGETS.get(gene)
        if anti:
            entry = {
                'level':       anti['level'],
                'icon':        anti['icon'],
                'category':    anti['category'],
                'gene_name':   t['gene_name'],
                'target_name': t['name'],
                'uniprot_id':  t['uniprot_id'],
                'rel_type':    t['rel_type'],
                'message':     anti['message'],
            }
            alerts.append(entry)
            if gene in _CYPS:
                cyp_interactions.append({
                    'gene':     t['gene_name'],
                    'rel_type': t['rel_type'],
                    'level':    anti['level'],
                    'note':     anti['message'],
                })

    # Ordenar: high → medium → low
    _order = {'high': 0, 'medium': 1, 'low': 2}
    alerts.sort(key=lambda a: _order[a['level']])

    # ── 2. Puntuación de riesgo (0-10) ───────────────────────────────────────
    raw_score = sum(_LEVEL_SCORE[a['level']] for a in alerts)
    risk_score = min(10, raw_score)
    if   risk_score == 0:  risk_level = 'sin_datos'
    elif risk_score <= 2:  risk_level = 'bajo'
    elif risk_score <= 5:  risk_level = 'moderado'
    elif risk_score <= 8:  risk_level = 'alto'
    else:                  risk_level = 'muy_alto'

    high_count   = sum(1 for a in alerts if a['level'] == 'high')
    medium_count = sum(1 for a in alerts if a['level'] == 'medium')
    low_count    = sum(1 for a in alerts if a['level'] == 'low')

    # ── 3. Off-targets predichos ──────────────────────────────────────────────
    predicted = []
    try:
        predicted = _predicted_offtargets(drug_id, top_n=25)
    except Exception as exc:
        log.warning("Error en predicción off-targets para %s: %s", drug_id, exc)

    # ── 4. Cluster estructural ────────────────────────────────────────────────
    genes_a = {t['gene_name'].upper() for t in targets if t['gene_name']}
    cluster = []
    try:
        cluster = _structural_cluster(drug_id, genes_a, min_jaccard=0.15)
    except Exception as exc:
        log.warning("Error en cluster estructural para %s: %s", drug_id, exc)

    return Response({
        'drug':        drug_info,
        'risk_score':  risk_score,
        'risk_level':  risk_level,
        'alert_counts': {'high': high_count, 'medium': medium_count, 'low': low_count},
        'alerts':      alerts,
        'cyp_interactions': cyp_interactions,
        'predicted_offtargets': predicted,
        'structural_cluster': cluster,
        'target_count': len(targets),
    })
