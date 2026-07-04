/**
 * GraphInteractionsSection.tsx
 * Pestaña "Red Molecular" en DrugDetailPage.
 *
 * Muestra las interacciones Drug→Target obtenidas de Neo4j organizadas por
 * tipo de relación, las categorías farmacológicas y las interacciones DDI.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { drugsApi, DrugGraphResponse, DrugSummary, GraphInteraction } from '../../../api/drugs';
import CytoscapeGraph, { CyNode, CyEdge } from '../../../components/CytoscapeGraph';

// ── Paleta semántica por tipo de relación ──────────────────────────────────

const REL_META: Record<string, { label: string; color: string; bg: string; icon: string }> = {
  // Relaciones base (rol estructural)
  TARGETS:          { label: 'Diana Farmacológica', color: '#38bdf8', bg: '#0c2a3a', icon: '🎯' },
  METABOLIZED_BY:   { label: 'Metabolizado por',    color: '#fb923c', bg: '#2a1500', icon: '⚗️'  },
  CARRIED_BY:       { label: 'Transportado por',     color: '#a78bfa', bg: '#1a1040', icon: '🚢' },
  TRANSPORTED_BY:   { label: 'Transportador',        color: '#c084fc', bg: '#1e0f3a', icon: '🔄' },
  // Semánticas de inhibición
  INHIBITS:                      { label: 'Inhibidor',              color: '#f87171', bg: '#2a0a0a', icon: '🚫' },
  SUPPRESSES:                    { label: 'Supresor',               color: '#fca5a5', bg: '#280808', icon: '⬇️' },
  DOWNREGULATES:                 { label: 'Regulador negativo',     color: '#fda4af', bg: '#2a0810', icon: '📉' },
  NEGATIVELY_MODULATES:          { label: 'Modulador negativo',     color: '#fb7185', bg: '#290610', icon: '➖' },
  INHIBITORY_ALLOSTERIC_MODULATES:{ label: 'Mod. Alostérico Inhib.',color: '#f43f5e', bg: '#250510', icon: '🔐' },
  DISRUPTS:                      { label: 'Disruptor',              color: '#ef4444', bg: '#270808', icon: '💥' },
  // Semánticas de activación
  ACTIVATES:                     { label: 'Activador / Agonista',   color: '#4ade80', bg: '#052010', icon: '✅' },
  INDUCES:                       { label: 'Inductor',               color: '#86efac', bg: '#041a0a', icon: '⬆️' },
  UPREGULATES:                   { label: 'Regulador positivo',     color: '#6ee7b7', bg: '#021a10', icon: '📈' },
  POSITIVE_ALLOSTERIC_MODULATES: { label: 'Mod. Alostérico Pos.',  color: '#34d399', bg: '#041a0e', icon: '🔓' },
  POSITIVELY_MODULATES:          { label: 'Modulador positivo',     color: '#10b981', bg: '#031a0c', icon: '➕' },
  POTENTIATES:                   { label: 'Potenciador',            color: '#059669', bg: '#021408', icon: '💪' },
  // Antagonismo
  ANTAGONIZES:                   { label: 'Antagonista',            color: '#fbbf24', bg: '#261800', icon: '⚔️' },
  INVERSE_AGONIZES:              { label: 'Agonista inverso',       color: '#f59e0b', bg: '#231400', icon: '🔃' },
  // Modulación
  MODULATES:                     { label: 'Modulador',              color: '#57534e', bg: '#1a2030', icon: '⚖️' },
  ALLOSTERIC_MODULATES:          { label: 'Mod. Alostérico',        color: '#7dd3fc', bg: '#0c1f30', icon: '🔩' },
  REGULATES:                     { label: 'Regulador',              color: '#93c5fd', bg: '#0a1a30', icon: '📊' },
  // Sustrato / producto
  IS_SUBSTRATE_OF:               { label: 'Sustrato',               color: '#a3e635', bg: '#141f04', icon: '🧪' },
  IS_PRODUCT_OF:                 { label: 'Producto de',            color: '#84cc16', bg: '#111a03', icon: '🏭' },
  IS_COFACTOR_OF:                { label: 'Cofactor',               color: '#bef264', bg: '#161e04', icon: '🔧' },
  IS_COMPONENT_OF:               { label: 'Componente de',          color: '#d9f99d', bg: '#181e05', icon: '🧩' },
  // Unión física
  BINDS:                         { label: 'Ligando / Une',          color: '#67e8f9', bg: '#052028', icon: '🔗' },
  FORMS_ADDUCT_WITH:             { label: 'Forma aducto',           color: '#22d3ee', bg: '#041c24', icon: '🧲' },
  INTERCALATES_INTO:             { label: 'Intercala en',           color: '#06b6d4', bg: '#031820', icon: '📐' },
  CROSS_LINKS:                   { label: 'Cross-linking',          color: '#0891b2', bg: '#021518', icon: '⛓️' },
  INCORPORATES_INTO:             { label: 'Incorpora en',           color: '#0e7490', bg: '#021215', icon: '🔀' },
  // Modificación química
  OXIDIZES:                      { label: 'Oxidante',               color: '#fde68a', bg: '#221800', icon: '🔥' },
  REDUCES:                       { label: 'Reductor',               color: '#fef08a', bg: '#201800', icon: '❄️' },
  CHELATES:                      { label: 'Quelante',               color: '#fef9c3', bg: '#201c00', icon: '🪝' },
  DEGRADES:                      { label: 'Degrada',                color: '#fed7aa', bg: '#201000', icon: '♻️' },
  CLEAVES:                       { label: 'Escinde',                color: '#fdba74', bg: '#1e0e00', icon: '✂️' },
  NEUTRALIZES:                   { label: 'Neutralizador',          color: '#fb923c', bg: '#1c0c00', icon: '🛡️' },
  METABOLIZES:                   { label: 'Metaboliza',             color: '#f97316', bg: '#1a0a00', icon: '🔬' },
  // Roles estructurales
  CARRIES:                       { label: 'Transportador',          color: '#e879f9', bg: '#200a28', icon: '📦' },
  CHAPERONES:                    { label: 'Chaperona',              color: '#d946ef', bg: '#1a0820', icon: '🤝' },
  STABILIZES:                    { label: 'Estabilizador',          color: '#c026d3', bg: '#16061a', icon: '🏛️' },
  PROTECTS:                      { label: 'Protector',              color: '#a21caf', bg: '#120518', icon: '🛡️' },
  // Bioterapéuticos
  REPLACES_GENE:                 { label: 'Reemplaza gen',          color: '#818cf8', bg: '#0f1030', icon: '🧬' },
  SILENCES:                      { label: 'Silencia (ASO)',         color: '#6366f1', bg: '#0c0e28', icon: '🔇' },
  // Fallback
  INTERACTS_WITH:                { label: 'Interacción',            color: '#78716c', bg: '#141c28', icon: '↔️' },
};

function getRelMeta(relType: string) {
  return REL_META[relType] ?? {
    label: relType.replace(/_/g, ' '),
    color: '#78716c',
    bg:    '#141c28',
    icon:  '•',
  };
}

// Relaciones base estructurales — se usan para agrupar en la vista de resumen
const BASE_REL_TYPES = new Set(['TARGETS', 'METABOLIZED_BY', 'CARRIED_BY', 'TRANSPORTED_BY']);


// ── Sub-componentes ────────────────────────────────────────────────────────

function StatPill({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      background: '#f3ece0', border: `1px solid ${color}33`,
      borderRadius: '10px', padding: '12px 20px', minWidth: '90px',
    }}>
      <span style={{ fontSize: '1.6rem', fontWeight: 700, color, fontFamily: 'monospace' }}>
        {value}
      </span>
      <span style={{ fontSize: '0.72rem', color: '#78716c', marginTop: '2px', textAlign: 'center' }}>
        {label}
      </span>
    </div>
  );
}

function ActionBadge({ action }: { action: string }) {
  return (
    <span style={{
      background: '#d6ccbb', border: '1px solid #bcae98',
      color: '#57534e', padding: '2px 8px', borderRadius: '4px',
      fontSize: '0.72rem', fontFamily: 'monospace', whiteSpace: 'nowrap',
    }}>
      {action}
    </span>
  );
}

function KnownActionDot({ value }: { value: string }) {
  const colors: Record<string, string> = { yes: '#15803d', no: '#b91c1c', unknown: '#57534e' };
  const col = colors[value] ?? '#78716c';
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', color: col }}>
      <span style={{ width: 7, height: 7, borderRadius: '50%', background: col, display: 'inline-block' }} />
      {value === 'yes' ? 'Acción confirmada' : value === 'no' ? 'Sin efecto directo' : 'Desconocida'}
    </span>
  );
}

function TargetCard({ iact }: { iact: GraphInteraction }) {
  const meta = getRelMeta(iact.rel_type);

  return (
    <div style={{
      background: `${meta.color}12`,
      border: `1px solid ${meta.color}40`,
      borderLeft: `4px solid ${meta.color}`,
      borderRadius: '8px',
      padding: '12px 14px',
      display: 'flex',
      flexDirection: 'column',
      gap: '6px',
    }}>
      {/* Encabezado: nombre del target + tipo relación */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
        <span style={{ color: '#1c1917', fontWeight: 600, fontSize: '0.9rem', lineHeight: 1.3 }}>
          {iact.target.name || '—'}
        </span>
        <span style={{
          background: `${meta.color}20`, color: meta.color,
          border: `1px solid ${meta.color}40`,
          padding: '2px 8px', borderRadius: '4px',
          fontSize: '0.7rem', fontWeight: 700, whiteSpace: 'nowrap',
          fontFamily: 'monospace', flexShrink: 0,
        }}>
          {meta.icon} {meta.label}
        </span>
      </div>

      {/* IDs */}
      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
        {iact.target.drugbank_target_id && (
          <span style={{ fontSize: '0.72rem', color: '#0284c7', fontFamily: 'monospace' }}>
            {iact.target.drugbank_target_id}
          </span>
        )}
        {iact.target.uniprot_id && (
          <a
            href={`https://www.uniprot.org/uniprotkb/${iact.target.uniprot_id}`}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: '0.72rem', color: '#6d28d9', fontFamily: 'monospace', textDecoration: 'none' }}
          >
            UniProt: {iact.target.uniprot_id} ↗
          </a>
        )}
        {iact.target.organism && (
          <span style={{ fontSize: '0.72rem', color: '#78716c', fontStyle: 'italic' }}>
            {iact.target.organism}
          </span>
        )}
      </div>

      {/* Acciones farmacológicas */}
      {iact.actions.length > 0 && (
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          {iact.actions.map((a) => <ActionBadge key={a} action={a} />)}
        </div>
      )}

      {/* Acción conocida */}
      <KnownActionDot value={iact.known_action} />
    </div>
  );
}

