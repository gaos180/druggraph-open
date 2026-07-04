import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import type { LucideIcon } from 'lucide-react';
import { ArrowLeft, Download, FlaskConical, Beaker, Stethoscope, Dna, Share2, Map, Microscope, DollarSign, BookMarked, Activity } from 'lucide-react';
import { drugsApi } from '../../api/drugs';
import type { DrugRecord } from '../../types/drug';
import ChemistrySection from './drug-sections/ChemistrySection';
import ClinicalSection from './drug-sections/ClinicalSection';
import TargetsSection from './drug-sections/TargetsSection';
import GenomicsSection from './drug-sections/GenomicsSection';
import MarketSection from './drug-sections/MarketSection';
import GraphInteractionsSection from './drug-sections/GraphInteractionsSection';
import PathwaysSection from './drug-sections/PathwaysSection';
import BioactivitySection from './drug-sections/BioactivitySection';
import { usePageTitle } from '../../hooks/usePageTitle';
import { NotebookLayout, NotebookNavbar, PencilButton, Loader, EmptyState, Tag, groupTone } from '../../components/notebook';
import '../../styles/drugs.css';

type Tab = 'general' | 'quimica' | 'clinica' | 'targets' | 'grafo' | 'rutas' | 'bioactividad' | 'genomica' | 'mercado' | 'referencias';

const TABS: { key: Tab; label: string; Icon: LucideIcon }[] = [
  { key: 'general', label: 'Farmacología', Icon: FlaskConical },
  { key: 'quimica', label: 'Química', Icon: Beaker },
  { key: 'clinica', label: 'Clínica', Icon: Stethoscope },
  { key: 'targets', label: 'Dianas y Enzimas', Icon: Dna },
  { key: 'grafo', label: 'Red Molecular', Icon: Share2 },
  { key: 'rutas', label: 'Rutas y Efectos', Icon: Map },
  { key: 'bioactividad', label: 'Bioactividad', Icon: Activity },
  { key: 'genomica', label: 'Genómica', Icon: Microscope },
  { key: 'mercado', label: 'Costos y Mercado', Icon: DollarSign },
  { key: 'referencias', label: 'Sinónimos y Refs', Icon: BookMarked },
];

// Wrapper de bloque tipo "ficha de cuaderno" para los paneles inline.
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-4 shadow-[2px_2.5px_0px_rgba(30,25,21,0.06)]">
      <div className="text-[11px] font-bold font-mono tracking-wider text-[#7c2d12] mb-1.5">{label.toUpperCase()}</div>
      <div className="text-[13px] text-stone-700 leading-relaxed">{children}</div>
    </div>
  );
}

