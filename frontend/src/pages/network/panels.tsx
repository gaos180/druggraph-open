import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  gdsApi,
  CentralityResponse,
  CommunitiesResponse,
  LinkPredictionResponse,
  Community,
} from '../../api/gds';
import { drugsApi, DrugSummary } from '../../api/drugs';
import CytoscapeGraph, { CyNode, CyEdge } from '../../components/CytoscapeGraph';

// ── Helpers de presentación ────────────────────────────────────────────────

function ScoreBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: '140px' }}>
      <div style={{ flex: 1, height: '6px', background: '#d6ccbb', borderRadius: '4px', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: '4px' }} />
      </div>
      <span style={{ fontSize: '0.74rem', color, fontFamily: 'monospace', minWidth: '52px', textAlign: 'right' }}>
        {value.toFixed(3)}
      </span>
    </div>
  );
}

function ErrorBox({ msg, isGdsError }: { msg: string; isGdsError: boolean }) {
  return (
    <div style={{
      background: '#1a0a0a', border: '1px solid #7f1d1d', color: '#fca5a5',
      padding: '20px', borderRadius: '10px', textAlign: 'center',
    }}>
      <div style={{ fontSize: '1.3rem', marginBottom: '6px' }}>⚠</div>
      <div>{msg}</div>
      {isGdsError && (
        <div style={{ fontSize: '0.8rem', color: '#78350f', marginTop: '8px' }}>
          Instala el plugin Graph Data Science en Neo4j para habilitar este análisis.
        </div>
      )}
    </div>
  );
}

const COMMUNITY_PALETTE = [
  '#6366f1', '#a855f7', '#ec4899', '#f59e0b', '#10b981',
  '#06b6d4', '#8b5cf6', '#ef4444', '#84cc16', '#14b8a6',
];

