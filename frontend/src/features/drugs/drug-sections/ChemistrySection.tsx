import React from 'react';
import type { DrugRecord } from '../../../types/drug';

export default function ChemistrySection({ drug }: { drug: DrugRecord }) {
  if (!drug) return null;

  return (
    <>
      {/* Clasificación Taxonómica de ClassyFire */}
      {drug.classification && (
        <div className="detail-section">
          <label>Clasificación Química (ClassyFire Taxon)</label>
          <p style={{ fontStyle: 'italic', marginBottom: '8px' }}>{drug.classification.description}</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '10px', background: '#f3ece0', padding: '12px', borderRadius: '6px', fontSize: '0.85rem' }}>
            <div>🟢 <span style={{ color: '#6366f1' }}>Reino:</span> {drug.classification.kingdom}</div>
            <div>🟢 <span style={{ color: '#6366f1' }}>Superclase:</span> {drug.classification.superclass}</div>
            <div>🟢 <span style={{ color: '#6366f1' }}>Clase:</span> {drug.classification.class}</div>
            <div>🟢 <span style={{ color: '#6366f1' }}>Padre Directo:</span> {drug.classification['direct-parent']}</div>
          </div>
        </div>
      )}

      {/* Masas Moleculares */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
        <div className="detail-section">
          <label>Masa Promedio (Average Mass)</label>
          <p>{drug['average-mass']} Da</p>
        </div>
        <div className="detail-section">
          <label>Masa Monoisotópica</label>
          <p style={{ fontFamily: 'monospace' }}>{drug['monoisotopic-mass']} Da</p>
        </div>
      </div>

      {/* Propiedades Calculadas */}
      <div className="detail-section">
        <label>Propiedades Químicas Calculadas e IUPAC</label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
          {Array.isArray(drug['calculated-properties']) && drug['calculated-properties'].map((prop: any, i: number) => {
            if (['logP', 'logS', 'Water Solubility', 'IUPAC Name', 'SMILES', 'InChIKey'].includes(prop.kind)) {
              return (
                <div key={i} style={{ fontSize: '0.9rem', background: '#f3ece0', padding: '8px 12px', borderRadius: '6px', fontFamily: prop.kind === 'SMILES' ? 'monospace' : 'inherit' }}>
                  <strong style={{ color: '#7c2d12' }}>{prop.kind}:</strong> {prop.value} <span style={{ fontSize: '0.75rem', color: '#78716c' }}>({prop.source})</span>
                </div>
              );
            }
            return null;
          })}
        </div>
      </div>

      {/* Referencia de Síntesis */}
      {drug['synthesis-reference'] && (
        <div className="detail-section">
          <label>Síntesis Química (Synthesis Reference)</label>
          <p style={{ fontFamily: 'monospace', fontSize: '0.85rem', color: '#44403c' }}>{drug['synthesis-reference']}</p>
        </div>
      )}
    </>
  );
}