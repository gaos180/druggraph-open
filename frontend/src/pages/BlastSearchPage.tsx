/**
 * BlastSearchPage — Búsqueda por secuencia: el usuario pega una secuencia de
 * aminoácidos (FASTA) y obtiene targets homólogos + los fármacos que los afectan.
 */
import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Microscope, Search, ExternalLink, Pill } from 'lucide-react';
import { blastApi, BlastSearchResponse, BlastHit } from '../api/blast';
import { usePageTitle } from '../hooks/usePageTitle';
import { NotebookLayout, NotebookNavbar, HandTitle, PencilButton, Loader, EmptyState } from '../components/notebook';

const EXAMPLE_SEQUENCE = `>ejemplo_PBP2a_MRSA
MKKIKIVPLILIVVVVGFGIYFYASKDKEINNTIDAIEDKNFKQVYKDSSYISKSDNGEV
EMTERPIKIYNSLGVKDINIQDRKIKKVSKNKKRVDAQYKIKTNYGNIDRNVQFNFVKED
GMWKLDWDHSVIIPGMQKDQSIHIENLKSERGKILDRNNVELANTGTAYEIGIVPKNVSK`;

function identityColor(pident: number): string {
  if (pident >= 90) return '#15803d';
  if (pident >= 60) return '#4d7c0f';
  if (pident >= 40) return '#b45309';
  if (pident >= 25) return '#c2410c';
  return '#b91c1c';
}
function formatEvalue(e: number): string {
  if (e === 0) return '0';
  if (e < 1e-3) return e.toExponential(1);
  return e.toFixed(4);
}

function IdentityBadge({ pident }: { pident: number }) {
  const color = identityColor(pident);
  return (
    <span className="px-2.5 py-1 rounded-md font-bold text-[13px] font-mono whitespace-nowrap border"
      style={{ background: `${color}1a`, color, borderColor: `${color}55` }}>{pident}% id</span>
  );
}

function DrugChip({ drug }: { drug: BlastHit['drugs'][number] }) {
  const navigate = useNavigate();
  return (
    <button onClick={() => navigate(`/drugs/${drug.drugbank_id}`)}
      title={drug.actions.length ? `Acciones: ${drug.actions.join(', ')}` : undefined}
      className="bg-purple-100 border border-purple-300 text-purple-800 px-2.5 py-1 rounded-md text-xs cursor-pointer inline-flex items-center gap-1.5 hover:bg-purple-200">
      {drug.name}
      {drug.actions.length > 0 && <span className="text-purple-500 text-[11px]">({drug.actions.slice(0, 2).join(', ')}{drug.actions.length > 2 ? '…' : ''})</span>}
    </button>
  );
}

function HitCard({ hit }: { hit: BlastHit }) {
  const { target, alignment, drugs } = hit;
  return (
    <div className="bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-4 flex flex-col gap-2.5 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]">
      <div className="flex justify-between items-start gap-2.5">
        <div>
          <div className="text-stone-900 font-bold text-[15px]">{target.name || target.drugbank_target_id}</div>
          <div className="flex gap-2.5 flex-wrap mt-1 text-[11px] font-mono">
            <span className="text-sky-700">{target.drugbank_target_id}</span>
            {target.uniprot_id && <a href={`https://www.uniprot.org/uniprotkb/${target.uniprot_id}`} target="_blank" rel="noopener noreferrer" className="text-purple-700 no-underline inline-flex items-center gap-0.5">{target.uniprot_id}<ExternalLink className="w-3 h-3" /></a>}
            {target.gene_name && <span className="text-stone-500">gen: {target.gene_name}</span>}
            {target.organism && <span className="text-stone-500 italic">{target.organism}</span>}
          </div>
        </div>
        <IdentityBadge pident={alignment.pident} />
      </div>
      <div className="flex gap-4 flex-wrap text-xs text-stone-500">
        <span>E-value: <span className="text-stone-700 font-mono">{formatEvalue(alignment.evalue)}</span></span>
        <span>Bitscore: <span className="text-stone-700 font-mono">{alignment.bitscore}</span></span>
        <span>Long.: <span className="text-stone-700 font-mono">{alignment.align_length}</span></span>
        <span>Query: <span className="text-stone-700 font-mono">{alignment.qstart}–{alignment.qend}</span></span>
      </div>
      {drugs.length > 0 ? (
        <div>
          <div className="text-xs text-stone-500 mb-1.5 flex items-center gap-1"><Pill className="w-3.5 h-3.5" /> {drugs.length} fármaco{drugs.length !== 1 ? 's' : ''} sobre este target:</div>
          <div className="flex gap-1.5 flex-wrap">{drugs.map((d) => <DrugChip key={d.drugbank_id} drug={d} />)}</div>
        </div>
      ) : <div className="text-xs text-stone-500 italic">Sin fármacos asociados en el grafo.</div>}
    </div>
  );
}

