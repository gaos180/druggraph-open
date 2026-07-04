import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  targetsApi, TargetDetail, UniProtDetails,
  TargetPathwaysResponse, TargetPathwaysStringNeighbor,
} from '../../api/targets';
import CytoscapeGraph, { CyNode, CyEdge } from '../../components/CytoscapeGraph';

// ── SwissBioPics ──────────────────────────────────────────────────────────────
function SwissBioPicsPanel({ slIds, taxId = '9606' }: { slIds: string[]; taxId?: string }) {
  const valid = slIds.filter(id => /^SL-\d+$/.test(id));
  const [err, setErr] = useState(false);

  if (!valid.length || err) return null;

  // Usar el endpoint SVG directamente en lugar del web component,
  // así onError maneja cualquier fallo del servidor limpiamente.
  const src = `https://www.swissbiopics.org/api/locations/${valid.join(',')}.svg?taxid=${taxId}`;

  return (
    <div style={{
      background: '#050d1a', border: '1px solid #d6ccbb',
      borderRadius: '8px', padding: '10px', overflow: 'hidden', marginTop: '4px',
    }}>
      <div style={{ fontSize: '0.72rem', color: '#a8a29e', marginBottom: '6px' }}>
        🗺️ Localización Subcelular (SwissBioPics)
      </div>
      <img
        src={src}
        alt="Localización subcelular — SwissBioPics / UniProt"
        onError={() => setErr(true)}
        style={{ maxWidth: '100%', display: 'block' }}
      />
    </div>
  );
}

// ── UniProt panel ─────────────────────────────────────────────────────────────
const GO_ASPECT: Record<string, string> = {
  P: '🔬 Proceso Biológico', F: '⚙️ Función Molecular', C: '🏛️ Componente Celular',
};

