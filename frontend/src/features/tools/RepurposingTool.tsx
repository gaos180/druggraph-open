import React, { useState } from 'react';
import { Repeat, Download, ChevronDown, ChevronUp } from 'lucide-react';
import { toolsApi, RepurposingResult, RepurposingCandidate, DiseaseEvidenceResult } from '../../api/tools';
import GoEnrichmentChart from './components/GoEnrichmentChart';
import { usePageTitle } from '../../hooks/usePageTitle';
import { HandTitle, PencilButton } from '../../components/notebook';
import ReportPanel from '../reports/ReportPanel';

const cardCls = 'bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-5 mb-4 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]';
const inpCls = 'bg-[#faf6ee] border-2 border-[#3f3429] rounded-lg px-3 py-2 text-[13px] font-hand outline-none';

function JaccardBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const col = value >= 0.5 ? '#15803d' : value >= 0.25 ? '#b45309' : '#2563eb';
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 bg-stone-300/50 rounded-full h-2 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${Math.min(100, pct * 2)}%`, background: col }} />
      </div>
      <span className="text-xs font-mono min-w-[40px]" style={{ color: col }}>{value.toFixed(3)}</span>
    </div>
  );
}

export default function RepurposingTool() {
  usePageTitle('Reposicionamiento');
  const [drugId, setDrugId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<RepurposingResult | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [tab, setTab] = useState<'candidates' | 'go' | 'diseases'>('candidates');
  const [minJaccard, setMinJaccard] = useState(0.1);
  const [diseases, setDiseases] = useState<DiseaseEvidenceResult | null>(null);
  const [diseasesLoading, setDiseasesLoading] = useState(false);
  const [diseasesError, setDiseasesError] = useState('');

  const handleSearch = async () => {
    const id = drugId.trim().toUpperCase();
    if (!id) { setError('Ingresa un DrugBank ID'); return; }
    setLoading(true); setError(''); setResult(null); setDiseases(null); setDiseasesError('');
    try { const res = await toolsApi.repurposing(id); setResult(res.data); setTab('candidates'); }
    catch (err: unknown) { setError((err as any)?.response?.data?.error || (err as any)?.message || 'Error al conectar'); }
    finally { setLoading(false); }
  };

  const loadDiseases = async () => {
    if (!result || diseases || diseasesLoading) return;
    setDiseasesLoading(true); setDiseasesError('');
    try { const res = await toolsApi.diseaseEvidence(result.drug.drugbank_id); setDiseases(res.data); }
    catch (err: any) { setDiseasesError(err?.response?.data?.error || 'No se pudo consultar Open Targets.'); }
    finally { setDiseasesLoading(false); }
  };

  const filtered: RepurposingCandidate[] = result ? result.candidates.filter(c => c.jaccard >= minJaccard) : [];

  const exportCsv = () => {
    if (!result) return;
    const header = 'drugbank_id,name,jaccard,shared_count,targets_a,targets_b,shared_genes';
    const rows = filtered.map(c => [c.drugbank_id, `"${c.name}"`, c.jaccard, c.shared_count, c.targets_a, c.targets_b, `"${c.shared_genes.join(';')}"`].join(','));
    const blob = new Blob([[header, ...rows].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `repurposing_${drugId}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const thc = 'px-2 py-1.5 text-left text-stone-500 font-mono text-[11px]';

  return (
    <div className="max-w-5xl">
      <HandTitle className="text-2xl flex items-center gap-2"><Repeat className="w-6 h-6 text-amber-800" /> Reposicionamiento de Fármacos</HandTitle>
      <p className="text-stone-500 text-[13px] font-hand mt-1 mb-5">Fármacos con perfiles de target similares (Jaccard del conjunto de dianas) para proponer nuevas indicaciones.</p>

      <div className={cardCls}>
        <div className="flex gap-3 items-end flex-wrap">
          <div>
            <label className="text-[11px] text-stone-500 block mb-1 font-mono">DRUGBANK ID DE REFERENCIA</label>
            <input className={`${inpCls} w-72`} value={drugId} onChange={e => setDrugId(e.target.value)} placeholder="DC1234" onKeyDown={e => e.key === 'Enter' && handleSearch()} />
          </div>
          <div>
            <label className="text-[11px] text-stone-500 block mb-1 font-mono">JACCARD MÍNIMO</label>
            <input className={`${inpCls} w-24`} type="number" step="0.01" min="0.05" max="1" value={minJaccard} onChange={e => setMinJaccard(Number(e.target.value))} />
          </div>
          <PencilButton variant="solid" onClick={handleSearch} disabled={loading}>{loading ? 'Buscando…' : 'Buscar candidatos'}</PencilButton>
          {error && <span className="text-red-600 text-[13px]">{error}</span>}
        </div>
      </div>

      {result && (
        <>
          <div className={`${cardCls} flex gap-5 items-center flex-wrap`}>
            <div>
              <div className="text-stone-500 text-[11px] font-mono">FÁRMACO ANALIZADO</div>
              <div className="text-stone-900 text-lg font-bold">{result.drug.name}</div>
              <div className="text-sky-700 text-xs font-mono">{result.drug.drugbank_id}</div>
            </div>
            <div className="w-px bg-stone-300 self-stretch" />
            <div className="text-center"><div className="text-2xl font-bold font-hand text-stone-800">{result.targets.length}</div><div className="text-stone-500 text-xs">Targets</div></div>
            <div className="text-center"><div className="text-2xl font-bold font-hand text-purple-700">{filtered.length}</div><div className="text-stone-500 text-xs">Candidatos (J ≥ {minJaccard})</div></div>
          </div>

          <div className="flex gap-1 border-b border-stone-800/10 items-center">
            {[{ key: 'candidates', label: `Candidatos (${filtered.length})` }, { key: 'go', label: `GO perfil (${result.go_profile.length})` }, { key: 'diseases', label: 'Enfermedades (Open Targets)' }].map(t => (
              <button key={t.key} onClick={() => { setTab(t.key as any); if (t.key === 'diseases') loadDiseases(); }}
                className={`px-4 py-2 text-[13px] font-hand cursor-pointer border-b-2 ${tab === t.key ? 'border-purple-600 text-purple-700' : 'border-transparent text-stone-500'}`}>{t.label}</button>
            ))}
            <div className="flex-1" />
            {tab === 'candidates' && filtered.length > 0 && <PencilButton onClick={exportCsv} icon={<Download className="w-4 h-4 text-amber-800" />} className="my-1">CSV</PencilButton>}
          </div>

          <div className={`${cardCls} rounded-t-none`}>
            {tab === 'candidates' && (
              filtered.length === 0 ? (
                <div className="text-stone-500 text-[13px] font-hand">Sin candidatos con Jaccard ≥ {minJaccard}. Baja el umbral.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-xs">
                    <thead><tr className="border-b border-stone-800/10">{['#', 'Candidato', 'ID', 'Jaccard', 'Comunes', '|A|', '|B|', ''].map((h, i) => <th key={i} className={thc}>{h}</th>)}</tr></thead>
                    <tbody>
                      {filtered.map((c, i) => (
                        <React.Fragment key={c.drugbank_id}>
                          <tr className={`cursor-pointer border-b border-stone-800/5 ${i % 2 ? 'bg-stone-500/5' : ''}`} onClick={() => setExpanded(expanded === c.drugbank_id ? null : c.drugbank_id)}>
                            <td className="px-2 py-1.5 text-stone-500">{i + 1}</td>
                            <td className="px-2 py-1.5 text-stone-800 font-semibold">{c.name}</td>
                            <td className="px-2 py-1.5 text-sky-700 font-mono">{c.drugbank_id}</td>
                            <td className="px-2 py-1.5"><JaccardBar value={c.jaccard} /></td>
                            <td className="px-2 py-1.5 text-amber-700 font-semibold">{c.shared_count}</td>
                            <td className="px-2 py-1.5 text-stone-500">{c.targets_a}</td>
                            <td className="px-2 py-1.5 text-stone-500">{c.targets_b}</td>
                            <td className="px-2 py-1.5 text-stone-500">{expanded === c.drugbank_id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}</td>
                          </tr>
                          {expanded === c.drugbank_id && (
                            <tr className="bg-stone-500/5 border-b border-stone-800/5">
                              <td colSpan={8} className="px-4 py-2.5">
                                <div className="text-stone-500 text-[11px] mb-1.5 font-mono">GENES EN COMÚN:</div>
                                <div className="flex flex-wrap gap-1.5">{c.shared_genes.map(g => <span key={g} className="bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full text-[11px] font-mono">{g}</span>)}</div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}
            {tab === 'go' && (
              <div>
                <div className="text-stone-500 text-xs mb-3 font-hand">Enriquecimiento GO/KEGG de los targets de {result.drug.name}.</div>
                <GoEnrichmentChart terms={result.go_profile} width={920} maxTerms={20} />
              </div>
            )}
            {tab === 'diseases' && (
              <div>
                <div className="text-stone-500 text-xs mb-3 font-hand">
                  Enfermedades asociadas al módulo de dianas de {result.drug.name} según Open Targets (score integrado 0–1). Hipótesis diana→enfermedad para reposicionamiento.
                </div>
                {diseasesLoading && <div className="text-stone-500 text-[13px] font-hand">Consultando Open Targets…</div>}
                {diseasesError && <div className="text-red-600 text-[13px]">{diseasesError}</div>}
                {diseases && diseases.diseases.length === 0 && !diseasesLoading && (
                  <div className="text-stone-500 text-[13px] font-hand">Sin enfermedades asociadas encontradas.</div>
                )}
                {diseases && diseases.diseases.length > 0 && (
                  <table className="w-full border-collapse text-xs">
                    <thead><tr className="border-b border-stone-800/10">{['Enfermedad', 'Score', 'Dianas que la soportan'].map(h => <th key={h} className="px-2 py-1.5 text-left text-stone-500 font-mono text-[11px]">{h}</th>)}</tr></thead>
                    <tbody>
                      {diseases.diseases.map((d, i) => (
                        <tr key={d.disease_id} className={`border-b border-stone-800/5 ${i % 2 ? 'bg-stone-500/5' : ''}`}>
                          <td className="px-2 py-1.5 text-stone-800">
                            <a href={`https://platform.opentargets.org/disease/${d.disease_id}`} target="_blank" rel="noreferrer" className="text-sky-700 no-underline hover:underline">{d.disease_name}</a>
                          </td>
                          <td className="px-2 py-1.5">
                            <span className="font-mono font-semibold" style={{ color: d.score >= 0.6 ? '#15803d' : d.score >= 0.3 ? '#b45309' : '#78716c' }}>{d.score.toFixed(3)}</span>
                          </td>
                          <td className="px-2 py-1.5">
                            <div className="flex flex-wrap gap-1">
                              {d.supporting_genes.map(g => <span key={g} className="bg-purple-100 text-purple-800 px-1.5 py-0.5 rounded text-[11px] font-mono">{g}</span>)}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>

          <div className="mt-4">
            <ReportPanel kind="repurposing" payload={result} />
          </div>
        </>
      )}
    </div>
  );
}
