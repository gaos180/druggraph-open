/**
 * SimilarityCards.tsx — átomos de UI del Sandbox: badges de propiedades,
 * barras de score, chips de target y tarjeta de fármaco similar.
 */
import React, { useState } from 'react';
import { TargetSearchResult, CombinedSimilarityResult, sandboxApi, SimilarityDetailResponse } from '../../../api/sandbox';

const FP_LABELS: Record<string, string> = {
  morgan: 'Morgan', maccs: 'MACCS', atompair: 'Atom-pair', pharmacophore: 'Farmacóforo',
};

function MultiFingerprintBreakdown({ smiles, drugbankId }: { smiles?: string; drugbankId: string }) {
  const [data, setData] = useState<SimilarityDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  const toggle = async () => {
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (data || !smiles) return;
    setLoading(true);
    try {
      const res = await sandboxApi.similarityDetail({ smiles, drugbank_id: drugbankId });
      setData(res.data);
    } catch { /* silencioso */ }
    finally { setLoading(false); }
  };

  return (
    <div style={{ marginTop: '2px' }}>
      <button onClick={toggle} disabled={!smiles}
        style={{ background: 'none', border: 'none', color: '#7c3aed', cursor: smiles ? 'pointer' : 'default',
                 fontSize: '0.72rem', fontWeight: 600, padding: 0 }}>
        {open ? '▾' : '▸'} Desglose multi-fingerprint
      </button>
      {open && (
        <div style={{ marginTop: '6px' }}>
          {loading && <div style={{ color: '#78716c', fontSize: '0.72rem' }}>Calculando…</div>}
          {data && data.available && (
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
              {Object.entries(data.per_fingerprint).map(([k, v]) => (
                <span key={k} style={{ fontSize: '0.7rem', color: '#57534e', fontFamily: 'monospace' }}>
                  {FP_LABELS[k] || k}: <strong style={{ color: '#0284c7' }}>{v != null ? `${Math.round(v * 100)}%` : '—'}</strong>
                </span>
              ))}
              <span style={{ fontSize: '0.7rem', color: '#15803d', fontFamily: 'monospace', fontWeight: 700 }}>
                Consenso: {Math.round(data.consensus_score * 100)}%
              </span>
            </div>
          )}
          {data && !data.available && (
            <div style={{ color: '#78716c', fontSize: '0.72rem' }}>{data.notes?.[0] || 'Sin datos.'}</div>
          )}
        </div>
      )}
    </div>
  );
}

export function PropertyBadge({ label, value, unit }: { label: string; value: number | string; unit?: string }) {
  return (
    <div style={{
      background: '#f3ece0', border: '1px solid #bcae98',
      borderRadius: '8px', padding: '10px 14px',
      display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '90px',
    }}>
      <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#0284c7', fontFamily: 'monospace' }}>
        {value}{unit && <span style={{ fontSize: '0.7rem', color: '#57534e' }}> {unit}</span>}
      </span>
      <span style={{ fontSize: '0.68rem', color: '#78716c', marginTop: '2px', textAlign: 'center' }}>
        {label}
      </span>
    </div>
  );
}

export function ScoreBar({ value, color }: { value: number; color: string }) {
  const pct = Math.round(value * 100);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: '120px' }}>
      <div style={{ flex: 1, height: '6px', background: '#d6ccbb', borderRadius: '4px', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: '4px', transition: 'width 0.4s ease' }} />
      </div>
      <span style={{ fontSize: '0.75rem', color, fontFamily: 'monospace', fontWeight: 700, minWidth: '36px' }}>
        {pct}%
      </span>
    </div>
  );
}

export function TargetChip({ target, onRemove }: { target: TargetSearchResult; onRemove: () => void }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '6px',
      background: '#0c2a3a', border: '1px solid #1e4a5f',
      color: '#7dd3fc', padding: '4px 10px', borderRadius: '6px', fontSize: '0.8rem',
    }}>
      <span>{target.name}</span>
      <span style={{ color: '#a8a29e', fontFamily: 'monospace', fontSize: '0.7rem' }}>
        {target.gene_name || target.drugbank_target_id}
      </span>
      <button
        onClick={onRemove}
        style={{ background: 'none', border: 'none', color: '#78716c', cursor: 'pointer', fontSize: '0.9rem', padding: 0, lineHeight: 1 }}
        title="Quitar"
      >×</button>
    </span>
  );
}

export function CombinedResultCard({ result, rank, sandboxSmiles }: { result: CombinedSimilarityResult; rank: number; sandboxSmiles?: string }) {
  return (
    <div style={{
      background: '#f3ece0', border: '1px solid #d6ccbb', borderRadius: '10px',
      padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: '10px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{
            background: '#d6ccbb', color: '#3730a3', fontWeight: 700,
            borderRadius: '6px', width: '28px', height: '28px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '0.85rem', fontFamily: 'monospace',
          }}>#{rank}</span>
          <div>
            <div style={{ color: '#1c1917', fontWeight: 600, fontSize: '0.95rem' }}>{result.name}</div>
            <div style={{ color: '#57534e', fontSize: '0.75rem', fontFamily: 'monospace' }}>{result.drugbank_id}</div>
          </div>
        </div>
        <a
          href={`/drugs/${result.drugbank_id}`}
          target="_blank"
          rel="noreferrer"
          style={{
            background: '#d6ccbb', border: '1px solid #bcae98', color: '#57534e',
            padding: '6px 12px', borderRadius: '6px', fontSize: '0.75rem',
            cursor: 'pointer', fontWeight: 600, whiteSpace: 'nowrap',
            textDecoration: 'none', display: 'inline-block',
          }}
        >Ver perfil ↗</a>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '0.72rem', color: '#78716c', minWidth: '110px' }}>🧬 Estructural</span>
          <ScoreBar value={result.structural_score} color="#0284c7" />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '0.72rem', color: '#78716c', minWidth: '110px' }}>🎯 Comportamiento</span>
          <ScoreBar value={result.behavioral_score} color="#7c3aed" />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '0.72rem', color: '#57534e', minWidth: '110px', fontWeight: 700 }}>⭐ Combinado</span>
          <ScoreBar value={result.combined_score} color="#15803d" />
        </div>
      </div>

      {result.shared_targets && result.shared_targets.length > 0 && (
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '2px' }}>
          {result.shared_targets.slice(0, 6).map((t) => (
            <span key={t} style={{
              background: '#1a0a28', border: '1px solid #3b1a5c',
              color: '#c4b5fd', padding: '2px 7px', borderRadius: '4px',
              fontSize: '0.68rem', fontFamily: 'monospace',
            }}>{t}</span>
          ))}
          {result.shared_targets.length > 6 && (
            <span style={{ color: '#57534e', fontSize: '0.7rem', alignSelf: 'center' }}>
              +{result.shared_targets.length - 6} más
            </span>
          )}
        </div>
      )}

      <MultiFingerprintBreakdown smiles={sandboxSmiles} drugbankId={result.drugbank_id} />
    </div>
  );
}
