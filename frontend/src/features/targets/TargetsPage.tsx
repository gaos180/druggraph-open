import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Crosshair, ExternalLink, GitCompare } from 'lucide-react';
import { targetsApi, TargetRecord } from '../../api/targets';
import { usePageTitle } from '../../hooks/usePageTitle';
import { NotebookLayout, NotebookNavbar, HandTitle, PencilButton, Tag } from '../../components/notebook';

export default function TargetsPage() {
  const navigate = useNavigate();
  usePageTitle('Dianas');
  const [search, setSearch] = useState('');
  const [onlyHuman, setOnlyHuman] = useState(false);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ results: TargetRecord[]; total: number; has_next: boolean; has_prev: boolean } | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchInput, setSearchInput] = useState('');

  const fetchTargets = useCallback((s: string, human: boolean, p: number) => {
    setLoading(true);
    targetsApi.list({ search: s, organism: human ? 'Humans' : '', page: p, per_page: 25 })
      .then(res => setData(res.data)).catch(() => setData(null)).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => { setPage(1); setSearch(searchInput); }, 350);
    return () => clearTimeout(timeout);
  }, [searchInput]);
  useEffect(() => { fetchTargets(search, onlyHuman, page); }, [search, onlyHuman, page, fetchTargets]);

  const th = 'text-left px-3.5 py-2.5 text-stone-500 text-[11px] font-bold uppercase tracking-wider font-mono';
  const td = 'px-3.5 py-2.5 text-sm';

  return (
    <NotebookLayout navbar={<NotebookNavbar />}>
      <div className="mb-5 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <HandTitle className="text-3xl flex items-center gap-2"><Crosshair className="w-7 h-7 text-amber-800" /> Navegador de Dianas</HandTitle>
          <p className="text-sm text-stone-500 font-hand mt-1">
            Explora las {data ? data.total.toLocaleString() : '…'} proteínas diana de la red. Clic en una fila para ver su perfil UniProt.
          </p>
        </div>
        <PencilButton
          onClick={() => navigate('/targets/compare')}
          icon={<GitCompare className="w-4 h-4" />}
          variant="solid"
          className="shrink-0"
        >
          Comparar dianas
        </PencilButton>
      </div>

      <div className="flex gap-3 items-center mb-4 flex-wrap">
        <div className="flex-1 min-w-[240px]">
          <input value={searchInput} onChange={e => setSearchInput(e.target.value)} placeholder="Buscar por nombre, gen o UniProt…"
            className="w-full bg-[#faf6ee] px-3 py-2.5 border-2 border-[#3f3429] rounded-xl font-hand text-base focus:outline-none focus:ring-1 focus:ring-stone-600" />
        </div>
        <label className="flex items-center gap-2 text-stone-600 text-sm font-hand cursor-pointer select-none">
          <input type="checkbox" checked={onlyHuman} onChange={e => { setOnlyHuman(e.target.checked); setPage(1); }} className="w-4 h-4 cursor-pointer accent-stone-700" />
          Solo proteínas humanas
        </label>
        {loading && <span className="text-stone-500 text-xs font-hand">Cargando…</span>}
      </div>

      <div className="bg-[#faf6ee] border-2 border-[#2b251d] rounded-2xl overflow-hidden shadow-[3px_3.5px_0_rgba(43,37,29,0.1)]">
        <div className="overflow-x-auto scrollbar-none">
        <table className="w-full border-collapse min-w-[600px]">
          <thead>
            <tr className="bg-[#efe7d6]">
              {['Nombre', 'Gen', 'UniProt', 'Organismo', 'Fármacos'].map(h => <th key={h} className={th}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {!loading && data?.results.length === 0 && (
              <tr><td colSpan={5} className="p-8 text-center text-stone-500 font-hand">No se encontraron dianas con los filtros actuales.</td></tr>
            )}
            {data?.results.map((t, i) => (
              <tr key={t.id || i} onClick={() => t.id && navigate(`/targets/${t.id}`)}
                className={`border-t border-stone-800/10 transition-colors ${t.id ? 'cursor-pointer hover:bg-[#f0e9da]' : ''}`}>
                <td className={`${td} text-stone-800 font-medium`}>{t.name}</td>
                <td className={td}><code className="text-sky-700 text-xs font-bold">{t.gene_name || '—'}</code></td>
                <td className={td}>
                  {t.uniprot_id
                    ? <a href={`https://www.uniprot.org/uniprotkb/${t.uniprot_id}`} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}
                        className="text-purple-700 text-xs font-mono no-underline inline-flex items-center gap-1">{t.uniprot_id} <ExternalLink className="w-3 h-3" /></a>
                    : <span className="text-stone-300 text-xs">—</span>}
                </td>
                <td className={`${td} text-stone-500 text-xs`}>{t.organism || '—'}</td>
                <td className={td}><Tag tone="blue">{t.drug_count}</Tag></td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      {data && (data.has_prev || data.has_next) && (
        <div className="flex justify-center gap-4 mt-4 items-center font-hand">
          <PencilButton disabled={!data.has_prev} onClick={() => setPage(p => p - 1)}>← Anterior</PencilButton>
          <span className="text-stone-600 text-sm">Página {page}</span>
          <PencilButton disabled={!data.has_next} onClick={() => setPage(p => p + 1)}>Siguiente →</PencilButton>
        </div>
      )}
    </NotebookLayout>
  );
}
