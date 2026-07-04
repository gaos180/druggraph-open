/**
 * SwissTargetPanel.tsx — panel de importación de predicciones de
 * SwissTargetPrediction (CSV o API), con selección y cruce contra DrugGraph.
 */
import React, { useState, useRef, useCallback } from 'react';
import {
  sandboxApi, SwissTargetResult, SwissTargetsResponse, TargetSearchResult,
} from '../../../api/sandbox';
import { probColor, probColorDark } from './styles';

interface SwissPanelProps {
  smiles: string;
  onImport: (targets: TargetSearchResult[]) => void;
}

export default function SwissTargetPanel({ smiles, onImport }: SwissPanelProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [results, setResults]       = useState<SwissTargetResult[]>([]);
  const [matched, setMatched]       = useState(0);
  const [total, setTotal]           = useState(0);
  const [organisms, setOrganisms]   = useState<string[]>(['Homo sapiens']);
  const [organism, setOrganism]     = useState('Homo sapiens');
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState('');
  const [selected, setSelected]     = useState<Set<string>>(new Set());
  const [showAll, setShowAll]       = useState(false);
  const [minProb, setMinProb]       = useState(0.2);
  const [source, setSource]         = useState<'api' | 'csv'>('csv');
  const [apiUnavailable, setApiUnavailable] = useState(false);

  const handleResponse = useCallback((data: SwissTargetsResponse) => {
    setResults(data.results);
    setMatched(data.matched);
    setTotal(data.total);
    setOrganisms(data.organisms ?? ['Homo sapiens']);
    const preselected = new Set(
      data.results
        .filter((r) => r.in_druggraph && r.probability >= minProb)
        .map((r) => r.uniprot_id || r.gene_name),
    );
    setSelected(preselected);
    setError('');
  }, [minProb]);

  const fetchFromApi = () => {
    if (!smiles.trim()) { setError('Ingresa un SMILES antes de predecir.'); return; }
    setLoading(true); setError('');
    sandboxApi.predictSwiss(smiles.trim(), organism)
      .then((r) => handleResponse(r.data))
      .catch((e) => {
        if (e?.response?.status === 503 || e?.response?.data?.error === 'api_unavailable') {
          setSource('csv');
          setApiUnavailable(true);
        } else {
          setError(e?.response?.data?.error || 'Error llamando a SwissTargetPrediction. Intenta importar el CSV manualmente.');
        }
      })
      .finally(() => setLoading(false));
  };

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true); setError('');
    sandboxApi.importSwissCsv(file)
      .then((r) => handleResponse(r.data))
      .catch((e) => setError(e?.response?.data?.error || 'Error parseando el CSV.'))
      .finally(() => { setLoading(false); e.target.value = ''; });
  };

  const toggleSelect = (key: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const handleImport = () => {
    const toImport = results
      .filter((r) => r.in_druggraph && r.drugbank_target_id &&
        selected.has(r.uniprot_id || r.gene_name))
      .map((r) => ({
        drugbank_target_id: r.drugbank_target_id!,
        uniprot_id: r.uniprot_id,
        gene_name: r.gene_name,
        name: r.db_name || r.target_name,
        organism: r.db_organism || '',
      }));
    onImport(toImport);
  };

  const visible = results.filter(
    (r) => r.probability >= minProb && (showAll || r.in_druggraph),
  );

  const selectedInDg = results.filter(
    (r) => r.in_druggraph && selected.has(r.uniprot_id || r.gene_name),
  ).length;

  return (
    <div style={{
      background: '#0c1a2b', border: '1px solid #cdd9e6',
      borderRadius: '10px', padding: '16px',
    }}>
      {/* Cabecera */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <span style={{ color: '#38bdf8', fontWeight: 700, fontSize: '0.9rem' }}>
            SwissTargetPrediction
          </span>
          <span style={{ color: '#a8a29e', fontSize: '0.75rem', marginLeft: '8px' }}>
            predicción automática de targets
          </span>
        </div>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Selector de modo */}
          <div style={{ display: 'flex', background: '#f3ece0', borderRadius: '6px', border: '1px solid #bcae98', overflow: 'hidden' }}>
            {(['csv', 'api'] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => { setSource(m); if (m === 'api') setApiUnavailable(false); }}
                style={{
                  padding: '5px 12px', border: 'none', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600,
                  background: source === m ? '#1e4a5f' : 'transparent',
                  color: source === m ? '#38bdf8' : '#78716c',
                  transition: 'background 0.15s',
                }}
              >
                {m === 'csv' ? '📂 Importar CSV' : '🌐 API en línea'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Controles según modo */}
      {source === 'csv' ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <p style={{ color: '#78716c', fontSize: '0.78rem', margin: 0, flex: 1 }}>
            Descarga el CSV desde{' '}
            <span style={{ color: '#38bdf8', fontFamily: 'monospace' }}>swisstargetprediction.ch</span>
            {' '}con tu SMILES y súbelo aquí.
          </p>
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={loading}
            style={{
              background: '#1e4a5f', border: '1px solid #2d6a8a',
              color: '#7dd3fc', padding: '8px 16px', borderRadius: '7px',
              fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap',
            }}
          >
            {loading ? 'Procesando…' : '📂 Seleccionar CSV'}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".csv"
            onChange={handleFile}
            style={{ display: 'none' }}
          />
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <select
            value={organism}
            onChange={(e) => setOrganism(e.target.value)}
            style={{
              background: '#f3ece0', border: '1px solid #bcae98', color: '#57534e',
              padding: '7px 10px', borderRadius: '7px', fontSize: '0.8rem',
            }}
          >
            {organisms.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
          <button
            type="button"
            onClick={fetchFromApi}
            disabled={loading}
            style={{
              background: loading ? '#d6ccbb' : '#1e4a5f',
              border: '1px solid #2d6a8a', color: '#7dd3fc',
              padding: '8px 16px', borderRadius: '7px', fontSize: '0.82rem',
              fontWeight: 600, cursor: loading ? 'default' : 'pointer',
            }}
          >
            {loading ? 'Prediciendo…' : '🔮 Predecir'}
          </button>
        </div>
      )}

      {/* Banner API no disponible */}
      {apiUnavailable && (
        <div style={{
          background: '#1a130a', border: '1px solid #7c5e1d', color: '#fde68a',
          padding: '10px 14px', borderRadius: '7px', fontSize: '0.8rem', marginTop: '10px',
          lineHeight: '1.6',
        }}>
          ⚠ La API automática de SwissTargetPrediction <strong>ya no está disponible</strong> programáticamente.{' '}
          Visita{' '}
          <a
            href="https://www.swisstargetprediction.ch/predict.php"
            target="_blank"
            rel="noreferrer"
            style={{ color: '#38bdf8' }}
          >
            swisstargetprediction.ch
          </a>
          , introduce tu SMILES, descarga el CSV y súbelo con el botón de arriba.
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          background: '#1a0a0a', border: '1px solid #7f1d1d', color: '#fca5a5',
          padding: '8px 12px', borderRadius: '7px', fontSize: '0.8rem', marginTop: '10px',
        }}>
          ⚠ {error}
        </div>
      )}

      {/* Resultados */}
      {results.length > 0 && (
        <div style={{ marginTop: '14px' }}>
          {/* Resumen y controles de filtro */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '6px' }}>
            <div style={{ fontSize: '0.78rem', color: '#78716c' }}>
              <span style={{ color: '#4ade80', fontWeight: 700 }}>{matched}</span>
              /{total} targets encontrados en DrugGraph
            </div>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              {/* Seleccionar / deseleccionar todos los visibles en DrugGraph */}
              {(() => {
                const visibleInDg = visible.filter((r) => r.in_druggraph);
                const allSelected = visibleInDg.length > 0 &&
                  visibleInDg.every((r) => selected.has(r.uniprot_id || r.gene_name));
                return visibleInDg.length > 0 ? (
                  <button
                    type="button"
                    onClick={() => {
                      if (allSelected) {
                        setSelected((prev) => {
                          const next = new Set(prev);
                          visibleInDg.forEach((r) => next.delete(r.uniprot_id || r.gene_name));
                          return next;
                        });
                      } else {
                        setSelected((prev) => {
                          const next = new Set(prev);
                          visibleInDg.forEach((r) => next.add(r.uniprot_id || r.gene_name));
                          return next;
                        });
                      }
                    }}
                    style={{
                      background: allSelected ? '#1e3a2e' : '#d6ccbb',
                      border: `1px solid ${allSelected ? '#166534' : '#bcae98'}`,
                      color: allSelected ? '#4ade80' : '#57534e',
                      padding: '4px 10px', borderRadius: '6px',
                      fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer',
                    }}
                  >
                    {allSelected ? '☑ Quitar todos' : '☐ Seleccionar todos'}
                  </button>
                ) : null;
              })()}
              <label style={{ fontSize: '0.75rem', color: '#78716c', display: 'flex', alignItems: 'center', gap: '5px' }}>
                Prob. mín.
                <input
                  type="range" min={0} max={1} step={0.05}
                  value={minProb}
                  onChange={(e) => setMinProb(parseFloat(e.target.value))}
                  style={{ width: '70px', accentColor: '#38bdf8' }}
                />
                <span style={{ fontFamily: 'monospace', color: '#38bdf8', minWidth: '32px' }}>
                  {Math.round(minProb * 100)}%
                </span>
              </label>
              <label style={{ fontSize: '0.75rem', color: '#78716c', display: 'flex', alignItems: 'center', gap: '5px', cursor: 'pointer' }}>
                <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} style={{ accentColor: '#38bdf8' }} />
                Mostrar todos
              </label>
            </div>
          </div>

          {/* Lista de targets */}
          <div style={{ maxHeight: '320px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {visible.length === 0 && (
              <div style={{ color: '#a8a29e', fontSize: '0.8rem', textAlign: 'center', padding: '16px' }}>
                Sin resultados con los filtros actuales.
              </div>
            )}
            {visible.map((r) => {
              const key = r.uniprot_id || r.gene_name;
              const isSelected = selected.has(key);
              return (
                <div
                  key={key}
                  onClick={() => r.in_druggraph && toggleSelect(key)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '10px',
                    padding: '7px 10px', borderRadius: '7px', cursor: r.in_druggraph ? 'pointer' : 'default',
                    background: isSelected ? '#0c2a3a' : '#f3ece0',
                    border: `1px solid ${isSelected ? '#1e4a5f' : '#d6ccbb'}`,
                    opacity: r.in_druggraph ? 1 : 0.5,
                    transition: 'background 0.15s, border 0.15s',
                  }}
                >
                  {/* Checkbox */}
                  <input
                    type="checkbox"
                    checked={isSelected}
                    disabled={!r.in_druggraph}
                    onChange={() => r.in_druggraph && toggleSelect(key)}
                    onClick={(e) => e.stopPropagation()}
                    style={{ accentColor: '#38bdf8', flexShrink: 0 }}
                  />

                  {/* Probabilidad */}
                  <div style={{ width: '44px', flexShrink: 0 }}>
                    <div style={{ height: '4px', background: '#d6ccbb', borderRadius: '4px', overflow: 'hidden' }}>
                      <div style={{ width: `${Math.round(r.probability * 100)}%`, height: '100%', background: probColor(r.probability), borderRadius: '4px' }} />
                    </div>
                    <span style={{ fontSize: '0.65rem', color: isSelected ? probColor(r.probability) : probColorDark(r.probability), fontFamily: 'monospace' }}>
                      {Math.round(r.probability * 100)}%
                    </span>
                  </div>

                  {/* Nombre y gen */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: '0.82rem', color: '#292524', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {r.in_druggraph ? (r.db_name || r.target_name) : r.target_name}
                    </div>
                    <div style={{ display: 'flex', gap: '6px', marginTop: '1px', flexWrap: 'wrap' }}>
                      {r.gene_name && (
                        <span style={{ fontSize: '0.68rem', fontFamily: 'monospace', color: isSelected ? '#7dd3fc' : '#0369a1' }}>{r.gene_name}</span>
                      )}
                      {r.uniprot_id && (
                        <span style={{ fontSize: '0.68rem', fontFamily: 'monospace', color: isSelected ? '#a8a29e' : '#57534e' }}>{r.uniprot_id}</span>
                      )}
                      {r.target_class && (
                        <span style={{ fontSize: '0.65rem', color: '#78716c' }}>{r.target_class}</span>
                      )}
                    </div>
                  </div>

                  {/* Badge DrugGraph */}
                  {r.in_druggraph ? (
                    <span style={{
                      background: '#052e16', border: '1px solid #166534', color: '#4ade80',
                      padding: '2px 7px', borderRadius: '5px', fontSize: '0.65rem', fontWeight: 700, flexShrink: 0,
                    }}>En DrugGraph</span>
                  ) : (
                    <span style={{
                      background: '#d6ccbb', border: '1px solid #bcae98', color: '#57534e',
                      padding: '2px 7px', borderRadius: '5px', fontSize: '0.65rem', flexShrink: 0,
                    }}>No disponible</span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Botón importar */}
          {selectedInDg > 0 && (
            <button
              type="button"
              onClick={handleImport}
              style={{
                marginTop: '10px', width: '100%',
                background: '#2d2621',
                border: '1px solid #2d6a8a', color: '#7dd3fc',
                padding: '10px', borderRadius: '8px', fontWeight: 700,
                fontSize: '0.85rem', cursor: 'pointer',
              }}
            >
              ✓ Importar {selectedInDg} target{selectedInDg !== 1 ? 's' : ''} al sandbox
            </button>
          )}
        </div>
      )}
    </div>
  );
}
