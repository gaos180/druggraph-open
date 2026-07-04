"""
gprofiler_service.py — ORA (Over-Representation Analysis) vía g:Profiler.

API gratuita, sin clave. Documentación:
  https://biit.cs.ut.ee/gprofiler/page/apis
"""
import time
import logging
import requests

log = logging.getLogger(__name__)

GPROFILER_URL = "https://biit.cs.ut.ee/gprofiler/api/gost/profile/"
_cache: dict = {}
_CACHE_TTL  = 3600 * 6  # 6 h

VALID_SOURCES = {'GO:BP', 'GO:MF', 'GO:CC', 'KEGG', 'REAC', 'WP'}

# g:Profiler sólo acepta: 'g_SCS', 'bonferroni', 'analytical'
# fdr_bh y fdr_by no existen en su API — se mapean a g_SCS
_METHOD_MAP = {
    'fdr_bh':        'g_SCS',
    'fdr_by':        'g_SCS',
    'bonferroni':    'bonferroni',
    'g_SCS':         'g_SCS',
    'gSCS':          'g_SCS',
    'analytical':    'analytical',
}


def run_enrichment(
    gene_list: list[str],
    organism: str = 'hsapiens',
    sources: list[str] | None = None,
    user_threshold: float = 0.05,
    significance_method: str = 'fdr_bh',
) -> list[dict]:
    """
    Realiza ORA para una lista de genes.
    Devuelve lista de resultados ordenados por p_value ajustado.
    """
    if not gene_list:
        return []

    sources = [s for s in (sources or ['GO:BP', 'GO:MF', 'GO:CC', 'KEGG']) if s in VALID_SOURCES]
    cache_key = (tuple(sorted(gene_list)), organism, tuple(sorted(sources)),
                 user_threshold, significance_method)

    if cache_key in _cache:
        ts, result = _cache[cache_key]
        if time.time() - ts < _CACHE_TTL:
            return result

    api_method = _METHOD_MAP.get(significance_method, 'g_SCS')

    try:
        r = requests.post(
            GPROFILER_URL,
            json={
                'organism':                     organism,
                'query':                        list(gene_list),
                'sources':                      sources,
                'ordered':                      False,
                'all_results':                  False,
                'no_evidences':                 True,
                'combined':                     False,
                'measure_underrepresentation':  False,
                'domain_scope':                 'annotated',
                'significance_threshold_method': api_method,
                'user_threshold':               user_threshold,
            },
            timeout=30,
            headers={'Content-Type': 'application/json'},
        )
        if r.status_code == 200:
            raw = r.json().get('result', [])
            result = [
                {
                    'source':      item.get('source', ''),
                    'term_id':     item.get('native', ''),
                    'term_name':   item.get('name', ''),
                    'p_value':     item.get('p_value', 1.0),
                    'fdr':         item.get('p_value', 1.0),   # g:Profiler ya aplica el método
                    'intersection_size': item.get('intersection_size', 0),
                    'term_size':   item.get('term_size', 0),
                    'query_size':  item.get('query_size', 0),
                    'genes':       item.get('intersections', []),
                }
                for item in raw
            ]
            result.sort(key=lambda x: x['p_value'])
            _cache[cache_key] = (time.time(), result)
            return result
        log.warning("g:Profiler HTTP %s: %s", r.status_code, r.text[:200])
    except Exception as exc:
        log.error("g:Profiler error: %s", exc)

    return []
