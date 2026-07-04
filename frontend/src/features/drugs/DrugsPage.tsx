import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { Search, Download, X, ArrowRight, FlaskConical } from 'lucide-react';
import { useDrugs } from '../../hooks/useDrugs';
import { DrugSummary, DrugDetail, drugsApi } from '../../api/drugs';
import { targetsApi, DrugByTargetResult } from '../../api/targets';
import { usePageTitle } from '../../hooks/usePageTitle';
import {
  NotebookLayout, NotebookNavbar, NotebookCard, HandTitle, PencilButton,
  Tag, groupTone, ChemicalDoodle, SectionHeader, EmptyState, Loader,
} from '../../components/notebook';

function downloadCsv(filename: string, headers: string[], rows: (string | number)[][]) {
  const esc = (v: string | number) => {
    const s = String(v ?? '');
    return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [headers.map(esc).join(','), ...rows.map(r => r.map(esc).join(','))];
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

function drugbankId(raw: any): string {
  if (!raw) return '';
  if (Array.isArray(raw)) {
    const p = raw.find((i: any) => typeof i === 'object' && i?.primary === true) || raw[0];
    return p && typeof p === 'object' ? p.value : String(p);
  }
  return typeof raw === 'object' && 'value' in raw ? raw.value : String(raw);
}

const inputCls = 'w-full bg-[#faf6ee] px-3 py-2.5 border-2 border-[#3f3429] rounded-xl font-hand text-base focus:outline-none focus:ring-1 focus:ring-stone-600';
const selectCls = 'bg-[#faf6ee] px-3 py-2.5 border-2 border-[#3f3429] rounded-xl font-hand text-base cursor-pointer text-[#423a31]';

function DrugCard({ drug, onClick, isSelected, seed }: { drug: DrugSummary; onClick: () => void; isSelected: boolean; seed: number }) {
  const groups = drug.groups ?? [];
  const desc = drug.description?.slice(0, 110) || 'Sin descripción disponible.';
  return (
    <NotebookCard selected={isSelected} onClick={onClick} className="flex flex-col min-h-[160px]">
      <div className="flex justify-between items-start gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-base font-bold text-stone-900 leading-tight">
            {drug.name} <span className="text-[11px] text-stone-500 font-mono">({drugbankId(drug['drugbank-id'])})</span>
          </h3>
          <p className="text-[11px] text-stone-500 leading-snug font-hand mt-1.5 line-clamp-2">
            {desc}{drug.description && drug.description.length > 110 ? '…' : ''}
          </p>
        </div>
        <ChemicalDoodle size={64} seed={seed} />
      </div>
      <div className="flex flex-wrap gap-1.5 mt-auto">
        {drug.type && <Tag tone="blue">{drug.type}</Tag>}
        {groups.slice(0, 2).map((g: string) => <Tag key={g} tone={groupTone(g)}>{g}</Tag>)}
      </div>
    </NotebookCard>
  );
}

export default function DrugsPage() {
  const navigate = useNavigate();
  usePageTitle('Fármacos');
  const { data, filters, loading, error, searchInput, query, updateSearch, triggerSearch, updateType, updateGroup, nextPage, prevPage } = useDrugs();

  const [selectedDrug, setSelectedDrug] = useState<DrugDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [targetQuery, setTargetQuery] = useState('');
  const [targetResults, setTargetResults] = useState<DrugByTargetResult[] | null>(null);
  const [loadingTarget, setLoadingTarget] = useState(false);
  const targetDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!targetQuery.trim()) { setTargetResults(null); return; }
    if (targetDebounce.current) clearTimeout(targetDebounce.current);
    targetDebounce.current = setTimeout(() => {
      setLoadingTarget(true);
      targetsApi.byGene(targetQuery.trim())
        .then(r => setTargetResults(r.data.results)).catch(() => setTargetResults([])).finally(() => setLoadingTarget(false));
    }, 400);
    return () => { if (targetDebounce.current) clearTimeout(targetDebounce.current); };
  }, [targetQuery]);

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSelectedDrug(null); setTargetQuery(''); setTargetResults(null); triggerSearch();
  };

  const handleCardClick = (id: string) => {
    setLoadingDetail(true);
    setDetailError('');
    drugsApi.detail(id).then(res => setSelectedDrug(res.data))
      .catch(() => setDetailError('No se pudo cargar el detalle del fármaco.')).finally(() => setLoadingDetail(false));
  };

  const closeDetail = () => { setSelectedDrug(null); setLoadingDetail(false); setDetailError(''); };

  const modalOpen = !!(selectedDrug || loadingDetail || detailError);
  useEffect(() => {
    if (modalOpen) document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, [modalOpen]);

  const inTargetMode = targetResults !== null;

  const handleExportCsv = () => {
    if (inTargetMode && targetResults) {
      downloadCsv(`druggraph_diana_${targetQuery.replace(/\s+/g, '_')}.csv`,
        ['Nombre', 'DrugBank ID', 'Dianas encontradas'],
        targetResults.map(r => [r.name, r.drugbank_id, r.targets_matched.map((t: any) => t.gene_name || t.target_name).join('; ')]));
    } else if (data?.results?.length) {
      downloadCsv('druggraph_busqueda.csv', ['Nombre', 'DrugBank ID', 'Tipo', 'Grupos'],
        data.results.map(d => [d.name, drugbankId(d['drugbank-id']), d.type ?? '', (d.groups ?? []).join('; ')]));
    }
  };

  return (
    <NotebookLayout navbar={<NotebookNavbar />}>
      <div className="mb-4">
        <HandTitle className="text-3xl flex items-center gap-2"><FlaskConical className="w-7 h-7 text-amber-800" /> Catálogo de Fármacos</HandTitle>
      </div>

      {/* Barra de filtros */}
      <div className="bg-stone-500/5 rounded-2xl p-5 mb-6 border border-stone-800/10">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <form onSubmit={handleFormSubmit} className="lg:col-span-2">
            <input className={inputCls} placeholder="Nombre, sinónimo o SMILES…" value={searchInput} onChange={(e) => updateSearch(e.target.value)} />
          </form>
          <div className="relative">
            <input className={inputCls} placeholder="Filtrar por diana/gen…" value={targetQuery} onChange={e => setTargetQuery(e.target.value)} />
            {targetQuery && (
              <button onClick={() => { setTargetQuery(''); setTargetResults(null); }} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-stone-500 cursor-pointer"><X className="w-4 h-4" /></button>
            )}
          </div>
          <select className={selectCls} value={query.type} onChange={(e) => updateType(e.target.value)}>
            <option value="">Todos los tipos</option>
            {(filters?.types ?? []).map((t: string) => <option key={t} value={t}>{t}</option>)}
          </select>
          <select className={selectCls} value={query.group} onChange={(e) => updateGroup(e.target.value)}>
            <option value="">Todos los grupos</option>
            {(filters?.groups ?? []).map((g: string) => <option key={g} value={g}>{g}</option>)}
          </select>
        </div>
        {(data?.results?.length || targetResults?.length) ? (
          <div className="mt-4 flex justify-end">
            <PencilButton onClick={handleExportCsv} icon={<Download className="w-4 h-4 text-amber-800" />}>Exportar CSV</PencilButton>
          </div>
        ) : null}
      </div>

      {inTargetMode && (
        <div className="bg-indigo-500/8 border border-indigo-500/25 rounded-xl px-4 py-2.5 mb-3 text-sm text-indigo-900 font-hand flex items-center justify-between">
          <span>🎯 Fármacos que interactúan con <strong>"{targetQuery}"</strong>{loadingTarget ? ' — buscando…' : ` — ${targetResults?.length ?? 0} encontrados`}</span>
          <button onClick={() => { setTargetQuery(''); setTargetResults(null); }} className="text-stone-500 cursor-pointer text-xs">✕ Quitar</button>
        </div>
      )}

      {error && <div className="bg-red-50 border border-red-300 text-red-700 rounded-xl px-4 py-2 mb-3 text-sm">⚠ {error}</div>}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
          {/* Modo diana */}
          {inTargetMode && !loadingTarget && (targetResults ?? []).map((r, i) => (
            <NotebookCard key={i} onClick={() => navigate(`/drugs/${r.drugbank_id}`)}>
              <div className="flex justify-between items-start mb-2">
                <span className="font-bold text-stone-900">{r.name}</span>
                <span className="text-[11px] text-stone-500 font-mono">{r.drugbank_id}</span>
              </div>
              <div className="flex flex-col gap-1">
                {r.targets_matched.slice(0, 3).map((t, j) => (
                  <div key={j} className="text-xs text-stone-500 flex gap-1.5 items-center">
                    <code className="text-sky-700 font-bold">{t.gene_name || t.target_name.slice(0, 20)}</code>
                    <ArrowRight className="w-3 h-3 text-stone-500" />
                    <span className="text-stone-500">{t.rel_type.replace(/_/g, ' ')}</span>
                  </div>
                ))}
                {r.targets_matched.length > 3 && <div className="text-[11px] text-stone-500">+ {r.targets_matched.length - 3} dianas más</div>}
              </div>
            </NotebookCard>
          ))}
          {inTargetMode && loadingTarget && <div className="col-span-full"><Loader label="Buscando dianas…" /></div>}
          {inTargetMode && !loadingTarget && (targetResults ?? []).length === 0 && (
            <div className="col-span-full"><EmptyState title="Ningún fármaco para esa diana" /></div>
          )}

          {/* Modo normal */}
          {!inTargetMode && loading && <div className="col-span-full"><Loader label="Buscando registros…" /></div>}
          {!inTargetMode && !loading && (!data || data.results.length === 0) && (
            <div className="col-span-full">
              <EmptyState title="No se encontraron fármacos" hint="Verifica el nombre, sinónimo o estructura ingresada." icon={<Search className="w-10 h-10 text-stone-500" />} />
            </div>
          )}
          {!inTargetMode && !loading && data?.results.map((drug: DrugSummary, i: number) => (
            <DrugCard key={drug._id} drug={drug} seed={i} isSelected={selectedDrug?._id === drug._id} onClick={() => handleCardClick(drug._id)} />
          ))}
      </div>

      {/* Modal de detalle — portal a document.body, funciona en todos los tamaños */}
      {modalOpen && createPortal(
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px', backgroundColor: 'rgba(0,0,0,0.5)' }}
          onClick={closeDetail}
        >
          <div
            style={{ background: '#faf6ee', color: '#2b251d', width: '100%', maxWidth: 520, borderRadius: 16, border: '2px solid #2b251d', padding: '24px', maxHeight: '88dvh', overflowY: 'auto', boxShadow: '0 8px 40px rgba(43,37,29,0.22)' }}
            onClick={e => e.stopPropagation()}
          >
            {loadingDetail ? <Loader label="Mapeando propiedades…" /> : detailError ? (
              <div className="flex flex-col items-center gap-4 py-6">
                <p className="text-red-700 font-hand text-sm text-center">{detailError}</p>
                <PencilButton onClick={closeDetail}>Cerrar</PencilButton>
              </div>
            ) : selectedDrug && (
              <>
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-2xl font-hand font-bold text-stone-900 leading-none">{selectedDrug.name}</h3>
                    <span className="text-xs text-stone-500 font-hand italic">Análisis in silico</span>
                  </div>
                  <button onClick={closeDetail} className="text-stone-500 hover:text-stone-800 cursor-pointer p-1"><X className="w-5 h-5" /></button>
                </div>
                {[
                  ['Indicación clínica', selectedDrug.indication || 'No registrada.'],
                  ['Farmacodinamia', selectedDrug.pharmacodynamics || 'No disponible.'],
                  ['Toxicidad', selectedDrug.toxicity || 'No disponible.'],
                ].map(([label, val]) => (
                  <div key={label} className="mb-3">
                    <SectionHeader tone="#7c2d12">{label}</SectionHeader>
                    <p className="text-[13px] text-stone-700 leading-relaxed text-justify">{val}</p>
                  </div>
                ))}
                <div className="mb-4">
                  <SectionHeader tone="#065f46">SMILES</SectionHeader>
                  {selectedDrug.smiles
                    ? <div style={{ backgroundColor: '#e7e5e4', color: '#1c1917' }} className="p-3 rounded-lg break-all font-mono text-xs leading-relaxed select-all">{selectedDrug.smiles}</div>
                    : <p className="text-stone-500 italic text-xs">Sin cadena SMILES.</p>}
                </div>
                <PencilButton variant="solid" className="w-full justify-center" onClick={() => navigate(`/drugs/${selectedDrug._id}`)} icon={<ArrowRight className="w-4 h-4" />}>
                  Perfil molecular completo
                </PencilButton>
              </>
            )}
          </div>
        </div>,
        document.body
      )}

      {data && data.results.length > 0 && (
        <div className="flex items-center justify-center gap-4 mt-6 font-hand">
          <PencilButton disabled={!data.has_prev} onClick={prevPage}>← Anterior</PencilButton>
          <span className="text-stone-600 text-sm">Página {data.page}</span>
          <PencilButton disabled={!data.has_next} onClick={nextPage}>Siguiente →</PencilButton>
        </div>
      )}
    </NotebookLayout>
  );
}
