"""
deg.py — Análisis de Expresión Diferencial (DEG).

POST /api/tools/deg-analysis/ — clasifica genes (up/down/significativo), cruza con
los targets del fármaco y corre enriquecimiento GO (g:Profiler) de la intersección.
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from config.services.gprofiler_service import run_enrichment
from ._common import _get_drug_targets, _get_drug_info

log = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deg_analysis_view(request):
    """
    POST /api/tools/deg-analysis/

    Body:
      drug_id         — DrugBank ID (e.g. DB00001)
      genes           — lista de objetos {symbol, log2fc?, pvalue?, padj?}
      fc_threshold    — corte log2FC absoluto (default 1.0 = 2x)
      pval_threshold  — corte de significancia (default 0.05)
      use_fdr         — true → usa padj; false → usa pvalue
      organism        — e.g. 'hsapiens', 'mmusculus', 'rnorvegicus'
      go_sources      — lista de fuentes GO (default ['GO:BP','GO:MF','GO:CC','KEGG'])
      significance_method — 'fdr_bh' | 'bonferroni' | 'g_SCS'
    """
    data = request.data

    drug_id   = data.get('drug_id', '').strip()
    genes_raw = data.get('genes', [])
    fc_thr    = float(data.get('fc_threshold',  1.0))
    pval_thr  = float(data.get('pval_threshold', 0.05))
    use_fdr   = bool(data.get('use_fdr', False))
    organism  = data.get('organism', 'hsapiens')
    go_sources = data.get('go_sources', ['GO:BP', 'GO:MF', 'GO:CC', 'KEGG'])
    sig_method = data.get('significance_method', 'fdr_bh')

    if not drug_id:
        return Response({'error': 'drug_id requerido'}, status=status.HTTP_400_BAD_REQUEST)
    if not genes_raw:
        return Response({'error': 'genes requeridos'}, status=status.HTTP_400_BAD_REQUEST)

    # ── 1. Obtener info del fármaco y sus targets ────────────────────────────
    drug_info = _get_drug_info(drug_id)
    targets   = _get_drug_targets(drug_id)

    # Índice de targets por gene_name (case-insensitive)
    target_by_gene: dict[str, dict] = {}
    for t in targets:
        if t['gene_name']:
            target_by_gene[t['gene_name'].upper()] = t
        # También por nombre de proteína
        if t['name']:
            target_by_gene[t['name'].upper()] = t

    # ── 2. Clasificar genes ──────────────────────────────────────────────────
    has_quantitative = any('log2fc' in g or 'pvalue' in g or 'padj' in g for g in genes_raw)

    processed = []
    for g in genes_raw:
        symbol  = str(g.get('symbol', '')).strip()
        if not symbol:
            continue
        log2fc  = float(g.get('log2fc', 0.0))
        pvalue  = float(g.get('pvalue', 1.0))
        padj    = float(g.get('padj',   1.0)) if 'padj' in g else pvalue

        stat_val = padj if use_fdr else pvalue
        is_sig   = (stat_val <= pval_thr and abs(log2fc) >= fc_thr) if has_quantitative else True
        direction = 'up' if log2fc > 0 else ('down' if log2fc < 0 else 'none')

        is_target = symbol.upper() in target_by_gene
        target_info = target_by_gene.get(symbol.upper())

        processed.append({
            'symbol':    symbol,
            'log2fc':    log2fc,
            'pvalue':    pvalue,
            'padj':      padj,
            'sig_value': stat_val,
            'is_sig':    is_sig,
            'direction': direction,
            'is_target': is_target,
            'target_id':   target_info['target_id']   if target_info else '',
            'gene_name':   target_info['gene_name']   if target_info else '',
            'uniprot_id':  target_info['uniprot_id']  if target_info else '',
            'rel_type':    target_info['rel_type']     if target_info else '',
        })

    # ── 3. Estadísticas ──────────────────────────────────────────────────────
    sig_genes   = [g for g in processed if g['is_sig']]
    up_genes    = [g for g in sig_genes if g['direction'] == 'up']
    down_genes  = [g for g in sig_genes if g['direction'] == 'down']
    overlap     = [g for g in sig_genes if g['is_target']]
    overlap_up  = [g for g in overlap  if g['direction'] == 'up']
    overlap_down= [g for g in overlap  if g['direction'] == 'down']

    stats = {
        'total_input':   len(processed),
        'significant':   len(sig_genes),
        'up':            len(up_genes),
        'down':          len(down_genes),
        'drug_targets':  len(targets),
        'overlap':       len(overlap),
        'overlap_up':    len(overlap_up),
        'overlap_down':  len(overlap_down),
        'has_quantitative': has_quantitative,
    }

    # ── 4. GO Enrichment para genes de la intersección ──────────────────────
    go_results = []
    enrichment_genes = [g['symbol'] for g in overlap]
    notes = []
    if len(enrichment_genes) < 3 and sig_genes:
        # ORA no es significativo con menos de 3 genes; enriquecer todos los DEGs
        enrichment_genes = [g['symbol'] for g in sig_genes[:500]]

    if enrichment_genes:
        try:
            go_results = run_enrichment(
                enrichment_genes,
                organism=organism,
                sources=go_sources,
                user_threshold=0.05,
                significance_method=sig_method,
            )
        except Exception as exc:
            log.error("g:Profiler error in deg_analysis: %s", exc)
            notes.append(f'No se pudo obtener enriquecimiento GO: {exc}')

    if len(overlap) < 3:
        if not overlap:
            notes.append('No se encontró intersección directa entre DEGs y targets del fármaco. '
                         'El enriquecimiento GO se calculó para todos los DEGs significativos.')
        else:
            notes.append(f'Solo {len(overlap)} gen(es) en la intersección (mínimo 3 para ORA robusto). '
                         'El enriquecimiento GO se calculó para todos los DEGs significativos.')

    return Response({
        'drug':         drug_info,
        'stats':        stats,
        'genes':        processed,
        'drug_targets': targets,
        'overlap':      overlap,
        'go_enrichment': go_results,
        'notes':        notes,
    })