export function UniProtTab({ targetId, uniprotId }: { targetId: string; uniprotId: string }) {
  const [data, setData]       = useState<UniProtDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr]         = useState('');
  const [goFilter, setGoFilter] = useState<'ALL'|'P'|'F'|'C'>('ALL');

  useEffect(() => {
    if (!targetId || !uniprotId) return;
    setLoading(true); setErr('');
    targetsApi.uniprot(targetId)
      .then(r  => setData(r.data))
      .catch(e => setErr(e?.response?.data?.error ?? 'Error al obtener datos de UniProt'))
      .finally(() => setLoading(false));
  }, [targetId, uniprotId]);

  if (!uniprotId) return (
    <div style={{ color: '#57534e', textAlign: 'center', padding: '40px' }}>
      Este target no tiene UniProt ID registrado.
    </div>
  );
  if (loading) return (
    <div style={{ padding: '40px', textAlign: 'center', color: '#78716c' }}>
      Consultando UniProt…
    </div>
  );
  if (err) return (
    <div style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid #7f1d1d',
      borderRadius: '8px', padding: '16px', color: '#f87171' }}>
      {err}
    </div>
  );
  if (!data) return null;

  const slIds       = data.subcellular_locations.map(l => l.sl_id).filter(Boolean);
  const filteredGo  = goFilter === 'ALL' ? data.go_terms : data.go_terms.filter(g => g.aspect === goFilter);

  const infoBox = (label: string, value: string) => !value ? null : (
    <div style={{ background: '#d6ccbb', borderRadius: '8px', padding: '12px 16px' }}>
      <div style={{ fontSize: '0.72rem', color: '#78716c', marginBottom: '4px', fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: '0.84rem', color: '#292524', lineHeight: 1.6 }}>{value}</div>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      {/* Header */}
      <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
        {data.reviewed && (
          <span style={{ fontSize: '0.73rem', fontWeight: 700, color: '#facc15',
            background: 'rgba(250,204,21,0.12)', border: '1px solid rgba(250,204,21,0.3)',
            padding: '2px 8px', borderRadius: '4px' }}>
            ⭐ Swiss-Prot revisado
          </span>
        )}
        <a href={`https://www.uniprot.org/uniprotkb/${uniprotId}`} target="_blank" rel="noopener noreferrer"
          style={{ fontSize: '0.82rem', color: '#00D4FF', textDecoration: 'none' }}>
          {uniprotId} ↗
        </a>
        {data.sequence.length > 0 && (
          <span style={{ fontSize: '0.8rem', color: '#78716c' }}>
            {data.sequence.length} aa · {(data.sequence.mass / 1000).toFixed(1)} kDa
          </span>
        )}
        {data.gene_names.length > 0 && (
          <code style={{ fontSize: '0.8rem', color: '#0284c7', background: '#eef5fb',
            padding: '2px 8px', borderRadius: '4px' }}>
            {data.gene_names.join(' / ')}
          </code>
        )}
      </div>

      {infoBox('Nombre de proteína', data.protein_name)}
      {infoBox('Función molecular', data.function)}
      {infoBox('Regulación de actividad', data.activity_regulation)}
      {infoBox('Estructura de subunidades', data.subunit)}
      {infoBox('Modificaciones post-traduccionales', data.ptm)}

      {/* Localización subcelular */}
      {data.subcellular_locations.length > 0 && (
        <div style={{ background: '#eef5fb', border: '1px solid #1e4070', borderRadius: '8px', padding: '12px 16px' }}>
          <div style={{ fontSize: '0.72rem', color: '#78716c', marginBottom: '8px', fontWeight: 600 }}>
            📍 Localización Subcelular
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '10px' }}>
            {data.subcellular_locations.map((loc, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                background: '#f3ece0', border: '1px solid #cdd9e6',
                borderRadius: '6px', padding: '5px 10px',
              }}>
                <span style={{ fontSize: '1.1rem' }}>{loc.icon}</span>
                <div>
                  <div style={{ color: '#1d4ed8', fontSize: '0.84rem', fontWeight: 500 }}>{loc.value}</div>
                  {loc.topology && (
                    <div style={{ color: '#57534e', fontSize: '0.72rem' }}>{loc.topology}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
          <SwissBioPicsPanel slIds={slIds} taxId={String(data.organism.taxon_id || 9606)} />
        </div>
      )}

      {/* GO terms */}
      {data.go_terms.length > 0 && (
        <div>
          <div style={{ display: 'flex', gap: '6px', marginBottom: '8px', flexWrap: 'wrap' }}>
            {(['ALL', 'P', 'F', 'C'] as const).map(k => (
              <button key={k} onClick={() => setGoFilter(k)} style={{
                padding: '3px 10px', fontSize: '0.75rem', borderRadius: '6px', cursor: 'pointer',
                fontWeight: 600, border: '1px solid #bcae98',
                background: goFilter === k ? '#2d2621' : '#faf6ee', color: goFilter === k ? '#faf6ee' : '#57534e',
              }}>
                {k === 'ALL' ? 'Todos' : GO_ASPECT[k]}
              </button>
            ))}
          </div>
          <div style={{ maxHeight: '240px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {filteredGo.map((g, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <a href={`https://www.ebi.ac.uk/QuickGO/term/${g.id}`} target="_blank" rel="noopener noreferrer"
                  style={{ fontSize: '0.72rem', color: '#78716c', fontFamily: 'monospace', textDecoration: 'none' }}>
                  {g.id}
                </a>
                <span style={{ fontSize: '0.82rem', color: '#57534e' }}>{g.term}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Secuencia */}
      {data.sequence.first_50 && (
        <div style={{ background: '#d6ccbb', borderRadius: '8px', padding: '12px 16px' }}>
          <div style={{ fontSize: '0.72rem', color: '#78716c', marginBottom: '6px' }}>
            Secuencia (primeros 50 aa de {data.sequence.length})
          </div>
          <code style={{ fontSize: '0.78rem', color: '#15803d', letterSpacing: '0.05em', wordBreak: 'break-all' }}>
            {data.sequence.first_50}…
          </code>
          {data.pdb_ids.length > 0 && (
            <div style={{ marginTop: '8px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {data.pdb_ids.map(pdb => (
                <a key={pdb} href={`https://www.rcsb.org/structure/${pdb}`} target="_blank" rel="noopener noreferrer"
                  style={{ fontSize: '0.72rem', color: '#6d28d9', fontFamily: 'monospace',
                    background: 'rgba(109,40,217,0.08)', border: '1px solid rgba(109,40,217,0.2)',
                    padding: '2px 6px', borderRadius: '4px', textDecoration: 'none' }}>
                  PDB:{pdb}
                </a>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Keywords */}
      {data.keywords.length > 0 && (
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {data.keywords.map(kw => (
            <span key={kw} style={{ fontSize: '0.72rem', color: '#78716c',
              background: '#d6ccbb', border: '1px solid #bcae98',
              padding: '2px 8px', borderRadius: '12px' }}>{kw}</span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Red de Fármacos ───────────────────────────────────────────────────────────
export function NetworkTab({ target }: { target: TargetDetail }) {
  const navigate   = useNavigate();
  const validDrugs = target.drugs.filter(d => d.drugbank_id);

  const nodes: CyNode[] = [
    { id: target.id, label: target.name, kind: 'target', weight: 4 },
    ...validDrugs.map(d => ({
      id:     d.drugbank_id,
      label:  d.drug_name,
      kind:   'drug' as const,
      weight: 2,
      meta:   { drugbank_id: d.drugbank_id },
    })),
  ];

  const edges: CyEdge[] = validDrugs.map((d, i) => ({
    id:     `${d.drugbank_id}-${target.id}-${i}`,
    source: d.drugbank_id,
    target: target.id,
    label:  d.rel_type,
  }));

  if (validDrugs.length === 0) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: '#57534e' }}>
        No hay fármacos vinculados a esta diana en el grafo.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <p style={{ margin: 0, color: '#78716c', fontSize: '0.88rem' }}>
        {validDrugs.length} fármaco{validDrugs.length !== 1 ? 's' : ''} interactúan con esta diana.
        Haz clic derecho sobre un nodo para ver más opciones.
      </p>
      <CytoscapeGraph
        nodes={nodes}
        edges={edges}
        height={520}
        layout="cose"
        onNodeClick={n => { if (n.kind === 'drug' && n.meta?.drugbank_id) navigate(`/drugs/${n.meta.drugbank_id}`); }}
      />
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
        gap: '8px',
      }}>
        {validDrugs.map(d => (
          <div key={d.drugbank_id} onClick={() => navigate(`/drugs/${d.drugbank_id}`)}
            style={{
              background: '#f3ece0', border: '1px solid #d6ccbb', borderLeft: '3px solid #6366f1',
              borderRadius: '8px', padding: '10px 14px', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = '#d6ccbb')}
            onMouseLeave={e => (e.currentTarget.style.background = '#f3ece0')}
          >
            <div>
              <div style={{ color: '#292524', fontSize: '0.88rem', fontWeight: 500 }}>{d.drug_name}</div>
              <code style={{ fontSize: '0.72rem', color: '#57534e' }}>{d.drugbank_id}</code>
            </div>
            <span style={{
              background: '#312e81', color: '#a5b4fc', padding: '2px 8px',
              borderRadius: '4px', fontSize: '0.7rem', fontFamily: 'monospace', whiteSpace: 'nowrap',
            }}>
              {d.rel_type}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Vecino STRING expandible ──────────────────────────────────────────────────
function ExpandableNeighbor({ neighbor }: { neighbor: TargetPathwaysStringNeighbor }) {
  const [expanded, setExpanded] = useState(false);
  const [pathways, setPathways] = useState<{ pathway_id: string; name: string }[] | null>(null);
  const [loading, setLoading]   = useState(false);

  const toggle = () => {
    if (!expanded && pathways === null) {
      setLoading(true);
      targetsApi.keggGene(neighbor.partner_protein)
        .then(r => setPathways(r.data.pathways))
        .catch(() => setPathways([]))
        .finally(() => setLoading(false));
    }
    setExpanded(e => !e);
  };

  const score = neighbor.max_score;
  const scoreColor = score >= 0.9 ? '#15803d' : score >= 0.7 ? '#4d7c0f' : score >= 0.5 ? '#92400e' : '#9a3412';

  return (
    <div style={{
      background: '#f3ece0', border: '1px solid #d6ccbb', borderRadius: '8px', overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 14px', cursor: 'pointer',
      }} onClick={toggle}>
        <span style={{ color: '#78350f', fontWeight: 600, fontSize: '0.88rem', flex: 1 }}>
          {neighbor.partner_protein}
        </span>
        <span style={{ fontSize: '0.74rem', color: '#78716c', flex: 2 }}>
          vía {neighbor.connected_to.slice(0, 3).join(', ')}{neighbor.connected_to.length > 3 ? '…' : ''}
        </span>
        <span style={{ color: scoreColor, fontFamily: 'monospace', fontSize: '0.8rem', fontWeight: 700 }}>
          {score.toFixed(2)}
        </span>
        <button style={{
          background: 'none', border: '1px solid #bcae98', color: '#78716c',
          borderRadius: '4px', padding: '2px 8px', cursor: 'pointer', fontSize: '0.72rem',
        }}>
          {loading ? '…' : expanded ? '▲ ocultar' : '🧬 Ver rutas'}
        </button>
      </div>

      {expanded && (
        <div style={{
          borderTop: '1px solid #d6ccbb', padding: '10px 14px 12px 28px',
          background: '#050d1a',
        }}>
          {loading ? (
            <span style={{ color: '#78716c', fontSize: '0.8rem' }}>Consultando KEGG…</span>
          ) : !pathways || pathways.length === 0 ? (
            <span style={{ color: '#a8a29e', fontSize: '0.8rem' }}>
              Sin rutas KEGG mapeadas para {neighbor.partner_protein}
            </span>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {pathways.map(p => {
                const pid = p.pathway_id.replace('path:', '');
                return (
                  <a key={p.pathway_id}
                    href={`https://www.kegg.jp/pathway/${pid}`} target="_blank" rel="noopener noreferrer"
                    style={{
                      fontSize: '0.8rem', color: '#6ee7b7', textDecoration: 'none',
                      display: 'flex', gap: '8px', alignItems: 'center',
                    }}>
                    <span style={{ color: '#bcae98', fontSize: '0.68rem', fontFamily: 'monospace' }}>{pid}</span>
                    <span>{p.name}</span>
                    <span style={{ fontSize: '0.7rem', color: '#bcae98' }}>↗</span>
                  </a>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Rutas & PPI ───────────────────────────────────────────────────────────────
type PathSubTab = 'kegg' | 'ppi';

export function PathwaysTab({ targetId }: { targetId: string }) {
  const [data, setData]       = useState<TargetPathwaysResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [subTab, setSubTab]   = useState<PathSubTab>('kegg');

  useEffect(() => {
    setLoading(true); setError('');
    targetsApi.pathways(targetId)
      .then(r => setData(r.data))
      .catch(e => setError(e?.response?.data?.error ?? 'Error al cargar rutas'))
      .finally(() => setLoading(false));
  }, [targetId]);

  if (loading) return (
    <div style={{ padding: '40px', textAlign: 'center', color: '#4338ca', fontSize: '0.9rem' }}>
      Consultando KEGG y STRING… (puede tardar varios segundos)
    </div>
  );
  if (error) return (
    <div style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid #7f1d1d',
      borderRadius: '8px', padding: '16px', color: '#f87171' }}>
      ⚠ {error}
    </div>
  );
  if (!data) return null;

  const kegg = data.pathways;
  const ppi  = data.indirect;

  // Grafo PPI
  const ppiNodes: CyNode[] = [];
  const ppiEdges: CyEdge[] = [];
  if (ppi) {
    ppi.direct_genes.forEach(g => {
      ppiNodes.push({ id: g, label: g, kind: 'target', weight: 2.5 });
    });
    ppi.neighbors.forEach(n => {
      if (!ppiNodes.find(x => x.id === n.partner_protein)) {
        ppiNodes.push({ id: n.partner_protein, label: n.partner_protein, kind: 'predicted', weight: 1 + n.max_score });
      }
    });
    const nodeIds = new Set(ppiNodes.map(n => n.id));
    ppi.edges.forEach((e, i) => {
      if (nodeIds.has(e.source) && nodeIds.has(e.target)) {
        ppiEdges.push({ id: `ppi-${i}`, source: e.source, target: e.target, style: 'dashed' });
      }
    });
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {data.notes.length > 0 && (
        <div style={{ background: '#f3ece0', border: '1px solid #cdd9e6', borderRadius: '8px',
          padding: '10px 14px', fontSize: '0.78rem', color: '#78716c' }}>
          {data.notes.map((n, i) => <div key={i}>ℹ {n}</div>)}
        </div>
      )}

      {/* Sub-tabs */}
      <div style={{ display: 'flex', gap: '8px' }}>
        <button onClick={() => setSubTab('kegg')} style={{
          padding: '8px 16px', borderRadius: '6px', fontSize: '0.83rem', fontWeight: 600,
          cursor: 'pointer', border: '1px solid #bcae98',
          background: subTab === 'kegg' ? '#2d2621' : '#faf6ee', color: subTab === 'kegg' ? '#faf6ee' : '#57534e',
        }}>
          🗺️ Rutas KEGG {kegg ? `(${kegg.pathway_count})` : ''}
        </button>
        <button onClick={() => setSubTab('ppi')} style={{
          padding: '8px 16px', borderRadius: '6px', fontSize: '0.83rem', fontWeight: 600,
          cursor: 'pointer', border: '1px solid #bcae98',
          background: subTab === 'ppi' ? '#2d2621' : '#faf6ee', color: subTab === 'ppi' ? '#faf6ee' : '#57534e',
        }}>
          🔗 Efecto Indirecto — PPI (STRING) {ppi ? `(${ppi.neighbors.length})` : ''}
        </button>
      </div>

      {/* ── KEGG ──────────────────────────────────────────────────────── */}
      {subTab === 'kegg' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <p style={{ margin: '0 0 4px 0', color: '#78716c', fontSize: '0.85rem' }}>
            Vías biológicas de KEGG donde participa esta diana según su gen / UniProt.
          </p>
          {!kegg || kegg.pathways.length === 0 ? (
            <div style={{ color: '#57534e', padding: '20px', textAlign: 'center' }}>
              Sin rutas KEGG mapeadas para este target.
            </div>
          ) : kegg.pathways.map(p => {
            const pid = p.pathway_id.replace('path:', '');
            return (
              <div key={p.pathway_id} style={{
                background: '#f3ece0', border: '1px solid #d6ccbb',
                borderLeft: '3px solid #10b981', borderRadius: '8px', padding: '10px 14px',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
                  <a href={`https://www.kegg.jp/pathway/${pid}`} target="_blank" rel="noopener noreferrer"
                    style={{ color: '#065f46', fontWeight: 600, fontSize: '0.88rem', textDecoration: 'none' }}>
                    {p.name} ↗
                  </a>
                  <span style={{ background: '#042f2e', color: '#5eead4', border: '1px solid #134e4a',
                    padding: '2px 10px', borderRadius: '12px', fontSize: '0.72rem', fontWeight: 700,
                    whiteSpace: 'nowrap' }}>
                    {p.target_count} diana{p.target_count !== 1 ? 's' : ''}
                  </span>
                </div>
                <span style={{ color: '#78716c', fontSize: '0.7rem', fontFamily: 'monospace' }}>{pid}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* ── PPI STRING ────────────────────────────────────────────────── */}
      {subTab === 'ppi' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <p style={{ margin: 0, color: '#78716c', fontSize: '0.85rem' }}>
            Proteínas que interactúan con esta diana en la red PPI (STRING).
            Expande cada vecino para ver en qué rutas KEGG participa — efecto indirecto del fármaco.
          </p>

          {!ppi || ppi.neighbors.length === 0 ? (
            <div style={{ color: '#57534e', padding: '20px', textAlign: 'center' }}>
              Sin vecinos PPI encontrados para esta diana.
            </div>
          ) : (
            <>
              {ppiNodes.length > 0 && (
                <CytoscapeGraph nodes={ppiNodes} edges={ppiEdges} height={400} layout="cose" />
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {ppi.neighbors.map(n => (
                  <ExpandableNeighbor key={n.partner_protein} neighbor={n} />
                ))}
              </div>

              {ppi.network_image_url && (
                <details style={{ marginTop: '4px' }}>
                  <summary style={{ color: '#78716c', fontSize: '0.78rem', cursor: 'pointer' }}>
                    Ver imagen de red oficial de STRING
                  </summary>
                  <img src={ppi.network_image_url} alt="STRING PPI"
                    style={{ maxWidth: '100%', marginTop: '8px', borderRadius: '8px', background: '#fff' }} />
                </details>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