// ── Componente principal ───────────────────────────────────────────────────

interface Props {
  /** MongoDB _id o DrugBank ID del fármaco (se usa como clave para el endpoint) */
  drugId: string;
  /** Nombre del fármaco — fallback si drugId no es un DB-id */
  drugName?: string;
}

export default function GraphInteractionsSection({ drugId, drugName }: Props) {
  const [data, setData]       = useState<DrugGraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  // Filtros locales
  const [activeRelType, setActiveRelType] = useState<string>('ALL');
  const [viewMode, setViewMode] = useState<'table' | 'graph'>('table');
  const [searchTarget, setSearchTarget]   = useState('');
  const [showDDI, setShowDDI]             = useState(false);

  // ── Comparación de fármacos ──────────────────────────────────────────────
  const [compareSearch, setCompareSearch]   = useState('');
  const [compareResults, setCompareResults] = useState<DrugSummary[]>([]);
  const [compareData, setCompareData]       = useState<DrugGraphResponse | null>(null);
  const [compareMode, setCompareMode]       = useState(false);
  const [compareName, setCompareName]       = useState('');
  const compareDebounce = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  React.useEffect(() => {
    if (!compareSearch.trim() || compareSearch.length < 2) { setCompareResults([]); return; }
    if (compareDebounce.current) clearTimeout(compareDebounce.current);
    compareDebounce.current = setTimeout(() => {
      drugsApi.list({ search: compareSearch, page: 1 })
        .then(res => setCompareResults(res.data.results))
        .catch(() => {});
    }, 350);
  }, [compareSearch]);

  const loadCompare = (cId: string, cName: string) => {
    setCompareName(cName);
    setCompareSearch('');
    setCompareResults([]);
    drugsApi.graph(cId, cName)
      .then(r => setCompareData(r.data))
      .catch(() => {});
  };

  useEffect(() => {
    setLoading(true);
    setError('');
    drugsApi
      .graph(drugId, drugName)
      .then((res) => setData(res.data))
      .catch((err) => {
        const msg = err?.response?.data?.error || 'No se pudo cargar la red molecular.';
        setError(msg);
      })
      .finally(() => setLoading(false));
  }, [drugId, drugName]);

  // Todos los tipos de relación presentes (ordenados: base primero, semánticos después)
  const relTypes = useMemo(() => {
    if (!data) return [];
    const types = Object.keys(data.stats.rel_type_counts);
    return [
      ...types.filter((t) => BASE_REL_TYPES.has(t)),
      ...types.filter((t) => !BASE_REL_TYPES.has(t)),
    ];
  }, [data]);

  // Interacciones filtradas
  const filtered = useMemo(() => {
    if (!data) return [];
    return data.interactions.filter((iact) => {
      const matchType = activeRelType === 'ALL' || iact.rel_type === activeRelType;
      const matchSearch =
        !searchTarget ||
        iact.target.name.toLowerCase().includes(searchTarget.toLowerCase()) ||
        iact.target.uniprot_id.toLowerCase().includes(searchTarget.toLowerCase()) ||
        iact.target.drugbank_target_id.toLowerCase().includes(searchTarget.toLowerCase());
      return matchType && matchSearch;
    });
  }, [data, activeRelType, searchTarget]);

  // ── Estados de carga / error ──────────────────────────────────────────────
  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <div style={{ color: '#6366f1', fontSize: '0.95rem', marginBottom: '10px' }}>
          Consultando grafo molecular en Neo4j…
        </div>
        <div style={{ display: 'flex', justifyContent: 'center', gap: '6px' }}>
          {[0, 1, 2].map((i) => (
            <span key={i} style={{
              width: 8, height: 8, borderRadius: '50%', background: '#6366f1',
              animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
              display: 'inline-block',
            }} />
          ))}
        </div>
        <style>{`@keyframes pulse { 0%,100%{opacity:.3} 50%{opacity:1} }`}</style>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        padding: '30px', background: '#1a0a0a', border: '1px solid #7f1d1d',
        borderRadius: '10px', textAlign: 'center', color: '#fca5a5',
      }}>
        <div style={{ fontSize: '1.4rem', marginBottom: '8px' }}>⚠</div>
        <div>{error}</div>
        <div style={{ fontSize: '0.8rem', color: '#78716c', marginTop: '6px' }}>
          Verifica que Neo4j esté activo y que el fármaco tenga entradas en el grafo.
        </div>
      </div>
    );
  }

  if (!data || data.stats.total_interactions === 0) {
    return (
      <div style={{
        padding: '30px', background: '#d6ccbb', border: '1px dashed #bcae98',
        borderRadius: '10px', textAlign: 'center', color: '#78716c',
      }}>
        <div style={{ fontSize: '1.6rem', marginBottom: '8px' }}>🕸️</div>
        <div style={{ color: '#57534e' }}>Sin interacciones moleculares registradas en el grafo.</div>
        <div style={{ fontSize: '0.8rem', marginTop: '4px' }}>
          Este fármaco puede no haber sido importado aún a Neo4j.
        </div>
      </div>
    );
  }

  const { stats, categories, drug_interactions: ddi } = data;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

      {/* ── Estadísticas ─────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
        <StatPill label="Interacciones" value={stats.total_interactions} color="#6366f1" />
        <StatPill label="Categorías"    value={stats.total_categories}   color="#a855f7" />
        <StatPill label="DDI"           value={stats.total_ddi}          color="#f59e0b" />
        {Object.entries(stats.rel_type_counts)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 5)
          .map(([rt, count]) => {
            const m = getRelMeta(rt);
            return <StatPill key={rt} label={m.label} value={count} color={m.color} />;
          })}
      </div>

      {/* ── Filtros ───────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
        {/* Buscador de target */}
        <input
          value={searchTarget}
          onChange={(e) => setSearchTarget(e.target.value)}
          placeholder="Buscar proteína o UniProt ID..."
          style={{
            background: '#f3ece0', border: '1px solid #bcae98', color: '#1c1917',
            padding: '8px 12px', borderRadius: '6px', fontSize: '0.85rem',
            flex: '1 1 180px', minWidth: '140px', maxWidth: '300px', outline: 'none',
          }}
        />

        {/* Filtro por tipo de relación */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          <button
            onClick={() => setActiveRelType('ALL')}
            style={{
              padding: '6px 12px', borderRadius: '6px', fontSize: '0.78rem',
              fontWeight: 600, cursor: 'pointer', border: 'none',
              background: activeRelType === 'ALL' ? '#6366f1' : '#d6ccbb',
              color: '#fff',
            }}
          >
            Todos ({stats.total_interactions})
          </button>
          {relTypes.map((rt) => {
            const m = getRelMeta(rt);
            const active = activeRelType === rt;
            return (
              <button
                key={rt}
                onClick={() => setActiveRelType(rt)}
                style={{
                  padding: '6px 12px', borderRadius: '6px', fontSize: '0.78rem',
                  fontWeight: 600, cursor: 'pointer',
                  border: `1px solid ${m.color}50`,
                  background: active ? `${m.color}26` : '#faf6ee',
                  color: active ? '#1c1917' : '#78716c',
                }}
              >
                {m.icon} {m.label} ({stats.rel_type_counts[rt]})
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Grid de targets / grafo ──────────────────────────────────────── */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <div style={{ fontSize: '0.75rem', color: '#57534e' }}>
            Mostrando {filtered.length} de {stats.total_interactions} interacciones
          </div>
          {/* Toggle tabla / grafo + Comparar */}
          <div style={{ display: 'flex', gap: '4px' }}>
            {(['table', 'graph'] as const).map((mode) => (
              <button key={mode} onClick={() => setViewMode(mode)} style={{
                padding: '5px 12px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer',
                border: '1px solid #bcae98', background: viewMode === mode ? '#2d2621' : '#faf6ee', color: viewMode === mode ? '#faf6ee' : '#57534e',
              }}>
                {mode === 'table' ? '☰ Tabla' : '🕸️ Grafo'}
              </button>
            ))}
            {viewMode === 'graph' && (
              <button
                onClick={() => {
                  if (compareMode) { setCompareData(null); setCompareName(''); setCompareSearch(''); setCompareResults([]); }
                  setCompareMode(m => !m);
                }}
                style={{
                  padding: '5px 12px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer',
                  border: `1px solid ${compareMode ? '#f59e0b' : '#bcae98'}`,
                  background: compareMode ? '#2a1a00' : '#d6ccbb', color: compareMode ? '#f59e0b' : '#78716c',
                }}
              >
                🔬 {compareMode ? 'Cerrar comparación' : 'Comparar fármaco'}
              </button>
            )}
          </div>
        </div>

        {/* ── Panel comparación ───────────────────────────────────────── */}
        {compareMode && viewMode === 'graph' && (
          <div style={{
            background: '#1a1400', border: '1px solid #3a2800', borderRadius: '8px',
            padding: '12px 14px', marginBottom: '10px',
          }}>
            <div style={{ color: '#f59e0b', fontWeight: 700, fontSize: '0.8rem', marginBottom: '8px' }}>
              🔬 Comparar con otro fármaco
            </div>
            {compareName ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                <span style={{ color: '#fde68a', fontSize: '0.85rem' }}>
                  ✅ Comparando con: <strong>{compareName}</strong>
                </span>
                <button onClick={() => { setCompareData(null); setCompareName(''); }} style={{
                  background: 'none', border: '1px solid #bcae98', color: '#78716c',
                  borderRadius: '4px', padding: '2px 8px', cursor: 'pointer', fontSize: '0.75rem',
                }}>
                  ✕ Quitar
                </button>
                {compareData && (() => {
                  const t1Ids = new Set(filtered.map(i => i.target.drugbank_target_id || i.target.name));
                  const t2Ids = new Set(compareData.interactions.map(i => i.target.drugbank_target_id || i.target.name));
                  const shared = Array.from(t1Ids).filter(id => t2Ids.has(id)).length;
                  return (
                    <span style={{ fontSize: '0.78rem', color: '#78350f' }}>
                      Compartidas: <strong style={{ color: '#f59e0b' }}>{shared}</strong>
                      {' · '}Solo en {drugName ?? 'este'}: <strong style={{ color: '#38bdf8' }}>{t1Ids.size - shared}</strong>
                      {' · '}Solo en {compareName}: <strong style={{ color: '#a78bfa' }}>{t2Ids.size - shared}</strong>
                    </span>
                  );
                })()}
              </div>
            ) : (
              <div style={{ position: 'relative' }}>
                <input
                  value={compareSearch}
                  onChange={e => setCompareSearch(e.target.value)}
                  placeholder="Escribe el nombre del fármaco a comparar..."
                  style={{
                    width: '100%', background: '#f3ece0', border: '1px solid #bcae98',
                    color: '#1c1917', padding: '7px 10px', borderRadius: '6px',
                    fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box',
                  }}
                />
                {compareResults.length > 0 && (
                  <div style={{
                    position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 50,
                    background: '#f3ece0', border: '1px solid #bcae98', borderRadius: '0 0 6px 6px',
                    boxShadow: '0 4px 20px #000a',
                  }}>
                    {compareResults.map(r => (
                      <div
                        key={r._id}
                        onClick={() => loadCompare(r._id, r.name)}
                        style={{ padding: '8px 12px', cursor: 'pointer', color: '#1c1917', fontSize: '0.85rem', borderBottom: '1px solid #d6ccbb' }}
                        onMouseEnter={e => (e.currentTarget.style.background = '#d6ccbb')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                      >
                        {r.name}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
            <div style={{ marginTop: '8px', fontSize: '0.72rem', color: '#4a3500' }}>
              Dianas compartidas aparecen en <span style={{ color: '#34d399' }}>verde</span>; cada fármaco en un color distinto
            </div>
          </div>
        )}

        {filtered.length === 0 ? (
          <div style={{ color: '#57534e', padding: '20px', textAlign: 'center', fontSize: '0.9rem' }}>
            Ninguna interacción coincide con los filtros aplicados.
          </div>
        ) : viewMode === 'table' ? (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
            gap: '10px',
          }}>
            {filtered.map((iact, idx) => (
              <TargetCard key={`${iact.rel_type}-${iact.target.drugbank_target_id}-${idx}`} iact={iact} />
            ))}
          </div>
        ) : (
          <CytoscapeGraph
            height={compareData ? 620 : 520}
            layout="cose"
            nodes={(() => {
              const drug1Id = data.drug.drugbank_id || 'drug';
              const center: CyNode = { id: drug1Id, label: data.drug.name, kind: 'drug', weight: 4 };

              if (!compareData) {
                const seen = new Set<string>([drug1Id]);
                const nodes: CyNode[] = [center];
                filtered.forEach(iact => {
                  const tid = iact.target.drugbank_target_id || iact.target.name;
                  if (!seen.has(tid)) {
                    seen.add(tid);
                    nodes.push({ id: tid, label: iact.target.name || tid, kind: 'target', weight: 1.5, meta: { uniprot: iact.target.uniprot_id, organism: iact.target.organism } });
                  }
                });
                return nodes;
              }

              const drug2Id = compareData.drug.drugbank_id || 'drug2';
              const drug2Node: CyNode = { id: drug2Id, label: compareData.drug.name, kind: 'drug', weight: 4, meta: { isCompare: true } };

              const t1Ids = new Set(filtered.map(i => i.target.drugbank_target_id || i.target.name));
              const t2Ids = new Set(compareData.interactions.map(i => i.target.drugbank_target_id || i.target.name));
              const sharedIds = new Set(Array.from(t1Ids).filter(id => t2Ids.has(id)));

              const seen = new Set<string>([drug1Id, drug2Id]);
              const targetNodes: CyNode[] = [];

              const addTargets = (interactions: GraphInteraction[]) => {
                interactions.forEach(iact => {
                  const tid = iact.target.drugbank_target_id || iact.target.name;
                  if (!seen.has(tid)) {
                    seen.add(tid);
                    targetNodes.push({
                      id: tid,
                      label: iact.target.name || tid,
                      kind: sharedIds.has(tid) ? 'category' : 'target',
                      weight: sharedIds.has(tid) ? 2 : 1.5,
                      meta: { uniprot: iact.target.uniprot_id, organism: iact.target.organism },
                    });
                  }
                });
              };
              addTargets(filtered);
              addTargets(compareData.interactions);
              return [center, drug2Node, ...targetNodes];
            })()}
            edges={(() => {
              const drug1Id = data.drug.drugbank_id || 'drug';
              const edges1: CyEdge[] = filtered.map((iact, idx) => ({
                id: `d1-${iact.rel_type}-${iact.target.drugbank_target_id}-${idx}`,
                source: drug1Id,
                target: iact.target.drugbank_target_id || iact.target.name,
                label: iact.rel_type,
              }));
              if (!compareData) return edges1;
              const drug2Id = compareData.drug.drugbank_id || 'drug2';
              const edges2: CyEdge[] = compareData.interactions.map((iact, idx) => ({
                id: `d2-${iact.rel_type}-${iact.target.drugbank_target_id}-${idx}`,
                source: drug2Id,
                target: iact.target.drugbank_target_id || iact.target.name,
                label: iact.rel_type,
              }));
              return [...edges1, ...edges2];
            })()}
          />
        )}
      </div>

      {/* ── Categorías farmacológicas ──────────────────────────────────── */}
      {categories.length > 0 && (
        <div style={{
          background: '#f3ece0', border: '1px solid #cdd9e6',
          borderRadius: '10px', padding: '16px',
        }}>
          <div style={{ color: '#0284c7', fontWeight: 700, fontSize: '0.85rem', marginBottom: '10px' }}>
            🏷️ Categorías Farmacológicas ({categories.length})
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {categories.map((cat) => (
              <span key={cat.name} style={{
                background: '#eef5fb', border: '1px solid #1e4070',
                color: '#1d4ed8', padding: '4px 10px', borderRadius: '6px',
                fontSize: '0.8rem',
              }}>
                {cat.name}
                {cat.mesh_id && (
                  <span style={{ color: '#57534e', marginLeft: '6px', fontSize: '0.7rem' }}>
                    {cat.mesh_id}
                  </span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Interacciones drug-drug ───────────────────────────────────── */}
      {ddi.length > 0 && (
        <div style={{
          background: '#110a00', border: '1px solid #3a2000',
          borderRadius: '10px', padding: '16px',
        }}>
          <button
            onClick={() => setShowDDI(!showDDI)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: '#f59e0b', fontWeight: 700, fontSize: '0.85rem',
              display: 'flex', alignItems: 'center', gap: '6px', padding: 0,
            }}
          >
            ⚠️ Interacciones Drug-Drug ({ddi.length})
            <span style={{ fontSize: '0.7rem', color: '#78350f' }}>
              {showDDI ? '▲ ocultar' : '▼ expandir'}
            </span>
          </button>

          {showDDI && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '12px' }}>
              {ddi.map((d) => (
                <div key={d.drugbank_id} style={{
                  background: '#1a0e00', border: '1px solid #3a2800',
                  borderRadius: '6px', padding: '10px 12px',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ color: '#fde68a', fontWeight: 600, fontSize: '0.88rem' }}>
                      {d.name}
                    </span>
                    <span style={{ color: '#78350f', fontSize: '0.72rem', fontFamily: 'monospace' }}>
                      {d.drugbank_id}
                    </span>
                  </div>
                  {d.description && (
                    <p style={{ color: '#92400e', fontSize: '0.8rem', margin: 0, lineHeight: 1.5 }}>
                      {d.description}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
