import React from 'react';
import type { DrugRecord } from '../../../types/drug';

export default function TargetsSection({ drug }: { drug: DrugRecord }) {
  if (!drug) return null;

  return (
    <>
      <div className="detail-section">
        <label>Dianas Farmacológicas (Targets)</label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '6px' }}>
          {Array.isArray(drug.targets) && drug.targets.map((t: any, i: number) => (
            <div key={i} style={{ background: '#f3ece0', padding: '12px', borderRadius: '6px', borderLeft: '4px solid #6366f1' }}>
              <h4>{t.name} ({t.organism})</h4>
              <p style={{ margin: 0, fontSize: '0.85rem' }}><strong>Acción:</strong> {Array.isArray(t.actions) ? t.actions.join(', ') : 'Ligando'} | ID: {t.id}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="detail-section">
        <label>Complejos Enzimáticos de Biotransformación (Enzymes)</label>
        {drug.reactions && Array.isArray(drug.reactions) ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '6px' }}>
            {drug.reactions.flat(2).map((reac: any, i: number) => {
              if (!reac || !reac.enzymes) return null;
              return reac.enzymes.map((enz: any, j: number) => (
                <div key={`${i}-${j}`} style={{ background: '#f3ece0', padding: '10px 14px', borderRadius: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <strong style={{ color: '#1c1917' }}>{enz.name}</strong>
                    <p style={{ margin: '2px 0 0 0', fontSize: '0.8rem', color: '#57534e' }}>ID Catálogo: {enz['drugbank-id']}</p>
                  </div>
                  <a href={`https://www.uniprot.org/uniprotkb/${enz['uniprot-id']}`} target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'none', background: '#7c3aed', color: '#fff', padding: '4px 10px', borderRadius: '4px', fontSize: '0.8rem', fontWeight: 'bold' }}>
                    🧬 UniProt: {enz['uniprot-id']}
                  </a>
                </div>
              ));
            })}
          </div>
        ) : <p style={{ fontStyle: 'italic', color: '#78716c' }}>Sin mapeo enzimático.</p>}
      </div>

      {/* Rutas de Acción SMPDB */}
      {Array.isArray(drug.pathways) && drug.pathways.length > 0 && (
        <div className="detail-section">
          <label>Vías de Acción Metabólica (SMPDB Pathways)</label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
            {drug.pathways.map((path: any, i: number) => (
              <div key={i} style={{ background: '#f3ece0', padding: '10px 14px', borderRadius: '6px', borderLeft: '4px solid #059669', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <strong style={{ color: '#1c1917' }}>{path.name}</strong><br />
                  <span style={{ fontSize: '0.8rem', color: '#78716c' }}>Categoría: {path.category}</span>
                </div>
                <span style={{ fontFamily: 'monospace', color: '#292524', background: '#d6ccbb', padding: '2px 6px', borderRadius: '4px', fontSize: '0.8rem' }}>{path['smpdb-id']}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}