export default function DrugDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [drug, setDrug] = useState<DrugRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<Tab>('general');
  usePageTitle(drug?.name || '');

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    drugsApi.detail(id).then((res) => setDrug(res.data))
      .catch(() => setError('Error cargando el perfil del fármaco.')).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <NotebookLayout navbar={<NotebookNavbar />}><Loader label="Desglosando el perfil molecular…" /></NotebookLayout>;
  if (error || !drug) return (
    <NotebookLayout navbar={<NotebookNavbar />}>
      <EmptyState title={error || 'Fármaco no encontrado'} />
      <div className="flex justify-center mt-4"><PencilButton onClick={() => navigate('/drugs')} icon={<ArrowLeft className="w-4 h-4" />}>Volver</PencilButton></div>
    </NotebookLayout>
  );

  let primaryDbId = 'N/A';
  if (drug['drugbank-id']) {
    if (Array.isArray(drug['drugbank-id'])) {
      const pItem = drug['drugbank-id'].find((item: any) => typeof item === 'object' && item?.primary === 'true') || drug['drugbank-id'][0];
      primaryDbId = pItem && typeof pItem === 'object' ? pItem.value : String(pItem);
    } else primaryDbId = String(drug['drugbank-id']);
  }
  const isDbId = primaryDbId !== 'N/A' && ['DB', 'BTD', 'BIOD'].some(p => primaryDbId.toUpperCase().startsWith(p));
  const graphDrugId = isDbId ? primaryDbId : (id ?? '');
  const graphDrugName = isDbId ? undefined : drug.name;

  const exportJson = () => {
    if (!drug) return;
    const blob = new Blob([JSON.stringify(drug, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `${drug.name.replace(/\s+/g, '_') || primaryDbId}.json`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <NotebookLayout navbar={<NotebookNavbar />}>
      <div className="flex gap-2 items-center mb-3">
        <PencilButton onClick={() => navigate('/drugs')} icon={<ArrowLeft className="w-4 h-4" />}>Volver</PencilButton>
        <PencilButton onClick={exportJson} icon={<Download className="w-4 h-4 text-amber-800" />}>JSON</PencilButton>
      </div>

      {/* Cabecera */}
      <div className="flex flex-wrap justify-between items-end gap-3 border-b-2 border-stone-800/15 pb-4">
        <div>
          <h1 className="font-hand font-bold text-4xl text-[#1a140f] leading-none">{drug.name}</h1>
          <p className="mt-1.5 flex items-center gap-2 flex-wrap">
            {drug.type && <Tag tone="blue">{drug.type}</Tag>}
            {Array.isArray(drug.groups) && drug.groups.slice(0, 3).map((g: string) => (
              <Tag key={g} tone={groupTone(g)}>{g}</Tag>
            ))}
            <span className="text-xs text-stone-500 font-mono">Estado: {drug.state || 'N/A'}</span>
          </p>
        </div>
        <div className="text-right">
          <span className="text-lg bg-[#faf6ee] text-sky-800 px-3 py-1.5 rounded-lg border-2 border-stone-800/20 font-bold font-mono">{primaryDbId}</span>
          <p className="mt-1.5 text-stone-500 text-xs font-mono">CAS: {drug['cas-number'] || 'N/A'} · UNII: {drug.unii || 'N/A'}</p>
        </div>
      </div>

      {/* Pestañas */}
      <div className="flex gap-2 border-b border-stone-800/10 pb-3 mt-4 overflow-x-auto scrollbar-none">
        {TABS.map(({ key, label, Icon }) => {
          const active = activeTab === key;
          return (
            <button key={key} onClick={() => setActiveTab(key)}
              className={`px-3 sm:px-4 py-2 sm:py-2.5 rounded-xl font-hand text-sm sm:text-base font-bold flex items-center gap-1.5 sm:gap-2 border-2 transition-all cursor-pointer shrink-0 whitespace-nowrap ${
                active ? 'bg-[#2d2621] text-[#faf6ee] border-[#1e1814] shadow-[2px_2px_0px_#1e1814]' : 'bg-white text-stone-700 border-stone-300 hover:bg-stone-50'
              }`}>
              <Icon className="w-4 h-4 sm:w-5 sm:h-5" /> {label}
            </button>
          );
        })}
      </div>

      <div className="mt-5 flex flex-col gap-4">
        {activeTab === 'general' && (
          <>
            <Field label="Descripción">{drug.description || 'Sin descripción.'}</Field>
            <Field label="Mecanismo de acción">{drug['mechanism-of-action'] || 'No especificado.'}</Field>
            <Field label="Farmacodinamia">{drug.pharmacodynamics || 'No disponible.'}</Field>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Field label="Absorción">{drug.absorption || 'N/A'}</Field>
              <Field label="Metabolismo">{drug.metabolism || 'N/A'}</Field>
              <Field label="Vida media">{drug['half-life'] || drug.half_life || 'N/A'}</Field>
              <Field label="Ruta de eliminación">{drug['route-of-elimination'] || 'N/A'}</Field>
              <Field label="Aclaramiento">{drug.clearance || 'N/A'}</Field>
              <Field label="Volumen de distribución">{drug['volume-of-distribution'] || 'N/A'}</Field>
            </div>
          </>
        )}

        {activeTab === 'quimica' && <ChemistrySection drug={drug} />}
        {activeTab === 'clinica' && <ClinicalSection drug={drug} />}
        {activeTab === 'targets' && <TargetsSection drug={drug} />}
        {activeTab === 'genomica' && <GenomicsSection drug={drug} />}
        {activeTab === 'mercado' && <MarketSection drug={drug} />}
        {activeTab === 'grafo' && <GraphInteractionsSection drugId={graphDrugId} drugName={graphDrugName} />}
        {activeTab === 'rutas' && <PathwaysSection drugId={isDbId ? primaryDbId : (id ?? '')} />}
        {activeTab === 'bioactividad' && <BioactivitySection drugId={isDbId ? primaryDbId : (id ?? '')} />}

        {activeTab === 'referencias' && (
          <>
            <Field label="Sinónimos internacionales">
              <div className="flex gap-2 flex-wrap">
                {Array.isArray(drug.synonyms)
                  ? drug.synonyms.flat(2).map((s: any, idx: number) => {
                      if (!s) return null;
                      const t = s && typeof s === 'object' && 'value' in s ? s.value : String(s);
                      return <span key={idx} className="bg-stone-100 border border-stone-300 px-2.5 py-1 rounded-md text-[13px]">{t}</span>;
                    })
                  : 'N/A'}
              </div>
            </Field>
            <Field label="Referencias bibliográficas">
              <div className="flex flex-col gap-3 mt-1">
                {Array.isArray(drug['general-references']) && drug['general-references'].flat(5).map((ref: any, idx: number) => {
                  if (!ref) return null;
                  const refText = ref.citation || ref.title || String(ref);
                  return (
                    <div key={idx} className="bg-stone-50 p-3 rounded-lg border-l-4 border-indigo-400 text-[13px] text-stone-700">
                      <div className="mb-1.5"><strong>[{idx + 1}]</strong> {refText}</div>
                      <div className="flex gap-2">
                        {ref['pubmed-id'] && <a href={`https://pubmed.ncbi.nlm.nih.gov/${ref['pubmed-id']}/`} target="_blank" rel="noopener noreferrer" className="bg-blue-100 text-blue-800 px-2 py-0.5 rounded text-[11px] font-bold no-underline">PubMed: {ref['pubmed-id']}</a>}
                        {ref.url && <a href={ref.url} target="_blank" rel="noopener noreferrer" className="bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded text-[11px] font-bold no-underline">Enlace externo</a>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </Field>
          </>
        )}
      </div>
    </NotebookLayout>
  );
}
