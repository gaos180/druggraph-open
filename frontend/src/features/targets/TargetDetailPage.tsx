import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import type { LucideIcon } from 'lucide-react';
import { ArrowLeft, Crosshair, Microscope, Share2, Dna, ExternalLink } from 'lucide-react';
import { targetsApi, TargetDetail } from '../../api/targets';
import { usePageTitle } from '../../hooks/usePageTitle';
import { NotebookLayout, NotebookNavbar, PencilButton, Loader, EmptyState, Tag } from '../../components/notebook';
import { UniProtTab, NetworkTab, PathwaysTab } from './tabs';

type Tab = 'info' | 'uniprot' | 'network' | 'pathways';

export default function TargetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [target, setTarget] = useState<TargetDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>('info');
  usePageTitle(target?.name || '');

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    targetsApi.detail(id).then(r => setTarget(r.data)).catch(() => setTarget(null)).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <NotebookLayout navbar={<NotebookNavbar />}><Loader label="Cargando diana…" /></NotebookLayout>;
  if (!target) return (
    <NotebookLayout navbar={<NotebookNavbar />}>
      <EmptyState title="Diana no encontrada" />
      <div className="flex justify-center mt-4"><PencilButton onClick={() => navigate('/targets')} icon={<ArrowLeft className="w-4 h-4" />}>Volver al navegador</PencilButton></div>
    </NotebookLayout>
  );

  const validDrugs = target.drugs.filter(d => d.drugbank_id);
  const tabs: { key: Tab; label: string; Icon: LucideIcon }[] = [
    { key: 'info', label: 'Info DrugBank', Icon: Crosshair },
    { key: 'uniprot', label: 'UniProt', Icon: Microscope },
    { key: 'network', label: `Red (${validDrugs.length})`, Icon: Share2 },
    { key: 'pathways', label: 'Rutas & PPI', Icon: Dna },
  ];

  return (
    <NotebookLayout navbar={<NotebookNavbar />}>
      <PencilButton onClick={() => navigate('/targets')} icon={<ArrowLeft className="w-4 h-4" />} className="mb-3">Dianas</PencilButton>

      {/* Cabecera */}
      <div className="bg-[#faf6ee] border-2 border-[#2b251d] rounded-2xl p-5 mb-5 shadow-[3px_3.5px_0_rgba(43,37,29,0.1)]">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="font-hand font-bold text-2xl text-[#1a140f] flex items-center gap-2 mb-1.5"><Crosshair className="w-6 h-6 text-amber-800" /> {target.name}</h1>
            <div className="flex gap-2.5 flex-wrap items-center">
              {target.gene_name && <code className="text-sm text-sky-700 bg-sky-50 border border-sky-200 px-2.5 py-0.5 rounded-md">{target.gene_name}</code>}
              {target.uniprot_id && <a href={`https://www.uniprot.org/uniprotkb/${target.uniprot_id}`} target="_blank" rel="noopener noreferrer" className="text-sm text-purple-700 font-mono no-underline inline-flex items-center gap-0.5">{target.uniprot_id}<ExternalLink className="w-3 h-3" /></a>}
              <span className="text-[0.83rem] text-stone-500 italic">{target.organism}</span>
            </div>
          </div>
          <div className="bg-indigo-500/10 border-2 border-indigo-500/20 rounded-xl px-4 py-2 text-center">
            <div className="text-indigo-700 text-xl font-bold font-hand">{validDrugs.length}</div>
            <div className="text-stone-500 text-[0.72rem]">fármacos</div>
          </div>
        </div>
        <div className="flex gap-2 mt-3 flex-wrap">
          {target.cellular_location && <Tag tone="blue">📍 {target.cellular_location}</Tag>}
          {target.chromosome_location && <Tag tone="green">🧬 {target.chromosome_location}</Tag>}
          {target.known_action && <Tag tone={target.known_action === 'yes' ? 'green' : 'red'}>Acción conocida: {target.known_action}</Tag>}
        </div>
      </div>

      {/* Pestañas */}
      <div className="flex gap-2 border-b border-stone-800/10 pb-3 mb-5 overflow-x-auto scrollbar-none">
        {tabs.map(({ key, label, Icon }) => (
          <button key={key} onClick={() => setTab(key)}
            className={`px-4 py-2.5 rounded-xl font-hand text-base font-bold flex items-center gap-2 border-2 cursor-pointer transition-all shrink-0 whitespace-nowrap ${
              tab === key ? 'bg-[#2d2621] text-[#faf6ee] border-[#1e1814] shadow-[2px_2px_0px_#1e1814]' : 'bg-white text-stone-700 border-stone-300 hover:bg-stone-50'
            }`}>
            <Icon className="w-5 h-5" /> {label}
          </button>
        ))}
      </div>

      <div>
        {tab === 'info' && (
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-2.5">
              {[
                { label: 'ID DrugBank Target', value: target.id || '—', mono: true },
                { label: 'Gen', value: target.gene_name || '—', mono: true },
                { label: 'UniProt', value: target.uniprot_id || '—', mono: true },
                { label: 'Organismo', value: target.organism || '—' },
                { label: 'Localización cel.', value: target.cellular_location || '—' },
                { label: 'Localización crom.', value: target.chromosome_location || '—' },
                { label: 'Acción conocida', value: target.known_action || '—' },
                { label: 'Fármacos vinculados', value: String(validDrugs.length) },
              ].map(({ label, value, mono }) => (
                <div key={label} className="bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl px-3.5 py-3">
                  <div className="text-[0.7rem] text-stone-500 mb-1 font-bold uppercase tracking-wider font-mono">{label}</div>
                  {mono ? <code className="text-[0.85rem] text-sky-700">{value}</code> : <div className="text-[0.88rem] text-stone-800">{value}</div>}
                </div>
              ))}
            </div>
            {target.uniprot_id && <PencilButton variant="solid" onClick={() => setTab('uniprot')} icon={<Microscope className="w-4 h-4" />} className="self-start">Ver datos en UniProt →</PencilButton>}
          </div>
        )}
        {tab === 'uniprot' && id && <UniProtTab targetId={id} uniprotId={target.uniprot_id} />}
        {tab === 'network' && <NetworkTab target={target} />}
        {tab === 'pathways' && id && <PathwaysTab targetId={id} />}
      </div>
    </NotebookLayout>
  );
}
