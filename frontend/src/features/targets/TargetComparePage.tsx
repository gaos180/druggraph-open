import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Search, Plus, X, GitCompare, Network } from 'lucide-react';
import {
  NotebookLayout,
  NotebookNavbar,
  NotebookCard,
  SectionHeader,
  Loader,
  Tag,
  TabBar,
} from '../../components/notebook';
import CytoscapeGraph, { CyNode, CyEdge } from '../../components/CytoscapeGraph';
import { targetsApi, TargetRecord, TargetGraphResponse, TargetCompareResponse } from '../../api/targets';
import { usePageTitle } from '../../hooks/usePageTitle';

// ── Selector de diana ────────────────────────────────────────────────────────
function TargetSelectorSlot({
  index,
  target,
  onSelect,
  onRemove,
  canRemove,
}: {
  index: number;
  target: TargetRecord | null;
  onSelect: (t: TargetRecord) => void;
  onRemove: () => void;
  canRemove: boolean;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<TargetRecord[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!query.trim()) { setResults([]); return; }
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await targetsApi.list({ search: query, per_page: 8 });
        setResults(res.data.results);
      } catch { /* ignore */ } finally { setLoading(false); }
    }, 300);
    return () => clearTimeout(t);
  }, [query]);

  if (target) {
    return (
      <div className="flex items-center justify-between gap-2 bg-sky-50 border-2 border-sky-200 rounded-xl px-3 py-2">
        <div className="min-w-0">
          <div className="font-hand font-bold text-sm text-[#1a140f] truncate">{target.name}</div>
          <div className="text-xs font-mono text-stone-500">{target.id} {target.gene_name ? `· ${target.gene_name}` : ''}</div>
        </div>
        {canRemove && (
          <button onClick={onRemove} className="text-stone-500 hover:text-red-500 transition-colors flex-shrink-0">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="relative">
      <div className="flex items-center gap-2 bg-white border-2 border-stone-200 rounded-xl px-3 py-2 focus-within:border-stone-500 transition-colors">
        <Search className="w-4 h-4 text-stone-500 flex-shrink-0" />
        <input
          type="text"
          value={query}
          onChange={e => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          placeholder={`Diana ${index + 1}…`}
          className="flex-1 bg-transparent text-sm font-hand text-[#1a140f] placeholder:text-stone-500 outline-none"
        />
        {loading && <span className="text-[10px] text-stone-500 animate-pulse">…</span>}
      </div>
      {open && results.length > 0 && (
        <div className="absolute z-20 top-full left-0 right-0 mt-1 bg-white border-2 border-stone-200 rounded-xl shadow-lg max-h-48 overflow-y-auto">
          {results.map(r => (
            <button
              key={r.id}
              onMouseDown={() => { onSelect(r); setQuery(''); setResults([]); setOpen(false); }}
              className="w-full text-left px-3 py-2 hover:bg-stone-50 text-sm font-hand border-b border-stone-100 last:border-0"
            >
              <span className="font-bold text-[#1a140f]">{r.name}</span>
              <span className="text-stone-500 text-xs ml-2 font-mono">{r.id}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Panel de comparación Jaccard ────────────────────────────────────────────
function ComparePanel({ targets }: { targets: (TargetRecord | null)[] }) {
  const a = targets[0];
  const b = targets[1];
  const [result, setResult] = useState<TargetCompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!a || !b) { setResult(null); return; }
    setLoading(true);
    setError('');
    targetsApi.compare(a.id, b.id)
      .then(r => setResult(r.data))
      .catch(e => setError(e.response?.data?.error || 'Error al comparar'))
      .finally(() => setLoading(false));
  }, [a?.id, b?.id]);

  if (!a || !b) {
    return <p className="text-stone-500 text-sm font-hand text-center py-8">Selecciona al menos dos dianas para comparar.</p>;
  }
  if (loading) return <Loader label="Comparando dianas…" />;
  if (error) return <p className="text-red-600 text-sm font-hand p-4">{error}</p>;
  if (!result) return null;

  const { stats, common_drugs, only_a_drugs, only_b_drugs } = result;

  return (
    <div className="space-y-4">
      {/* Resumen estadístico */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: a.name, value: stats.count_a, tone: 'blue' as const },
          { label: b.name, value: stats.count_b, tone: 'blue' as const },
          { label: 'Comunes', value: stats.count_common, tone: 'green' as const },
          { label: 'Jaccard', value: stats.jaccard_similarity.toFixed(3), tone: stats.jaccard_similarity > 0.2 ? 'green' as const : 'neutral' as const },
        ].map(({ label, value, tone }) => (
          <NotebookCard key={label} className="text-center p-3">
            <div className="text-xl font-bold font-mono text-[#1a140f]">{value}</div>
            <div className="text-xs text-stone-500 font-hand truncate mt-0.5">{label}</div>
            <Tag tone={tone}>{label === 'Jaccard' ? 'Jaccard' : 'fármacos'}</Tag>
          </NotebookCard>
        ))}
      </div>

      {/* Listas de fármacos */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <DrugList title={`Solo ${a.name}`} drugs={only_a_drugs} tone="blue" />
        <DrugList title="En ambas" drugs={common_drugs} tone="green" />
        <DrugList title={`Solo ${b.name}`} drugs={only_b_drugs} tone="blue" />
      </div>
    </div>
  );
}

function DrugList({ title, drugs, tone }: { title: string; drugs: { drugbank_id: string; drug_name: string }[]; tone: 'blue' | 'green' }) {
  return (
    <div>
      <SectionHeader tone={tone === 'green' ? '#15803d' : '#0369a1'}>{title} ({drugs.length})</SectionHeader>
      <div className="mt-2 max-h-52 overflow-y-auto space-y-1">
        {drugs.length === 0
          ? <p className="text-stone-500 text-xs font-hand italic">Sin fármacos exclusivos</p>
          : drugs.map(d => (
            <Link
              key={d.drugbank_id}
              to={`/drugs/${d.drugbank_id}`}
              className="flex items-center justify-between px-2 py-1 rounded-lg hover:bg-stone-100 transition-colors text-sm"
            >
              <span className="font-hand text-[#1a140f] truncate">{d.drug_name || d.drugbank_id}</span>
              <span className="text-xs font-mono text-stone-500 ml-2 flex-shrink-0">{d.drugbank_id}</span>
            </Link>
          ))
        }
      </div>
    </div>
  );
}

// ── Panel del grafo multi-diana ─────────────────────────────────────────────
function buildMultiGraph(graphs: TargetGraphResponse[], targets: TargetRecord[]): { nodes: CyNode[]; edges: CyEdge[] } {
  const drugTargets = new Map<string, Set<string>>();
  const drugLabels  = new Map<string, string>();

  for (let i = 0; i < graphs.length; i++) {
    const g = graphs[i];
    const tid = targets[i].id;
    for (const n of g.nodes) {
      if (n.data.kind === 'drug') {
        const did = n.data.id;
        if (!drugTargets.has(did)) drugTargets.set(did, new Set());
        drugTargets.get(did)!.add(tid);
        if (!drugLabels.has(did)) drugLabels.set(did, n.data.label);
      }
    }
  }

  const total = targets.length;
  const nodes: CyNode[] = targets.map(t => ({ id: t.id, label: t.name, kind: 'target' as const }));
  const edges: CyEdge[] = [];

  for (const [did, sharedWith] of Array.from(drugTargets.entries())) {
    const n = sharedWith.size;
    const kind: CyNode['kind'] = n === total && total > 1 ? 'seed'
      : n >= 2 ? 'predicted'
      : 'drug';
    nodes.push({ id: did, label: drugLabels.get(did) || did, kind });
    for (const tid of Array.from(sharedWith)) {
      edges.push({ id: `${did}--${tid}`, source: did, target: tid, label: '' });
    }
  }

  return { nodes, edges };
}

function MultiGraphPanel({ targets }: { targets: (TargetRecord | null)[] }) {
  const validTargets = useMemo(
    () => targets.filter((t): t is TargetRecord => t !== null),
    [targets],
  );
  const [graphs, setGraphs] = useState<TargetGraphResponse[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const key = validTargets.map(t => t.id).join(',');

  useEffect(() => {
    if (validTargets.length < 1) { setGraphs(null); return; }
    setLoading(true);
    setError('');
    Promise.all(validTargets.map(t => targetsApi.graph(t.id).then(r => r.data)))
      .then(setGraphs)
      .catch(e => setError(e.response?.data?.error || 'Error al cargar grafo'))
      .finally(() => setLoading(false));
  }, [key, validTargets]);

  if (validTargets.length === 0) {
    return <p className="text-stone-500 text-sm font-hand text-center py-8">Selecciona al menos una diana.</p>;
  }
  if (loading) return <Loader label="Construyendo grafo…" />;
  if (error) return <p className="text-red-600 text-sm font-hand p-4">{error}</p>;
  if (!graphs) return null;

  const { nodes, edges } = buildMultiGraph(graphs, validTargets);

  const sharedDrugs = nodes.filter(n => n.kind === 'predicted' || n.kind === 'seed');

  return (
    <div>
      <CytoscapeGraph nodes={nodes} edges={edges} height={460} />
      {sharedDrugs.length > 0 && (
        <div className="mt-4">
          <SectionHeader>Fármacos compartidos ({sharedDrugs.length})</SectionHeader>
          <div className="mt-2 flex flex-wrap gap-2">
            {sharedDrugs.map(n => (
              <Link key={n.id} to={`/drugs/${n.id}`}
                className="flex items-center gap-1.5 px-2 py-1 rounded-lg border border-stone-200 hover:bg-stone-50 text-sm transition-colors">
                <span className="font-hand text-[#1a140f]">{n.label}</span>
                <Tag tone={n.kind === 'seed' ? 'amber' : 'blue'}>
                  {n.kind === 'seed' ? `${validTargets.length}/${validTargets.length} dianas` : `${(graphs.reduce((acc, g) => acc + (g.nodes.some(x => x.data.id === n.id) ? 1 : 0), 0))}/${validTargets.length} dianas`}
                </Tag>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Página principal ─────────────────────────────────────────────────────────
const MAX_TARGETS = 6;
type TabId = 'compare' | 'graph';

export default function TargetComparePage() {
  usePageTitle('Comparar dianas');
  const [tab, setTab] = useState<TabId>('compare');
  const [slots, setSlots] = useState<(TargetRecord | null)[]>([null, null]);

  const addSlot = () => {
    if (slots.length < MAX_TARGETS) setSlots(s => [...s, null]);
  };

  const removeSlot = (i: number) => {
    setSlots(s => s.length > 2 ? s.filter((_, idx) => idx !== i) : s.map((v, idx) => idx === i ? null : v));
  };

  const setTarget = (i: number, t: TargetRecord) => {
    setSlots(s => s.map((v, idx) => idx === i ? t : v));
  };

  return (
    <NotebookLayout>
      <NotebookNavbar />
      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Encabezado */}
        <div>
          <h1 className="text-2xl font-bold font-hand text-[#1a140f] flex items-center gap-2">
            <GitCompare className="w-6 h-6 text-[#dd6b20]" />
            Comparador de dianas
          </h1>
          <p className="text-stone-500 text-sm font-hand mt-1">
            Compara el perfil farmacológico de hasta {MAX_TARGETS} dianas terapéuticas.
          </p>
        </div>

        {/* Selector de dianas */}
        <NotebookCard>
          <SectionHeader>Dianas seleccionadas</SectionHeader>
          <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2">
            {slots.map((target, i) => (
              <TargetSelectorSlot
                key={i}
                index={i}
                target={target}
                onSelect={t => setTarget(i, t)}
                onRemove={() => removeSlot(i)}
                canRemove={slots.length > 2 || target !== null}
              />
            ))}
          </div>
          {slots.length < MAX_TARGETS && (
            <button
              onClick={addSlot}
              className="mt-3 flex items-center gap-1.5 text-sm text-stone-500 hover:text-stone-700 font-hand transition-colors"
            >
              <Plus className="w-4 h-4" /> Añadir diana
            </button>
          )}
        </NotebookCard>

        {/* Pestañas */}
        <TabBar<TabId>
          tabs={[
            { id: 'compare', label: <span className="flex items-center gap-1.5"><GitCompare className="w-4 h-4" /> Jaccard</span> },
            { id: 'graph',   label: <span className="flex items-center gap-1.5"><Network className="w-4 h-4" /> Grafo multi-diana</span> },
          ]}
          active={tab}
          onChange={setTab}
        />

        <NotebookCard>
          {tab === 'compare'
            ? <ComparePanel targets={slots} />
            : <MultiGraphPanel targets={slots} />
          }
        </NotebookCard>
      </div>
    </NotebookLayout>
  );
}
