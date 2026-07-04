import React, { useState } from 'react';
import { sandboxApi, EmbeddingSimilarityResponse } from '../../../api/sandbox';

/**
 * EmbeddingSimilarityPanel — similitud molecular aprendida (ChemBERTa) por vecino
 * más cercano (índice vectorial de Neo4j). Complementa la similitud estructural
 * de Tanimoto/fingerprints. Carga bajo demanda (el modelo es pesado).
 */
export default function EmbeddingSimilarityPanel({ smiles }: { smiles?: string }) {
  const [data, setData] = useState<EmbeddingSimilarityResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    if (!smiles) return;
    setLoading(true); setError('');
    try {
      const res = await sandboxApi.embeddingSimilarity(smiles);
      setData(res.data);
    } catch (err: any) {
      const status = err?.response?.status;
      setError(status === 503
        ? (err?.response?.data?.error || 'Embeddings no disponibles en el servidor.')
        : (err?.response?.data?.error || 'No se pudo calcular la similitud por embedding.'));
    } finally { setLoading(false); }
  };

  return (
    <div style={{ background: '#faf6ee', border: '2px solid #1e1814', borderRadius: '12px',
                  padding: '16px', boxShadow: '4px 4px 0px #1e1814' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ fontFamily: 'var(--font-hand, inherit)', fontWeight: 700, fontSize: '1.05rem', color: '#1c1917' }}>
          Similitud por embedding (ChemBERTa)
        </div>
        {!data && (
          <button onClick={load} disabled={loading || !smiles}
            style={{ background: '#1e1814', color: '#faf6ee', border: 'none', borderRadius: '8px',
                     padding: '8px 14px', fontWeight: 600, fontSize: '0.85rem',
                     cursor: smiles ? 'pointer' : 'default', opacity: loading ? 0.6 : 1 }}>
            {loading ? 'Calculando embedding…' : 'Buscar por embedding'}
          </button>
        )}
      </div>
      <p style={{ fontSize: '0.75rem', color: '#78716c', margin: '6px 0 0 0' }}>
        Similitud molecular <strong>aprendida</strong> (transformer sobre SMILES), complementaria a Tanimoto. Requiere el índice vectorial poblado en el servidor.
      </p>
      {error && <div style={{ color: '#b91c1c', fontSize: '0.8rem', marginTop: '8px' }}>{error}</div>}
      {data?.results && data.results.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', marginTop: '10px' }}>
          <thead><tr>{['Fármaco', 'ID', 'Coseno'].map(h => (
            <th key={h} style={{ textAlign: 'left', padding: '5px 8px', color: '#78716c', fontSize: '0.72rem' }}>{h}</th>
          ))}</tr></thead>
          <tbody>
            {data.results.map((r, i) => (
              <tr key={r.drugbank_id} style={{ background: i % 2 ? '#f3ece0' : 'transparent' }}>
                <td style={{ padding: '5px 8px', color: '#1c1917' }}>{r.name}</td>
                <td style={{ padding: '5px 8px', color: '#0369a1', fontFamily: 'monospace' }}>
                  <a href={`/drugs/${r.drugbank_id}`} target="_blank" rel="noreferrer" style={{ color: '#0369a1', textDecoration: 'none' }}>{r.drugbank_id}</a>
                </td>
                <td style={{ padding: '5px 8px', color: '#15803d', fontFamily: 'monospace', fontWeight: 700 }}>{r.score.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {data && data.results && data.results.length === 0 && (
        <div style={{ color: '#78716c', fontSize: '0.8rem', marginTop: '8px' }}>Sin vecinos en el índice.</div>
      )}
    </div>
  );
}
