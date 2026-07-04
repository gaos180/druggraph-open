import React from 'react';
import type { DrugRecord } from '../../../types/drug';

export default function GenomicsSection({ drug }: { drug: DrugRecord }) {
  return (
    <>
      {Array.isArray(drug.sequences) && drug.sequences.length > 0 && (
        <div className="detail-section">
          <label>Secuencia FASTA Estructural (Biotech)</label>
          {drug.sequences.map((seq: any, i: number) => (
            <div key={i} style={{ marginTop: '6px' }}>
              <div style={{ fontFamily: 'monospace', background: '#090d16', color: '#34d399', fontSize: '0.8rem', padding: '12px', borderRadius: '6px', wordBreak: 'break-all', maxHeight: '120px', overflowY: 'auto' }}>
                {seq.value}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="detail-section">
        <label>Efectos de Polimorfismos Genéticos (SNP Effects)</label>
        {Array.isArray(drug['snp-effects']) && drug['snp-effects'].length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '6px' }}>
            {drug['snp-effects'].map((snp: any, i: number) => (
              <div key={i} style={{ background: '#f3ece0', padding: '12px', borderRadius: '6px', borderLeft: '4px solid #fbbf24' }}>
                <strong style={{ color: '#1c1917' }}>🧬 rs-ID: {snp['rs-id']} — Gen: {snp['gene-symbol']}</strong>
                <p style={{ margin: '4px 0', fontSize: '0.88rem', color: '#44403c' }}>{snp.description}</p>
                <span style={{ fontSize: '0.75rem', color: '#57534e' }}>Proteína: {snp['protein-name']}</span>
              </div>
            ))}
          </div>
        ) : <p style={{ fontStyle: 'italic', color: '#78716c' }}>Sin efectos SNP registrados.</p>}
      </div>

      <div className="detail-section">
        <label>Reacciones Adversas Genéticas (SNP Adverse Reactions)</label>
        {Array.isArray(drug['snp-adverse-drug-reactions']) && drug['snp-adverse-drug-reactions'].length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
            {drug['snp-adverse-drug-reactions'].map((snpar: any, i: number) => (
              <div key={i} style={{ background: '#f3ece0', padding: '12px', borderRadius: '6px', borderLeft: '4px solid #f87171' }}>
                <strong style={{ color: '#991b1b' }}>🚨 {snpar['adverse-reaction']}</strong>
                <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem' }}>{snpar.description} (Gen: {snpar['gene-symbol']})</p>
              </div>
            ))}
          </div>
        ) : <p style={{ fontStyle: 'italic', color: '#78716c' }}>Sin reacciones adversas genéticas reportadas.</p>}
      </div>
    </>
  );
}