/**
 * CtdSection.tsx — sección de interacciones químico-gen de CTD del Sandbox:
 * químicos que afectan al perfil de dianas + detalle por gen (acciones ↑/↓).
 */
import React from 'react';
import { CtdData } from '../../../api/sandbox';
import { th, td, miniBtn, actionColor } from './styles';

export default function CtdSection({
  ctd, onExportSummaryCsv, onExportGenesCsv, onExportJson,
}: {
  ctd: CtdData;
  onExportSummaryCsv: () => void;
  onExportGenesCsv: () => void;
  onExportJson: () => void;
}) {
  const [expanded, setExpanded] = React.useState(false);
  if (!ctd.available) {
    return (
      <div style={{ color: '#57534e', fontSize: '0.78rem', fontStyle: 'italic', marginBottom: '16px' }}>
        🧪 CTD: datos no cargados en el servidor (ejecuta <code>load_ctd_interactions.py</code>).
      </div>
    );
  }
  const summary = ctd.summary;
  if (!summary || summary.genes_with_data === 0) {
    return (
      <div style={{ color: '#57534e', fontSize: '0.78rem', fontStyle: 'italic', marginBottom: '16px' }}>
        🧪 CTD: sin interacciones químico-gen registradas para estos genes diana.
      </div>
    );
  }
  const genes = expanded ? ctd.genes : ctd.genes.slice(0, 6);
  return (
    <div style={{ marginBottom: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
        <span style={{ color: '#57534e', fontSize: '0.82rem', fontWeight: 700 }}>
          🧪 CTD — Interacciones químico-gen ({summary.genes_with_data} genes · {summary.total_interactions.toLocaleString()} interacciones)
        </span>
        <div style={{ display: 'flex', gap: '5px' }}>
          <button onClick={onExportSummaryCsv} style={miniBtn}>⬇ Químicos CSV</button>
          <button onClick={onExportGenesCsv} style={miniBtn}>⬇ Genes CSV</button>
          <button onClick={onExportJson} style={miniBtn}>⬇ JSON</button>
        </div>
      </div>
      <p style={{ color: '#57534e', fontSize: '0.73rem', margin: '0 0 8px 0' }}>
        Evidencia curada de literatura (CTD): qué químicos afectan a los genes diana y de qué forma
        (↑ aumenta / ↓ disminuye expresión o actividad). Útil para descubrir otros compuestos que afectan el mismo perfil.
      </p>

      {/* Químicos que afectan al mayor nº de genes diana */}
      <div style={{ overflowX: 'auto', marginBottom: '10px' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #d6ccbb' }}>
              <th style={th}>Químico</th>
              <th style={{ ...th, width: '90px', textAlign: 'right' }}>Genes diana</th>
              <th style={{ ...th, width: '90px', textAlign: 'right' }}>Interacciones</th>
              <th style={{ ...th, width: '120px' }}>DrugGraph</th>
            </tr>
          </thead>
          <tbody>
            {summary.top_chemicals.slice(0, expanded ? 25 : 10).map((c, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #f3ece0' }}>
                <td style={{ ...td, fontWeight: 600, color: '#292524' }}>{c.name}</td>
                <td style={{ ...td, textAlign: 'right', color: '#92400e', fontWeight: 700 }}>{c.gene_count}</td>
                <td style={{ ...td, textAlign: 'right', color: '#57534e' }}>{c.total_count}</td>
                <td style={td}>
                  {c.in_druggraph && c.drugbank_id ? (
                    <a href={`/drugs/${c.drugbank_id}`} target="_blank" rel="noreferrer"
                      style={{ color: '#15803d', textDecoration: 'none', fontSize: '0.72rem', fontWeight: 600 }}>
                      {c.drugbank_id} ↗
                    </a>
                  ) : (
                    <span style={{ color: '#57534e', fontSize: '0.7rem' }}>—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Detalle por gen */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {genes.map((g) => (
          <div key={g.gene} style={{ background: '#f3ece0', border: '1px solid #d6ccbb', borderRadius: '8px', padding: '8px 12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '6px' }}>
              <span style={{ color: '#0369a1', fontWeight: 700, fontSize: '0.82rem', fontFamily: 'monospace' }}>{g.gene}</span>
              <span style={{ color: '#78716c', fontSize: '0.72rem' }}>
                {g.chemical_count.toLocaleString()} químicos · {g.interaction_count.toLocaleString()} interacciones
              </span>
            </div>
            {/* Acciones */}
            <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginTop: '5px' }}>
              {g.actions.slice(0, 6).map((a, i) => (
                <span key={i} style={{
                  background: '#f3ece0', border: `1px solid ${actionColor(a.action)}33`,
                  color: actionColor(a.action), padding: '1px 7px', borderRadius: '4px', fontSize: '0.68rem', fontFamily: 'monospace',
                }}>
                  {a.action} ({a.count})
                </span>
              ))}
            </div>
            {/* Top químicos del gen */}
            <div style={{ color: '#78716c', fontSize: '0.7rem', marginTop: '5px' }}>
              Top químicos: {g.top_chemicals.slice(0, 5).map(c => c.name).join(', ')}
              {g.top_chemicals.length > 5 ? ` +${g.top_chemicals.length - 5}` : ''}
            </div>
          </div>
        ))}
      </div>
      {ctd.genes.length > 6 && (
        <button onClick={() => setExpanded(e => !e)} style={{ ...miniBtn, marginTop: '6px' }}>
          {expanded ? '▲ Mostrar menos' : `▼ Ver todos los genes (${ctd.genes.length})`}
        </button>
      )}
    </div>
  );
}
