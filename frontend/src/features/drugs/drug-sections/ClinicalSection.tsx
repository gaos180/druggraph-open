import React from 'react';
import type { DrugRecord } from '../../../types/drug';

export default function ClinicalSection({ drug }: { drug: DrugRecord }) {
  if (!drug) return null;

  return (
    <>
      <div className="detail-section">
        <label>Indicación Clínica Autorizada</label>
        <p>{drug.indication || 'No registrada.'}</p>
      </div>
      <div className="detail-section">
        <label>Toxicidad y Sintomatología de Sobredosis</label>
        <p>{drug.toxicity || 'No registrada.'}</p>
      </div>
      
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
        <div className="detail-section">
          <label>Restricciones Alimenticias (Food Interactions)</label>
          <ul style={{ margin: '6px 0 0 16px', padding: 0, color: '#44403c' }}>
            {Array.isArray(drug['food-interactions']) ? drug['food-interactions'].map((f: string, i: number) => <li key={i}>{f}</li>) : <li>No registradas.</li>}
          </ul>
        </div>
        <div className="detail-section">
          <label>Organismos Afectados</label>
          <div style={{ marginTop: '6px' }}>
            {Array.isArray(drug['affected-organisms']) ? drug['affected-organisms'].map((o: string, i: number) => <span key={i} className="tag-type" style={{ background: '#064e3b', color: '#34d399', padding: '4px 10px' }}>{o}</span>) : 'N/A'}
          </div>
        </div>
      </div>

      {/* Códigos ATC */}
      {Array.isArray(drug['atc-codes']) && drug['atc-codes'].length > 0 && (
        <div className="detail-section">
          <label>Códigos Anatómicos / Terapéuticos (ATC Codes)</label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
            {drug['atc-codes'].map((codeObj: any, i: number) => (
              <div key={i} style={{ background: '#f3ece0', padding: '8px 12px', borderRadius: '6px', fontSize: '0.88rem' }}>
                🔑 <strong style={{ color: '#1e40af' }}>{codeObj.code}</strong>
                <div style={{ paddingLeft: '14px', marginTop: '4px', fontSize: '0.8rem', color: '#57534e' }}>
                  {Array.isArray(codeObj.level) && codeObj.level.map((lvl: any, j: number) => (
                    <div key={j}>• [{lvl.code}] {lvl.value}</div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Interacciones Medicamentosas Masivas */}
      {Array.isArray(drug['drug-interactions']) && drug['drug-interactions'].length > 0 && (
        <div className="detail-section">
          <label>Interacciones Medicamentosas ({drug['drug-interactions'].length})</label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '8px', maxHeight: '250px', overflowY: 'auto', marginTop: '6px' }}>
            {drug['drug-interactions'].map((di: any, idx: number) => (
              <div key={idx} style={{ background: '#f3ece0', padding: '10px', borderRadius: '6px', fontSize: '0.85rem', borderLeft: '3px solid #fbbf24' }}>
                <strong>{di.name} ({di['drugbank-id']}):</strong> {di.description}
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}