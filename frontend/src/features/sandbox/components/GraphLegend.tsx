import React from 'react';

export interface LegendItem {
  color: string;
  border: string;
  label: string;
  dashed?: boolean;
}

/** Leyenda compacta para los grafos del Sandbox (nodos por color o aristas punteadas). */
export default function GraphLegend({ items }: { items: LegendItem[] }) {
  return (
    <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap', marginTop: '8px' }}>
      {items.map((it) => (
        <span key={it.label} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: '#57534e' }}>
          {it.dashed ? (
            <span style={{ width: '18px', height: 0, borderTop: `2px dashed ${it.border}` }} />
          ) : (
            <span style={{ width: '11px', height: '11px', borderRadius: '50%', background: it.color, border: `2px solid ${it.border}` }} />
          )}
          {it.label}
        </span>
      ))}
    </div>
  );
}
