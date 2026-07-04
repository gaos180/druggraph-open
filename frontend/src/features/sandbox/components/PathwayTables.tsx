/**
 * PathwayTables.tsx — tablas de la sección de rutas/GO del Sandbox:
 * términos funcionales (GO/Reactome/WikiPathways), rutas KEGG y vecinos PPI STRING.
 */
import React from 'react';
import { FunctionalTerm, KeggPathway, StringNeighbor } from '../../../api/sandbox';
import { th, td, miniBtn } from './styles';

export function FunctionalTable({
  title, items, termPrefix, onExportCsv, onExportJson,
}: {
  title: string;
  items: FunctionalTerm[];
  termPrefix?: string;
  /** nombre lógico (compat call-sites); no se usa internamente */
  exportName?: string;
  onExportCsv: () => void;
  onExportJson: () => void;
}) {
  const [expanded, setExpanded] = React.useState(false);
  const visible = expanded ? items : items.slice(0, 10);
  if (items.length === 0) return null;
  return (
    <div style={{ marginBottom: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
        <span style={{ color: '#57534e', fontSize: '0.82rem', fontWeight: 700 }}>{title} ({items.length})</span>
        <div style={{ display: 'flex', gap: '5px' }}>
          <button onClick={onExportCsv} style={miniBtn}>⬇ CSV</button>
          <button onClick={onExportJson} style={miniBtn}>⬇ JSON</button>
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #d6ccbb' }}>
              {termPrefix && <th style={th}>ID</th>}
              <th style={th}>Descripción</th>
              <th style={{ ...th, width: '70px', textAlign: 'right' }}>Genes</th>
              <th style={{ ...th, width: '90px' }}>Genes</th>
              <th style={{ ...th, width: '70px', textAlign: 'right' }}>FDR</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((item, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #f3ece0' }}>
                {termPrefix && <td style={{ ...td, fontFamily: 'monospace', color: '#0369a1', whiteSpace: 'nowrap' }}>{item.term}</td>}
                <td style={td}>{item.description}</td>
                <td style={{ ...td, textAlign: 'right', color: '#15803d', fontWeight: 700 }}>{item.gene_count}</td>
                <td style={{ ...td, fontSize: '0.7rem', color: '#78716c' }}>
                  {item.genes.slice(0, 5).join(', ')}{item.genes.length > 5 ? ` +${item.genes.length - 5}` : ''}
                </td>
                <td style={{ ...td, textAlign: 'right', fontFamily: 'monospace', color: '#57534e', fontSize: '0.7rem' }}>
                  {item.fdr < 0.001 ? item.fdr.toExponential(1) : item.fdr.toFixed(4)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {items.length > 10 && (
        <button onClick={() => setExpanded(e => !e)} style={{ ...miniBtn, marginTop: '6px' }}>
          {expanded ? '▲ Mostrar menos' : `▼ Ver todos (${items.length})`}
        </button>
      )}
    </div>
  );
}

export function KeggTable({
  pathways, onExportCsv, onExportJson,
}: { pathways: KeggPathway[]; onExportCsv: () => void; onExportJson: () => void }) {
  const [expanded, setExpanded] = React.useState(false);
  const visible = expanded ? pathways : pathways.slice(0, 10);
  if (pathways.length === 0) return null;
  return (
    <div style={{ marginBottom: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
        <span style={{ color: '#57534e', fontSize: '0.82rem', fontWeight: 700 }}>KEGG Pathways ({pathways.length})</span>
        <div style={{ display: 'flex', gap: '5px' }}>
          <button onClick={onExportCsv} style={miniBtn}>⬇ CSV</button>
          <button onClick={onExportJson} style={miniBtn}>⬇ JSON</button>
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #d6ccbb' }}>
              <th style={th}>ID</th>
              <th style={th}>Nombre</th>
              <th style={{ ...th, width: '70px', textAlign: 'right' }}>Targets</th>
              <th style={th}>Proteínas</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((pw, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #f3ece0' }}>
                <td style={{ ...td, fontFamily: 'monospace', color: '#0369a1', whiteSpace: 'nowrap' }}>
                  <a href={`https://www.kegg.jp/kegg-bin/show_pathway?${pw.pathway_id.replace('path:', '')}`}
                    target="_blank" rel="noreferrer" style={{ color: '#0369a1', textDecoration: 'none' }}>
                    {pw.pathway_id.replace('path:', '')}
                  </a>
                </td>
                <td style={td}>{pw.name}</td>
                <td style={{ ...td, textAlign: 'right', color: '#15803d', fontWeight: 700 }}>{pw.target_count}</td>
                <td style={{ ...td, fontSize: '0.7rem', color: '#78716c' }}>
                  {pw.targets.slice(0, 5).join(', ')}{pw.targets.length > 5 ? ` +${pw.targets.length - 5}` : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pathways.length > 10 && (
        <button onClick={() => setExpanded(e => !e)} style={{ ...miniBtn, marginTop: '6px' }}>
          {expanded ? '▲ Mostrar menos' : `▼ Ver todos (${pathways.length})`}
        </button>
      )}
    </div>
  );
}

export function PpiTable({
  neighbors, onExportCsv,
}: { neighbors: StringNeighbor[]; onExportCsv: () => void }) {
  const [expanded, setExpanded] = React.useState(false);
  const visible = expanded ? neighbors : neighbors.slice(0, 10);
  if (neighbors.length === 0) return null;
  return (
    <div style={{ marginBottom: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
        <span style={{ color: '#57534e', fontSize: '0.82rem', fontWeight: 700 }}>STRING PPI — vecinos indirectos ({neighbors.length})</span>
        <button onClick={onExportCsv} style={miniBtn}>⬇ CSV</button>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #d6ccbb' }}>
              <th style={th}>Proteína</th>
              <th style={{ ...th, width: '80px', textAlign: 'right' }}>Score</th>
              <th style={{ ...th, width: '50px', textAlign: 'right' }}>Conexiones</th>
              <th style={th}>Conectado a</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((n, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #f3ece0' }}>
                <td style={{ ...td, fontWeight: 600, color: '#292524' }}>{n.partner_protein}</td>
                <td style={{ ...td, textAlign: 'right', fontFamily: 'monospace', color: '#0284c7' }}>
                  {(n.max_score * 1000).toFixed(0)}
                </td>
                <td style={{ ...td, textAlign: 'right', color: '#15803d' }}>{n.connection_count}</td>
                <td style={{ ...td, fontSize: '0.7rem', color: '#78716c' }}>
                  {n.connected_to.slice(0, 4).join(', ')}{n.connected_to.length > 4 ? ' …' : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {neighbors.length > 10 && (
        <button onClick={() => setExpanded(e => !e)} style={{ ...miniBtn, marginTop: '6px' }}>
          {expanded ? '▲ Mostrar menos' : `▼ Ver todos (${neighbors.length})`}
        </button>
      )}
    </div>
  );
}