function downloadCsv(filename: string, headers: string[], rows: (string | number)[][]) {
  const esc = (v: string | number) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const lines = [headers.map(esc).join(','), ...rows.map(r => r.map(esc).join(','))];
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

const exportBtnStyle: React.CSSProperties = {
  padding: '6px 12px', borderRadius: '6px', border: '1px solid #bcae98',
  background: 'transparent', color: '#57534e', fontSize: '0.78rem',
  cursor: 'pointer', whiteSpace: 'nowrap',
};

// ── Panel: Centralidad ───────────────────────────────────────────────────────

export function CentralityPanel() {
  const navigate = useNavigate();
  const [node, setNode]       = useState<'Target' | 'Drug'>('Target');
  const [metric, setMetric]   = useState<'pagerank' | 'degree'>('degree');
  const [data, setData]       = useState<CentralityResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');
  const [isGdsError, setIsGdsError] = useState(false);
  const [filter, setFilter]   = useState('');

  const run = () => {
    setLoading(true); setError(''); setIsGdsError(false); setData(null); setFilter('');
    gdsApi.centrality({ node, metric, top_n: 50 })
      .then((res) => setData(res.data))
      .catch((err) => {
        setError(err?.response?.data?.error || 'Error en el análisis.');
        setIsGdsError(err?.response?.status === 503);
      })
      .finally(() => setLoading(false));
  };

  const maxScore = data?.results[0]?.score ?? 1;
  const filteredResults = React.useMemo(() => {
    if (!data) return [];
    if (!filter.trim()) return data.results;
    const q = filter.toLowerCase();
    return data.results.filter(r =>
      r.name?.toLowerCase().includes(q) || r.id.toLowerCase().includes(q) || r.uniprot_id?.toLowerCase().includes(q)
    );
  }, [data, filter]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <p style={{ color: '#78716c', fontSize: '0.88rem', margin: 0 }}>
        Encuentra los nodos más conectados de la red. Un <strong style={{ color: '#57534e' }}>target con grado alto</strong> es
        una diana promiscua (potencial fuente de efectos off-target); un <strong style={{ color: '#57534e' }}>fármaco con
        grado alto</strong> actúa sobre muchas dianas.
      </p>

      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '4px' }}>
          {(['Target', 'Drug'] as const).map((n) => (
            <button key={n} onClick={() => setNode(n)} style={{
              padding: '7px 14px', borderRadius: '6px', fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer',
              border: 'none', background: node === n ? '#0c4a6e' : '#d6ccbb',
              color: node === n ? '#38bdf8' : '#57534e',
            }}>
              {n === 'Target' ? '🎯 Dianas' : '💊 Fármacos'}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: '4px' }}>
          {(['degree', 'pagerank'] as const).map((m) => (
            <button key={m} onClick={() => setMetric(m)} style={{
              padding: '7px 14px', borderRadius: '6px', fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer',
              border: 'none', background: metric === m ? '#312e81' : '#d6ccbb',
              color: metric === m ? '#a5b4fc' : '#57534e',
            }}>
              {m === 'degree' ? 'Grado' : 'PageRank'}
            </button>
          ))}
        </div>
        <button onClick={run} disabled={loading} style={{
          padding: '7px 18px', borderRadius: '6px', fontSize: '0.82rem', fontWeight: 700, cursor: 'pointer',
          border: 'none', background: loading ? '#bcae98' : '#2d2621', color: '#fff',
        }}>
          {loading ? 'Calculando…' : 'Calcular'}
        </button>
        {data && (
          <button
            onClick={() => downloadCsv(
              `centrality_${node.toLowerCase()}_${metric}.csv`,
              ['rank', 'name', 'id', 'uniprot_id', 'organism', 'score'],
              data.results.map((r, i) => [i + 1, r.name || r.id, r.id, r.uniprot_id || '', r.organism || '', r.score])
            )}
            style={exportBtnStyle}
          >
            ⬇ Exportar CSV
          </button>
        )}
      </div>

      {error && <ErrorBox msg={error} isGdsError={isGdsError} />}

      {data && (
        <>
          <input
            value={filter}
            onChange={e => setFilter(e.target.value)}
            placeholder={`🔍 Buscar ${node === 'Target' ? 'diana / gen / UniProt' : 'fármaco / DrugBank ID'}…`}
            style={{
              background: '#f3ece0', border: '1px solid #bcae98', color: '#1c1917',
              padding: '8px 12px', borderRadius: '6px', fontSize: '0.85rem', outline: 'none',
            }}
          />
          {filter && (
            <div style={{ fontSize: '0.78rem', color: '#57534e' }}>
              {filteredResults.length === 0
                ? 'Sin coincidencias'
                : `${filteredResults.length} resultado${filteredResults.length !== 1 ? 's' : ''} de ${data.results.length}`
              }
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {filteredResults.map((r) => {
              const globalIdx = data.results.findIndex(x => x.id === r.id);
              return (
                <div key={r.id} style={{
                  display: 'flex', alignItems: 'center', gap: '12px',
                  background: filter && '#f3ece0' ? '#f3ece0' : '#f3ece0',
                  border: `1px solid ${filter ? '#cdd9e6' : '#d6ccbb'}`,
                  borderRadius: '8px', padding: '10px 14px',
                }}>
                  <span style={{ color: '#57534e', fontFamily: 'monospace', fontSize: '0.8rem', minWidth: '28px' }}>
                    #{globalIdx + 1}
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ color: '#1c1917', fontSize: '0.88rem', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {r.name || r.id}
                    </div>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      <span style={{ color: '#0369a1', fontSize: '0.7rem', fontFamily: 'monospace' }}>{r.id}</span>
                      {r.uniprot_id && <span style={{ color: '#6d28d9', fontSize: '0.7rem', fontFamily: 'monospace' }}>{r.uniprot_id}</span>}
                      {r.organism && <span style={{ color: '#78716c', fontSize: '0.7rem', fontStyle: 'italic' }}>{r.organism}</span>}
                    </div>
                  </div>
                  <ScoreBar value={r.score} max={maxScore} color={node === 'Target' ? '#38bdf8' : '#a5b4fc'} />
                  {node === 'Drug' && (
                    <button onClick={() => navigate(`/drugs/${r.id}`)} style={{
                      background: '#d6ccbb', border: '1px solid #bcae98', color: '#57534e',
                      padding: '5px 10px', borderRadius: '6px', fontSize: '0.72rem', cursor: 'pointer', whiteSpace: 'nowrap',
                    }}>
                      Ver →
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

// ── Panel: Comunidades ───────────────────────────────────────────────────────

export function CommunitiesPanel() {
  const [data, setData]       = useState<CommunitiesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');
  const [isGdsError, setIsGdsError] = useState(false);
  const [selected, setSelected] = useState<Community | null>(null);
  const [filter, setFilter]   = useState('');

  const run = () => {
    setLoading(true); setError(''); setIsGdsError(false); setData(null); setSelected(null); setFilter('');
    gdsApi.communities({ max: 40, min_size: 3, members: 30 })
      .then((res) => { setData(res.data); setSelected(res.data.communities[0] ?? null); })
      .catch((err) => {
        setError(err?.response?.data?.error || 'Error en el análisis.');
        setIsGdsError(err?.response?.status === 503);
      })
      .finally(() => setLoading(false));
  };

  const filteredCommunities = React.useMemo(() => {
    if (!data) return [];
    if (!filter.trim()) return data.communities;
    const q = filter.toLowerCase();
    return data.communities.filter(c =>
      c.members.some(m => m.name.toLowerCase().includes(q) || m.id.toLowerCase().includes(q))
    );
  }, [data, filter]);

  React.useEffect(() => {
    if (filteredCommunities.length > 0) setSelected(filteredCommunities[0]);
  }, [filteredCommunities]);

  // Construir grafo Cytoscape de la comunidad seleccionada
  const { cyNodes, cyEdges } = React.useMemo(() => {
    if (!selected) return { cyNodes: [] as CyNode[], cyEdges: [] as CyEdge[] };
    const nodes: CyNode[] = selected.members.map((m) => ({
      id: m.id || `${m.kind}-${m.name}`,
      label: m.name || m.id,
      kind: m.kind === 'Drug' ? 'drug' : 'target',
    }));
    // Conectar cada drug con cada target de la comunidad (vista de módulo).
    // Las aristas reales se obtienen del endpoint /graph/ por fármaco; aquí
    // mostramos la pertenencia al módulo de forma compacta.
    const drugs   = selected.members.filter((m) => m.kind === 'Drug');
    const targets = selected.members.filter((m) => m.kind === 'Target');
    const edges: CyEdge[] = [];
    drugs.forEach((d) => {
      targets.forEach((t) => {
        edges.push({
          id: `${d.id}-${t.id}`,
          source: d.id || `Drug-${d.name}`,
          target: t.id || `Target-${t.name}`,
        });
      });
    });
    return { cyNodes: nodes, cyEdges: edges };
  }, [selected]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <p style={{ color: '#78716c', fontSize: '0.88rem', margin: 0 }}>
        Detecta módulos de fármacos y dianas densamente interconectados (Louvain).
        Cada comunidad agrupa fármacos que comparten dianas — útil para identificar
        familias terapéuticas y posibles candidatos de reposicionamiento.
      </p>

      <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
        <button onClick={run} disabled={loading} style={{
          padding: '8px 20px', borderRadius: '6px', fontSize: '0.85rem', fontWeight: 700,
          cursor: 'pointer', border: 'none', background: loading ? '#bcae98' : '#2d2621', color: '#fff',
        }}>
          {loading ? 'Detectando comunidades…' : 'Detectar Comunidades'}
        </button>
        {data && (
          <button
            onClick={() => {
              const rows: (string | number)[][] = [];
              data.communities.forEach((c, idx) => {
                c.members.forEach(m => {
                  rows.push([idx + 1, c.community_id, c.drug_count, c.target_count, m.kind, m.id || '', m.name || '']);
                });
              });
              downloadCsv('communities.csv',
                ['community_idx', 'community_id', 'drug_count', 'target_count', 'kind', 'id', 'name'],
                rows
              );
            }}
            style={exportBtnStyle}
          >
            ⬇ Exportar CSV
          </button>
        )}
      </div>

      {error && <ErrorBox msg={error} isGdsError={isGdsError} />}

      {data && (
        <div className="grid gap-4 grid-cols-1 md:grid-cols-[280px_1fr]">
          {/* Lista de comunidades */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <input
              value={filter}
              onChange={e => setFilter(e.target.value)}
              placeholder="🔍 Buscar fármaco o diana en comunidades…"
              style={{
                background: '#f3ece0', border: '1px solid #bcae98', color: '#1c1917',
                padding: '7px 10px', borderRadius: '6px', fontSize: '0.8rem', outline: 'none',
              }}
            />
            <div style={{ color: '#78716c', fontSize: '0.78rem' }}>
              {filter
                ? `${filteredCommunities.length} de ${data.community_count} comunidades`
                : `${data.community_count} comunidades`
              }
            </div>
            <div style={{ maxHeight: '480px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {filteredCommunities.map((c, idx) => {
              const color = COMMUNITY_PALETTE[idx % COMMUNITY_PALETTE.length];
              const active = selected?.community_id === c.community_id;
              const matchingMembers = filter
                ? c.members.filter(m => m.name.toLowerCase().includes(filter.toLowerCase()) || m.id.toLowerCase().includes(filter.toLowerCase()))
                : [];
              return (
                <button key={c.community_id} onClick={() => setSelected(c)} style={{
                  textAlign: 'left', background: active ? '#d6ccbb' : '#f3ece0',
                  border: `1px solid ${active ? color : '#d6ccbb'}`, borderLeft: `3px solid ${color}`,
                  borderRadius: '8px', padding: '10px 12px', cursor: 'pointer',
                }}>
                  <div style={{ color: '#1c1917', fontSize: '0.82rem', fontWeight: 600 }}>
                    Comunidad {idx + 1}
                  </div>
                  <div style={{ color: '#78716c', fontSize: '0.72rem', marginTop: '2px' }}>
                    {c.drug_count} fármacos · {c.target_count} dianas
                  </div>
                  {matchingMembers.length > 0 && (
                    <div style={{ marginTop: '4px', fontSize: '0.7rem', color: '#f59e0b' }}>
                      ✓ {matchingMembers.slice(0, 2).map(m => m.name || m.id).join(', ')}
                      {matchingMembers.length > 2 && ` +${matchingMembers.length - 2}`}
                    </div>
                  )}
                </button>
              );
            })}
            </div>
          </div>

          {/* Grafo de la comunidad seleccionada */}
          <div>
            {selected ? (
              <>
                <div style={{ color: '#57534e', fontSize: '0.8rem', marginBottom: '8px' }}>
                  Módulo con {selected.drug_count} fármacos y {selected.target_count} dianas
                  {selected.members.length < selected.size && ' (vista parcial)'}
                </div>
                <CytoscapeGraph nodes={cyNodes} edges={cyEdges} height={460} layout="cose" />
              </>
            ) : (
              <div style={{ color: '#a8a29e', padding: '40px', textAlign: 'center' }}>
                Selecciona una comunidad para visualizarla.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Panel: Predicción de enlaces ───────────────────────────────────────────────

export function PredictionPanel() {
  const navigate = useNavigate();
  const [drugId, setDrugId]         = useState('');
  const [drugSearch, setDrugSearch] = useState('');
  const [drugSuggestions, setDrugSuggestions] = useState<DrugSummary[]>([]);
  const [data, setData]             = useState<LinkPredictionResponse | null>(null);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState('');
  const searchDebounce = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  React.useEffect(() => {
    if (!drugSearch.trim() || drugSearch.length < 2) { setDrugSuggestions([]); return; }
    if (searchDebounce.current) clearTimeout(searchDebounce.current);
    searchDebounce.current = setTimeout(() => {
      drugsApi.list({ search: drugSearch, page: 1 })
        .then(res => setDrugSuggestions(res.data.results.slice(0, 6)))
        .catch(() => {});
    }, 350);
  }, [drugSearch]);

  const selectDrug = (drug: DrugSummary) => {
    const rawId = drug['drugbank-id'];
    let dbId = '';
    if (Array.isArray(rawId)) {
      const primary = rawId.find((x: any) => typeof x === 'object' && x?.primary) || rawId[0];
      dbId = primary && typeof primary === 'object' ? primary.value : String(primary);
    } else if (rawId && typeof rawId === 'object' && 'value' in rawId) {
      dbId = (rawId as any).value;
    } else if (rawId) {
      dbId = String(rawId);
    }
    setDrugId(dbId || drug._id);
    setDrugSearch(drug.name);
    setDrugSuggestions([]);
  };

  const run = (e: React.FormEvent) => {
    e.preventDefault();
    if (!drugId.trim()) { setError('Ingresa un DrugBank ID o selecciona un fármaco.'); return; }
    setLoading(true); setError(''); setData(null);
    gdsApi.predictForDrug(drugId.trim(), { top_n: 25, method: 'adamic_adar' })
      .then((res) => setData(res.data))
      .catch((err) => setError(err?.response?.data?.error || 'Error en la predicción.'))
      .finally(() => setLoading(false));
  };

  const maxScore = data?.predictions[0]?.score ?? 1;

  // Grafo: fármaco central + targets predichos (aristas dashed = sugeridas)
  const { cyNodes, cyEdges } = React.useMemo(() => {
    if (!data) return { cyNodes: [] as CyNode[], cyEdges: [] as CyEdge[] };
    const center: CyNode = { id: data.drugbank_id, label: data.drug_name, kind: 'drug', weight: 4 };
    const targetNodes: CyNode[] = data.predictions.map((p) => ({
      id: p.target_id, label: p.target_name || p.target_id, kind: 'predicted',
      weight: 1 + p.score,
    }));
    const edges: CyEdge[] = data.predictions.map((p) => ({
      id: `${data.drugbank_id}-${p.target_id}`,
      source: data.drugbank_id, target: p.target_id, style: 'dashed',
    }));
    return { cyNodes: [center, ...targetNodes], cyEdges: edges };
  }, [data]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <p style={{ color: '#78716c', fontSize: '0.88rem', margin: 0 }}>
        Sugiere dianas a las que un fármaco <em>podría</em> unirse según la topología
        de la red (Adamic-Adar), aunque no estén documentadas. Es repurposing in silico:
        dianas en el mismo vecindario que las dianas conocidas del fármaco.
      </p>

      <form onSubmit={run} style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', flex: '1 1 200px' }}>
          <div style={{ position: 'relative' }}>
            <input
              value={drugSearch}
              onChange={e => { setDrugSearch(e.target.value); setDrugId(''); }}
              placeholder="Buscar fármaco por nombre…"
              style={{
                background: '#f3ece0', border: '1px solid #bcae98', color: '#1c1917',
                padding: '9px 14px', borderRadius: '8px', fontSize: '0.85rem',
                outline: 'none', width: '100%', boxSizing: 'border-box',
              }}
            />
            {drugSuggestions.length > 0 && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 50,
                background: '#f3ece0', border: '1px solid #bcae98', borderRadius: '0 0 8px 8px',
                boxShadow: '0 4px 20px #000a',
              }}>
                {drugSuggestions.map(d => (
                  <div key={d._id} onClick={() => selectDrug(d)}
                    style={{ padding: '8px 14px', cursor: 'pointer', color: '#1c1917', fontSize: '0.85rem', borderBottom: '1px solid #d6ccbb' }}
                    onMouseEnter={e => (e.currentTarget.style.background = '#d6ccbb')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  >
                    {d.name}
                  </div>
                ))}
              </div>
            )}
          </div>
          {drugId && (
            <div style={{ fontSize: '0.75rem', color: '#f59e0b', fontFamily: 'monospace' }}>
              ID: {drugId}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', flex: '1 1 200px' }}>
          <input
            value={drugId}
            onChange={e => { setDrugId(e.target.value); setDrugSearch(''); }}
            placeholder="o DrugBank ID directo — ej. DB00001"
            style={{
              background: '#f3ece0', border: '1px solid #bcae98', color: '#1c1917',
              padding: '9px 14px', borderRadius: '8px', fontSize: '0.85rem', fontFamily: 'monospace',
              outline: 'none', width: '100%', boxSizing: 'border-box',
            }}
          />
        </div>
        <button type="submit" disabled={loading} style={{
          padding: '9px 20px', borderRadius: '8px', fontSize: '0.85rem', fontWeight: 700, cursor: 'pointer',
          border: 'none', background: loading ? '#bcae98' : '#2d2621', color: '#fff',
          alignSelf: 'flex-start',
        }}>
          {loading ? 'Prediciendo…' : 'Predecir Dianas'}
        </button>
      </form>

      {error && <ErrorBox msg={error} isGdsError={false} />}

      {data && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
            <div style={{ color: '#57534e', fontSize: '0.85rem' }}>
              <strong style={{ color: '#fde68a' }}>{data.drug_name}</strong> tiene{' '}
              {data.current_target_count} dianas documentadas ·{' '}
              {data.predictions.length} sugerencias nuevas
            </div>
            <button
              onClick={() => downloadCsv(
                `prediction_${data.drugbank_id}.csv`,
                ['rank', 'target_id', 'target_name', 'uniprot_id', 'organism', 'score', 'shared_via_drugs'],
                data.predictions.map((p, i) => [
                  i + 1, p.target_id, p.target_name || '', p.uniprot_id || '',
                  p.organism || '', p.score.toFixed(4), p.shared_via_drugs,
                ])
              )}
              style={exportBtnStyle}
            >
              ⬇ Exportar CSV
            </button>
          </div>

          {cyNodes.length > 1 && (
            <CytoscapeGraph nodes={cyNodes} edges={cyEdges} height={420} layout="cose"
              onNodeClick={(n) => { if (n.kind === 'drug') navigate(`/drugs/${n.id}`); }}
            />
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {data.predictions.map((p, idx) => (
              <div key={p.target_id} style={{
                display: 'flex', alignItems: 'center', gap: '12px',
                background: '#f3ece0', border: '1px solid #d6ccbb', borderLeft: '3px solid #fbbf24',
                borderRadius: '8px', padding: '10px 14px',
              }}>
                <span style={{ color: '#a8a29e', fontFamily: 'monospace', fontSize: '0.8rem', minWidth: '28px' }}>#{idx + 1}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ color: '#1c1917', fontSize: '0.86rem', fontWeight: 600 }}>{p.target_name || p.target_id}</div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <span style={{ color: '#38bdf8', fontSize: '0.7rem', fontFamily: 'monospace' }}>{p.target_id}</span>
                    {p.uniprot_id && <span style={{ color: '#a78bfa', fontSize: '0.7rem', fontFamily: 'monospace' }}>{p.uniprot_id}</span>}
                    {p.organism && <span style={{ color: '#78716c', fontSize: '0.7rem', fontStyle: 'italic' }}>{p.organism}</span>}
                    <span style={{ color: '#78350f', fontSize: '0.7rem' }}>vía {p.shared_via_drugs} fármacos puente</span>
                  </div>
                </div>
                <ScoreBar value={p.score} max={maxScore} color="#fbbf24" />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