export default function BlastSearchPage() {
  usePageTitle('Búsqueda BLAST');
  const [sequence, setSequence] = useState('');
  const [evalue, setEvalue] = useState('1e-3');
  const [minIdentity, setMinIdentity] = useState(0);
  const [organismFilter, setOrganismFilter] = useState('');
  const [result, setResult] = useState<BlastSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!sequence.trim()) { setError('Ingresa una secuencia de aminoácidos.'); return; }
    setLoading(true); setError(''); setResult(null); setOrganismFilter('');
    let evalueNum = 1e-3;
    try { evalueNum = parseFloat(evalue) || 1e-3; } catch { evalueNum = 1e-3; }
    blastApi.search({ sequence: sequence.trim(), evalue: evalueNum, min_identity: minIdentity })
      .then((res) => setResult(res.data))
      .catch((err) => setError(err?.response?.data?.error || 'Error en la búsqueda por secuencia.'))
      .finally(() => setLoading(false));
  };

  const displayedHits = useMemo(() => {
    if (!result) return [];
    if (!organismFilter) return result.hits;
    return result.hits.filter((h) => h.target.organism === organismFilter);
  }, [result, organismFilter]);

  return (
    <NotebookLayout navbar={<NotebookNavbar />}>
      <div className="mb-5">
        <HandTitle className="text-3xl flex items-center gap-2"><Microscope className="w-7 h-7 text-amber-800" /> Búsqueda por Secuencia (BLAST)</HandTitle>
        <p className="text-sm text-stone-500 font-hand mt-1">Pega una secuencia de aminoácidos y encuentra proteínas homólogas y los fármacos que las afectan.</p>
      </div>

      <form onSubmit={handleSearch} className="bg-stone-500/5 border border-stone-800/10 rounded-2xl p-5 flex flex-col gap-4">
        <div>
          <label className="block text-[11px] font-mono text-stone-500 mb-1.5">SECUENCIA (TEXTO PLANO O FASTA) *</label>
          <textarea value={sequence} onChange={(e) => setSequence(e.target.value)} rows={7}
            placeholder=">mi_proteina&#10;MKKIKIVPLILIVVVVGFGIYFYASKDKEINNT..."
            className="w-full bg-[#faf6ee] border-2 border-[#3f3429] rounded-xl p-3 text-[13px] font-mono outline-none resize-y leading-relaxed" />
          <div className="flex gap-2 mt-2 items-center flex-wrap">
            <PencilButton type="button" onClick={() => setSequence(EXAMPLE_SEQUENCE)}>Cargar ejemplo (PBP2a MRSA)</PencilButton>
            {sequence && <PencilButton type="button" onClick={() => setSequence('')}>Limpiar</PencilButton>}
          </div>
        </div>

        <div className="flex gap-5 flex-wrap items-end">
          <div>
            <label className="block text-[11px] font-mono text-stone-500 mb-1">E-VALUE MÁXIMO</label>
            <input value={evalue} onChange={(e) => setEvalue(e.target.value)} className="bg-[#faf6ee] border-2 border-[#3f3429] rounded-lg px-3 py-2 text-sm w-32 font-mono outline-none" />
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="block text-[11px] font-mono text-stone-500 mb-1">IDENTIDAD MÍNIMA: <span className="font-mono" style={{ color: identityColor(minIdentity) }}>{minIdentity}%</span></label>
            <input type="range" min={0} max={100} step={5} value={minIdentity} onChange={(e) => setMinIdentity(Number(e.target.value))} className="w-full accent-stone-700" />
          </div>
        </div>

        {error && <div className="bg-red-50 border border-red-300 text-red-700 px-3.5 py-2.5 rounded-lg text-sm">⚠ {error}</div>}

        <PencilButton type="submit" variant="solid" disabled={loading} icon={<Search className="w-4 h-4" />} className="justify-center py-3">
          {loading ? 'Ejecutando BLAST…' : 'Buscar homólogos'}
        </PencilButton>
      </form>

      {loading && <Loader label="Ejecutando BLAST contra la base de datos…" />}

      {result && !loading && (
        <div className="mt-6 flex flex-col gap-4">
          <div className="flex justify-between items-center flex-wrap gap-3 bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl px-4 py-3">
            <div className="text-stone-600 text-sm font-hand">
              <span className="text-sky-700 font-bold">{result.hit_count}</span> homólogos para una query de <span className="font-mono">{result.query_length}</span> aa
              {organismFilter && <span className="text-stone-500"> · mostrando {displayedHits.length} de {result.hit_count}</span>}
            </div>
            {result.organisms.length > 0 && (
              <select value={organismFilter} onChange={(e) => setOrganismFilter(e.target.value)} className="bg-[#faf6ee] border-2 border-[#3f3429] rounded-lg px-3 py-1.5 text-sm font-hand outline-none cursor-pointer">
                <option value="">Todos los organismos ({result.organisms.length})</option>
                {result.organisms.map((org) => <option key={org} value={org}>{org}</option>)}
              </select>
            )}
          </div>

          {displayedHits.length === 0 ? (
            <EmptyState title={result.hit_count === 0 ? 'No se encontraron homólogos' : 'Ningún resultado para el organismo'} hint={result.hit_count === 0 ? 'Prueba relajando el E-value o la identidad mínima.' : undefined} icon={<Microscope className="w-10 h-10 text-stone-500" />} />
          ) : (
            <div className="flex flex-col gap-2.5">{displayedHits.map((hit, idx) => <HitCard key={`${hit.target.drugbank_target_id}-${idx}`} hit={hit} />)}</div>
          )}
        </div>
      )}
    </NotebookLayout>
  );
}
