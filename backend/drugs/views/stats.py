import logging

from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from config.services.mongo import get_db
from config.services.neo4j_service import get_driver

log = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_stats_view(request):
    """GET /api/drugs/stats/public/ — conteos básicos sin autenticación (landing page)."""
    total_drugs = 0
    total_targets = 0

    try:
        total_drugs = get_db().drugs.estimated_document_count()
    except Exception:
        pass

    try:
        driver = get_driver()
        with driver.session() as session:
            row = session.run("MATCH (t:Target) RETURN count(t) AS n").single()
            if row:
                total_targets = row['n']
    except Exception:
        pass

    return JsonResponse({'total_drugs': total_drugs, 'total_targets': total_targets})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stats_view(request):
    try:
        mongo  = _mongo_stats()
        neo4j  = _neo4j_stats()
        return JsonResponse({'mongo': mongo, 'neo4j': neo4j})
    except Exception as e:
        log.error('stats_view error: %s', e, exc_info=True)
        return JsonResponse({'error': 'Error interno al obtener estadísticas'}, status=500)


def _mongo_stats() -> dict:
    db    = get_db()
    total = db.drugs.count_documents({})

    type_dist = list(db.drugs.aggregate([
        {'$group': {'_id': '$type', 'count': {'$sum': 1}}},
        {'$sort':  {'count': -1}},
    ]))

    group_dist = list(db.drugs.aggregate([
        {'$unwind': '$groups'},
        {'$group':  {'_id': '$groups', 'count': {'$sum': 1}}},
        {'$sort':   {'count': -1}},
    ]))

    # Total de registros DDI en MongoDB (drug-interactions es array por documento)
    ddi_agg = list(db.drugs.aggregate([
        {'$project': {'cnt': {'$size': {'$ifNull': ['$drug-interactions', []]}}}},
        {'$group':   {'_id': None, 'total': {'$sum': '$cnt'}}},
    ]))
    total_ddi_mentions = ddi_agg[0]['total'] if ddi_agg else 0

    return {
        'total_drugs':       total,
        'total_ddi_mentions': total_ddi_mentions,
        'by_type':  [{'label': d['_id'] or 'unknown', 'count': d['count']} for d in type_dist],
        'by_group': [{'label': d['_id'] or 'unknown', 'count': d['count']} for d in group_dist],
    }


def _neo4j_stats() -> dict:
    driver = get_driver()
    try:
        with driver.session() as session:
            # Conteos de nodos principales
            row = session.run("""
                MATCH (d:Drug)     WITH count(d) AS drugs
                MATCH (t:Target)   WITH drugs, count(t) AS targets
                OPTIONAL MATCH (c:Category) WITH drugs, targets, count(c) AS categories
                RETURN drugs, targets, categories
            """).single()

            drugs      = row['drugs']      if row else 0
            targets    = row['targets']    if row else 0
            categories = row['categories'] if row else 0

            # Distribución de tipos de relación Drug→Target
            rel_rows = session.run("""
                MATCH (:Drug)-[r]->(:Target)
                RETURN type(r) AS rel_type, count(r) AS cnt
                ORDER BY cnt DESC LIMIT 10
            """)
            rel_types = [{'label': r['rel_type'], 'count': r['cnt']} for r in rel_rows]

            # Top 5 fármacos por número de targets
            top_rows = session.run("""
                MATCH (d:Drug)-[r]->(:Target)
                RETURN d.name AS name, d.drugbank_id AS id, count(r) AS targets
                ORDER BY targets DESC LIMIT 5
            """)
            top_drugs = [
                {'name': r['name'], 'id': r['id'], 'targets': r['targets']}
                for r in top_rows
            ]

            return {
                'drugs':      drugs,
                'targets':    targets,
                'categories': categories,
                'rel_types':  rel_types,
                'top_drugs':  top_drugs,
            }
    except Exception as e:
        log.error('_neo4j_stats error: %s', e, exc_info=True)
        return {'drugs': 0, 'targets': 0, 'categories': 0, 'rel_types': [], 'top_drugs': []}
