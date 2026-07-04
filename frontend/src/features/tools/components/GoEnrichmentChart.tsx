import React, { useMemo, useState } from 'react';
import { GoTerm } from '../../../api/tools';

interface Props {
  terms:     GoTerm[];
  maxTerms?: number;
  width?:    number;
}

const SOURCE_COLORS: Record<string, string> = {
  'GO:BP': '#60a5fa',
  'GO:MF': '#34d399',
  'GO:CC': '#f59e0b',
  'KEGG':  '#f87171',
  'REAC':  '#a78bfa',
};

function sourceColor(src: string) {
  return SOURCE_COLORS[src] ?? '#57534e';
}

type SortKey = 'fdr' | 'size';

export default function GoEnrichmentChart({ terms, maxTerms = 20, width = 640 }: Props) {
  const [sortBy, setSortBy] = useState<SortKey>('fdr');
  const [filter, setFilter] = useState<string>('ALL');

  const sources = useMemo(() => {
    const set = new Set(terms.map(t => t.source));
    return ['ALL', ...Array.from(set).sort()];
  }, [terms]);

  const visible = useMemo(() => {
    let t = filter === 'ALL' ? terms : terms.filter(x => x.source === filter);
    if (sortBy === 'fdr')  t = [...t].sort((a, b) => a.fdr - b.fdr);
    if (sortBy === 'size') t = [...t].sort((a, b) => b.intersection_size - a.intersection_size);
    return t.slice(0, maxTerms);
  }, [terms, filter, sortBy, maxTerms]);

  if (!terms.length) {
    return (
      <div style={{ color: '#78716c', fontSize: '13px', padding: '16px 0' }}>
        Sin términos enriquecidos significativos.
      </div>
    );
  }

  const PAD_LEFT = 200;
  const PAD_RIGHT = 100;
  const ROW_H = 22;
  const BAR_H = 14;
  const height = visible.length * ROW_H + 48;
  const W = width - PAD_LEFT - PAD_RIGHT;

  const minFdr  = Math.min(...visible.map(t => t.fdr));
  const maxSize = Math.max(...visible.map(t => t.intersection_size), 1);

  const barW = (t: GoTerm) =>
    sortBy === 'fdr'
      ? Math.max(4, ((1 - Math.log10(t.fdr) / Math.log10(minFdr || 1e-300)) * W) || 4)
      : (t.intersection_size / maxSize) * W;

  return (
    <div>
      {/* Controles */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ color: '#78716c', fontSize: '12px' }}>Fuente:</span>
        {sources.map(s => (
          <button key={s} onClick={() => setFilter(s)}
            style={{
              padding: '2px 10px', borderRadius: '12px', border: 'none', cursor: 'pointer',
              fontSize: '11px', fontWeight: 500,
              background: filter === s ? (SOURCE_COLORS[s] || '#7c3aed') : '#e7dfd0',
              color: filter === s ? '#000' : '#57534e',
            }}>
            {s}
          </button>
        ))}
        <span style={{ color: '#78716c', fontSize: '12px', marginLeft: '8px' }}>Ordenar:</span>
        {(['fdr', 'size'] as SortKey[]).map(k => (
          <button key={k} onClick={() => setSortBy(k)}
            style={{
              padding: '2px 10px', borderRadius: '12px', border: 'none', cursor: 'pointer',
              fontSize: '11px',
              background: sortBy === k ? '#7c3aed' : '#e7dfd0',
              color: sortBy === k ? '#fff' : '#57534e',
            }}>
            {k === 'fdr' ? '-log₁₀(FDR)' : 'Genes overlap'}
          </button>
        ))}
      </div>

      <div style={{ overflowX: 'auto' }}>
        <svg width={width} height={height} style={{ display: 'block' }}>
          {visible.map((t, i) => {
            const y    = i * ROW_H + 8;
            const bw   = barW(t);
            const col  = sourceColor(t.source);
            const label = t.term_name.length > 28
              ? t.term_name.slice(0, 26) + '…'
              : t.term_name;

            return (
              <g key={t.term_id}>
                {/* Nombre del término */}
                <text x={PAD_LEFT - 6} y={y + BAR_H / 2 + 4}
                  textAnchor="end" fontSize={10} fill="#57534e"
                  fontFamily="monospace">
                  <title>{t.term_name} [{t.term_id}]</title>
                  {label}
                </text>

                {/* Barra */}
                <rect x={PAD_LEFT} y={y} width={bw} height={BAR_H}
                  fill={col} opacity={0.75} rx={2} />

                {/* Etiqueta de fuente */}
                <rect x={PAD_LEFT + bw + 4} y={y + 2} width={38} height={BAR_H - 4}
                  fill={col + '30'} rx={3} />
                <text x={PAD_LEFT + bw + 23} y={y + BAR_H / 2 + 4}
                  textAnchor="middle" fontSize={8} fill={col} fontFamily="monospace">
                  {t.source}
                </text>

                {/* FDR / n */}
                <text x={PAD_LEFT + bw + 48} y={y + BAR_H / 2 + 4}
                  fontSize={9} fill="#78716c" fontFamily="monospace">
                  n={t.intersection_size} | {t.fdr < 0.001 ? t.fdr.toExponential(1) : t.fdr.toFixed(3)}
                </text>
              </g>
            );
          })}

          {/* Eje X label */}
          <text x={PAD_LEFT + W / 2} y={height - 8}
            textAnchor="middle" fontSize={10} fill="#a8a29e">
            {sortBy === 'fdr' ? '-log₁₀(FDR)  →' : 'Genes en intersección  →'}
          </text>
        </svg>
      </div>
    </div>
  );
}
