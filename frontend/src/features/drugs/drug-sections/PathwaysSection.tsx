/**
 * PathwaysSection.tsx
 *
 * Pestaña "Rutas y Efectos" del perfil de un fármaco. Muestra tres capas:
 *   1. Efecto DIRECTO   — targets que el fármaco toca (desde Neo4j)
 *   2. Efecto INDIRECTO — vecinos PPI de esos targets (STRING)
 *   3. Rutas afectadas  — vías biológicas KEGG donde caen los targets
 *
 * Las APIs externas (STRING/KEGG) pueden tardar varios segundos; por eso
 * el componente carga bajo demanda (cuando se abre la pestaña) y muestra
 * estados parciales si una de las dos fuentes falla.
 */

import React, { useState, useEffect } from 'react';
import {
  pathwaysApi,
  DrugPathwaysResponse,
  StringNeighbor,
  KeggPathway,
} from '../../../api/pathways';
import CytoscapeGraph, { CyNode, CyEdge } from '../../../components/CytoscapeGraph';

interface Props {
  /** DrugBank ID del fármaco (DB00001). */
  drugId: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function scoreColor(score: number): string {
  if (score >= 0.9) return '#15803d';
  if (score >= 0.7) return '#4d7c0f';
  if (score >= 0.5) return '#92400e';
  return '#9a3412';
}

function SubTabButton({ active, onClick, label, count }: {
  active: boolean; onClick: () => void; label: string; count?: number;
}) {
  return (
    <button onClick={onClick} style={{
      padding: '8px 14px', borderRadius: '6px', fontSize: '0.82rem', fontWeight: 600,
      cursor: 'pointer',
      background: active ? '#2d2621' : '#faf6ee', color: active ? '#faf6ee' : '#57534e', border: '1px solid #bcae98',
    }}>
      {label}{count !== undefined && <span style={{ opacity: 0.7 }}> ({count})</span>}
    </button>
  );
}

// ── Componente ───────────────────────────────────────────────────────────────

type SubTab = 'direct' | 'indirect' | 'kegg';

export default function PathwaysSection({ drugId }: Props) {
  const [data, setData]       = useState<DrugPathwaysResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [subTab, setSubTab]   = useState<SubTab>('direct');

  useEffect(() => {
    setLoading(true);
    setError('');
    pathwaysApi
      .forDrug(drugId, { include: 'string,kegg' })
      .then((res) => setData(res.data))
      .catch((err) => setError(err?.response?.data?.error || 'No se pudieron cargar las rutas.'))
      .finally(() => setLoading(false));
  }, [drugId]);

  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: '#6366f1' }}>
        Consultando targets, STRING y KEGG… (puede tardar unos segundos)
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        padding: '24px', background: '#1a0a0a', border: '1px solid #7f1d1d',
        borderRadius: '10px', color: '#fca5a5', textAlign: 'center',
      }}>
        ⚠ {error}
      </div>
    );
  }

  if (!data) return null;

  const direct   = data.direct_targets;
  const indirect = data.indirect;
  const kegg     = data.pathways;

  // Grafo combinado directo + indirecto para la sub-pestaña "indirect"
  const buildIndirectGraph = (): { nodes: CyNode[]; edges: CyEdge[] } => {
    if (!indirect) return { nodes: [], edges: [] };
    const nodes: CyNode[] = [];
    const seen = new Set<string>();

    // Genes directos (targets)
    indirect.direct_genes.forEach((g) => {
      if (!seen.has(g)) {
        seen.add(g);
        nodes.push({ id: g, label: g, kind: 'target', weight: 2.5 });
      }
    });
    // Vecinos indirectos
    indirect.neighbors.forEach((n) => {
      if (!seen.has(n.partner_protein)) {
        seen.add(n.partner_protein);
        nodes.push({
          id: n.partner_protein,
          label: n.partner_protein,
          kind: 'predicted',
          weight: 1 + n.max_score,
        });
      }
    });
    const edges: CyEdge[] = indirect.edges
      .filter(e => seen.has(e.source) && seen.has(e.target))
      .map((e, idx) => ({
        id: `${e.source}-${e.target}-${idx}`,
        source: e.source,
        target: e.target,
        style: 'dashed',
      }));
    return { nodes, edges };
  };

  const indirectGraph = subTab === 'indirect' ? buildIndirectGraph() : { nodes: [], edges: [] };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Avisos */}
      {data.notes.length > 0 && (
        <div style={{
          background: '#f3ece0', border: '1px solid #cdd9e6', borderRadius: '8px',
          padding: '10px 14px', fontSize: '0.78rem', color: '#78716c',
        }}>
          {data.notes.map((n, i) => <div key={i}>ℹ {n}</div>)}
        </div>
      )}

      {/* Sub-pestañas */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <SubTabButton active={subTab === 'direct'}   onClick={() => setSubTab('direct')}   label="🎯 Efecto directo" count={direct.length} />
        <SubTabButton active={subTab === 'indirect'} onClick={() => setSubTab('indirect')} label="🔗 Efecto indirecto (STRING)" count={indirect?.neighbors.length} />
        <SubTabButton active={subTab === 'kegg'}     onClick={() => setSubTab('kegg')}     label="🗺️ Rutas (KEGG)" count={kegg?.pathway_count} />
      </div>

      {/* ── EFECTO DIRECTO ─────────────────────────────────────────────── */}
      {subTab === 'direct' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <p style={{ color: '#78716c', fontSize: '0.85rem', margin: '0 0 4px 0' }}>
            Proteínas que el fármaco toca directamente, según DrugBank.
          </p>
          {direct.length === 0 ? (
            <div style={{ color: '#57534e', padding: '20px', textAlign: 'center' }}>
              Sin targets directos registrados.
            </div>
          ) : direct.map((t) => (
            <div key={t.drugbank_target_id} style={{
              background: '#f3ece0', border: '1px solid #d6ccbb', borderLeft: '3px solid #38bdf8',
              borderRadius: '8px', padding: '10px 14px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                <span style={{ color: '#1c1917', fontWeight: 600, fontSize: '0.9rem' }}>{t.name}</span>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  {t.rel_types.map((rt) => (
                    <span key={rt} style={{
                      background: '#312e81', color: '#a5b4fc', padding: '2px 8px',
                      borderRadius: '4px', fontSize: '0.7rem', fontFamily: 'monospace',
                    }}>{rt}</span>
                  ))}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginTop: '4px' }}>
                {t.gene_name && <span style={{ color: '#78716c', fontSize: '0.72rem' }}>gen: {t.gene_name}</span>}
                {t.uniprot_id && (
                  <a href={`https://www.uniprot.org/uniprotkb/${t.uniprot_id}`} target="_blank" rel="noopener noreferrer"
                     style={{ color: '#6d28d9', fontSize: '0.72rem', fontFamily: 'monospace', textDecoration: 'none' }}>
                    {t.uniprot_id} ↗
                  </a>
                )}
                {t.organism && <span style={{ color: '#78716c', fontSize: '0.72rem', fontStyle: 'italic' }}>{t.organism}</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── EFECTO INDIRECTO (STRING) ──────────────────────────────────── */}
      {subTab === 'indirect' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <p style={{ color: '#78716c', fontSize: '0.85rem', margin: 0 }}>
            Proteínas que interactúan con los targets directos (red PPI de STRING).
            El fármaco las afecta indirectamente a través de esas interacciones.
          </p>
          {!indirect || indirect.neighbors.length === 0 ? (
            <div style={{ color: '#57534e', padding: '20px', textAlign: 'center' }}>
              Sin vecinos PPI encontrados (o STRING no disponible).
            </div>
          ) : (
            <>
              <CytoscapeGraph nodes={indirectGraph.nodes} edges={indirectGraph.edges} height={420} layout="cose" />
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {indirect.neighbors.map((n: StringNeighbor) => (
                  <div key={n.partner_protein} style={{
                    display: 'flex', alignItems: 'center', gap: '12px',
                    background: '#f3ece0', border: '1px solid #d6ccbb', borderRadius: '8px', padding: '8px 12px',
                  }}>
                    <span style={{ color: '#fde68a', fontWeight: 600, fontSize: '0.85rem', minWidth: '90px' }}>
                      {n.partner_protein}
                    </span>
                    <span style={{ color: '#78716c', fontSize: '0.74rem', flex: 1 }}>
                      conecta con {n.connected_to.join(', ')}
                    </span>
                    <span style={{
                      color: scoreColor(n.max_score), fontFamily: 'monospace', fontSize: '0.78rem', fontWeight: 700,
                    }}>
                      {n.max_score.toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
              {indirect.network_image_url && (
                <details style={{ marginTop: '4px' }}>
                  <summary style={{ color: '#78716c', fontSize: '0.78rem', cursor: 'pointer' }}>
                    Ver imagen de red oficial de STRING
                  </summary>
                  <img src={indirect.network_image_url} alt="STRING network"
                       style={{ maxWidth: '100%', marginTop: '8px', borderRadius: '8px', background: '#fff' }} />
                </details>
              )}
            </>
          )}
        </div>
      )}

      {/* ── RUTAS (KEGG) ──────────────────────────────────────────────── */}
      {subTab === 'kegg' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <p style={{ color: '#78716c', fontSize: '0.85rem', margin: '0 0 4px 0' }}>
            Vías biológicas de KEGG donde participan los targets del fármaco.
            Más targets en una ruta = mayor impacto del fármaco sobre ese proceso.
          </p>
          {!kegg || kegg.pathways.length === 0 ? (
            <div style={{ color: '#57534e', padding: '20px', textAlign: 'center' }}>
              Sin rutas KEGG mapeadas (o KEGG no disponible).
            </div>
          ) : (
            <>
              {kegg.pathways.map((p: KeggPathway) => {
                const pid = p.pathway_id.replace('path:', '');
                return (
                  <div key={p.pathway_id} style={{
                    background: '#f3ece0', border: '1px solid #d6ccbb', borderLeft: '3px solid #10b981',
                    borderRadius: '8px', padding: '10px 14px',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                      <a href={`https://www.kegg.jp/pathway/${pid}`} target="_blank" rel="noopener noreferrer"
                         style={{ color: '#6ee7b7', fontWeight: 600, fontSize: '0.88rem', textDecoration: 'none' }}>
                        {p.name} ↗
                      </a>
                      <span style={{
                        background: '#042f2e', color: '#5eead4', border: '1px solid #134e4a',
                        padding: '2px 10px', borderRadius: '12px', fontSize: '0.72rem', fontWeight: 700,
                      }}>
                        {p.target_count} target{p.target_count !== 1 ? 's' : ''}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '6px' }}>
                      <span style={{ color: '#57534e', fontSize: '0.72rem', fontFamily: 'monospace' }}>{pid}</span>
                      {p.targets.map((t) => (
                        <span key={t} style={{
                          background: '#d6ccbb', color: '#57534e', padding: '1px 7px',
                          borderRadius: '4px', fontSize: '0.7rem',
                        }}>{t}</span>
                      ))}
                    </div>
                  </div>
                );
              })}
              {kegg.unmapped_targets.length > 0 && (
                <div style={{ color: '#57534e', fontSize: '0.74rem', marginTop: '4px' }}>
                  Sin mapeo KEGG: {kegg.unmapped_targets.join(', ')}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
