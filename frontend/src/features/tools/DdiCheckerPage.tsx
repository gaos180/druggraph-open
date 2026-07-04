import React, { useState } from 'react';
import { Pill, Download } from 'lucide-react';
import { statsApi, DdiPairResult, DdiSingleResult, DdiRiskResult } from '../../api/stats';
import { toolsApi, ProximityResult } from '../../api/tools';
import { usePageTitle } from '../../hooks/usePageTitle';
import { HandTitle, PencilButton, Tag } from '../../components/notebook';
import ReportPanel from '../reports/ReportPanel';

const cardCls = 'bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-5 mb-4 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]';
const inpCls = 'w-full bg-[#faf6ee] border-2 border-[#3f3429] rounded-lg px-3 py-2 text-[13px] font-hand outline-none';
const lblCls = 'text-[11px] text-stone-500 mb-1 block font-mono';

type Mode = 'pair' | 'single';

const RISK_COLOR: Record<string, string> = { 'sin_señales': '#78716c', bajo: '#15803d', moderado: '#b45309', alto: '#b91c1c' };
const RISK_LABEL: Record<string, string> = { 'sin_señales': 'Sin señales', bajo: 'Bajo', moderado: 'Moderado', alto: 'Alto' };

/**
 * DdiRiskCard — riesgo de interacción PREDICHO (mecanístico PK/PD, sin ML).
 * Complementa el DDI documentado con señales de CYP compartido y dianas/rutas comunes.
 */
function DdiRiskCard({ drugA, drugB }: { drugA: string; drugB: string }) {
  const [data, setData] = React.useState<DdiRiskResult | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');

  const load = async () => {
    setLoading(true); setError('');
    try { const res = await statsApi.ddiRisk(drugA, drugB); setData(res.data); }
    catch (err: any) { setError(err?.response?.data?.error || 'No se pudo calcular el riesgo.'); }
    finally { setLoading(false); }
  };

  const color = data ? RISK_COLOR[data.risk_level] : '#78716c';

  return (
    <div className="bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-5 mb-4 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
        <div className="font-hand font-bold text-lg text-stone-900">Riesgo de interacción predicho (PK/PD)</div>
        {!data && <PencilButton onClick={load} disabled={loading}>{loading ? 'Analizando…' : 'Estimar riesgo'}</PencilButton>}
      </div>
      <p className="text-[12px] text-stone-500 font-hand mb-2">
        Estimación mecanística in-silico: CYP450 compartido (farmacocinético) y dianas/rutas comunes (farmacodinámico). No sustituye una base clínica de interacciones.
      </p>
      {error && <div className="text-red-600 text-[13px]">{error}</div>}
      {data && (
        <>
          <div className="flex items-center gap-5 flex-wrap mb-3">
            <div className="text-center">
              <div className="text-4xl font-extrabold font-hand leading-none" style={{ color }}>{data.risk_score}</div>
              <div className="text-[11px] text-stone-500">/ 10</div>
            </div>
            <div>
              <div className="text-sm font-bold" style={{ color }}>Riesgo {RISK_LABEL[data.risk_level]}</div>
              <div className="text-[12px] text-stone-500">
                {data.shared_cyps.length} CYP compartido(s) · {data.shared_targets.length} diana(s) común(es) · Jaccard {data.jaccard}
                {data.proximity?.d_c_symmetric != null && ` · d_c ${data.proximity.d_c_symmetric}`}
              </div>
            </div>
          </div>
          {data.signals.length === 0 && <div className="text-stone-500 text-[13px] font-hand">Sin señales mecanísticas detectadas.</div>}
          {data.signals.map((s, i) => (
            <div key={i} className="rounded-lg p-2.5 mb-1.5 border" style={{ borderColor: s.level === 'high' ? '#b91c1c55' : '#b4530955', background: s.level === 'high' ? '#fef2f2' : '#fffbeb' }}>
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-[11px] font-bold px-1.5 py-0.5 rounded" style={{ color: s.type === 'PK' ? '#7c2d12' : '#3730a3', background: s.type === 'PK' ? '#fed7aa' : '#e0e7ff' }}>{s.type}</span>
                {s.gene && <span className="text-xs font-mono text-sky-800">{s.gene}</span>}
              </div>
              <div className="text-[13px] text-stone-700">{s.message}</div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

/**
 * ProximityCard — proximidad de red (network medicine) entre los módulos de dianas
 * de dos fármacos en el interactoma STRING. d_c baja ⇒ módulos cercanos.
 */
function ProximityCard({ drugA, drugB }: { drugA: string; drugB: string }) {
  const [data, setData] = React.useState<ProximityResult | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');

  const load = async () => {
    setLoading(true); setError('');
    try {
      const res = await toolsApi.proximity(drugA, drugB);
      setData(res.data);
    } catch (err: any) {
      setError(err?.response?.status === 503
        ? 'Requiere la red STRING cargada (load_string_network.py).'
        : (err?.response?.data?.error || 'No se pudo calcular la proximidad.'));
    } finally { setLoading(false); }
  };

  const dc = data?.d_c_symmetric;
  const tone = dc == null ? '#57534e' : dc <= 1 ? '#15803d' : dc <= 2 ? '#b45309' : '#b91c1c';
  const label = dc == null ? '—' : dc <= 1 ? 'Muy cercanos' : dc <= 2 ? 'Cercanos' : 'Distantes';

  return (
    <div className="bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-5 mb-4 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
        <div className="font-hand font-bold text-lg text-stone-900">Proximidad de red (interactoma)</div>
        {!data && <PencilButton onClick={load} disabled={loading}>{loading ? 'Calculando…' : 'Calcular proximidad'}</PencilButton>}
      </div>
      <p className="text-[12px] text-stone-500 font-hand mb-2">
        Distancia media de camino más corto entre los módulos de dianas en la red STRING (métrica d<sub>c</sub>, Guney 2016). Menor = más relacionados funcionalmente.
      </p>
      {error && <div className="text-red-600 text-[13px]">{error}</div>}
      {data && data.available && dc != null && (
        <div className="flex items-center gap-5 flex-wrap">
          <div className="text-center">
            <div className="text-4xl font-extrabold font-hand leading-none" style={{ color: tone }}>{dc}</div>
            <div className="text-[11px] text-stone-500">saltos (d_c)</div>
          </div>
          <div>
            <div className="text-sm font-bold" style={{ color: tone }}>{label}</div>
            <div className="text-[12px] text-stone-500">
              {data.genes_a_used.length} vs {data.genes_b_used.length} genes en red · cobertura {Math.round(data.coverage_a * 100)}%
            </div>
          </div>
        </div>
      )}
      {data && data.available && dc == null && (
        <div className="text-stone-500 text-[13px]">Sin camino en la red entre los módulos (dianas no conectadas dentro del límite).</div>
      )}
    </div>
  );
}

export default function DdiCheckerPage() {
  usePageTitle('DDI Checker');
  const [mode, setMode] = useState<Mode>('pair');
  const [drugA, setDrugA] = useState('');
  const [drugB, setDrugB] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<DdiPairResult | DdiSingleResult | null>(null);
  const [search, setSearch] = useState('');

  const handleCheck = async () => {
    const a = drugA.trim().toUpperCase();
    const b = drugB.trim().toUpperCase();
    if (!a) { setError('Ingresa al menos el primer DrugBank ID'); return; }
    if (mode === 'pair' && !b) { setError('Ingresa el segundo DrugBank ID'); return; }
    setLoading(true); setError(''); setResult(null); setSearch('');
    try {
      const res = await statsApi.checkDdi(a, mode === 'pair' ? b : undefined);
      setResult(res.data);
    } catch (e: unknown) {
      setError((e as any)?.response?.data?.error || (e as any)?.message || 'Error al conectar con el servidor');
    } finally { setLoading(false); }
  };

  const exportCsv = () => {
    if (!result || result.mode !== 'single') return;
    const header = 'drugbank_id,name,description';
    const rows = result.interactions.map(i => `${i.drugbank_id},"${i.name}","${(i.description || '').replace(/"/g, "'")}"`);
    const blob = new Blob([[header, ...rows].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `ddi_${drugA}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const filtered = result?.mode === 'single'
    ? result.interactions.filter(i => !search || i.name.toLowerCase().includes(search.toLowerCase()) || i.drugbank_id.toLowerCase().includes(search.toLowerCase()))
    : [];

  return (
    <div className="max-w-4xl">
      <HandTitle className="text-2xl flex items-center gap-2"><Pill className="w-6 h-6 text-amber-800" /> Verificador de Interacciones DDI</HandTitle>
      <p className="text-stone-500 text-[13px] font-hand mt-1 mb-5">Consulta interacciones fármaco-fármaco registradas en el grafo Neo4j.</p>

      <div className={cardCls}>
        <div className="flex gap-2 mb-4">
          {([['pair', 'Verificar par A ↔ B'], ['single', 'Todas las DDIs de un fármaco']] as [Mode, string][]).map(([m, label]) => (
            <button key={m} onClick={() => { setMode(m); setResult(null); setError(''); }}
              className={`px-5 py-2 rounded-lg text-sm font-hand border-2 cursor-pointer ${mode === m ? 'bg-[#2d2621] text-[#faf6ee] border-[#1e1814]' : 'bg-white text-stone-600 border-stone-300'}`}>
              {label}
            </button>
          ))}
        </div>
        <div className={`grid ${mode === 'pair' ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1'} gap-4 mb-4`}>
          <div>
            <span className={lblCls}>DRUGBANK ID — FÁRMACO A</span>
            <input className={inpCls} value={drugA} onChange={e => setDrugA(e.target.value)} placeholder="DC1234" onKeyDown={e => e.key === 'Enter' && handleCheck()} />
          </div>
          {mode === 'pair' && (
            <div>
              <span className={lblCls}>DRUGBANK ID — FÁRMACO B</span>
              <input className={inpCls} value={drugB} onChange={e => setDrugB(e.target.value)} placeholder="DC1815" onKeyDown={e => e.key === 'Enter' && handleCheck()} />
            </div>
          )}
        </div>
        <div className="flex gap-3 items-center">
          <PencilButton variant="solid" onClick={handleCheck} disabled={loading}>{loading ? 'Consultando…' : mode === 'pair' ? 'Verificar interacción' : 'Buscar DDIs'}</PencilButton>
          {error && <span className="text-red-600 text-[13px]">{error}</span>}
        </div>
      </div>

      {result?.mode === 'pair' && (() => {
        const r = result as DdiPairResult;
        return (
          <div className={`rounded-xl p-5 mb-4 border-2 ${r.interacts ? 'bg-amber-50 border-amber-400' : 'bg-emerald-50 border-emerald-300'}`}>
            <div className={`flex items-center gap-3.5 ${r.description ? 'mb-4' : ''}`}>
              <span className="text-3xl">{r.interacts ? '⚠️' : '✅'}</span>
              <div>
                <div className={`text-base font-bold ${r.interacts ? 'text-amber-700' : 'text-emerald-700'}`}>{r.interacts ? 'Interacción detectada' : 'Sin interacción registrada'}</div>
                <div className="text-[13px] text-stone-500 mt-0.5">
                  <span className="text-sky-700">{r.drug_a.name}</span> <span className="text-stone-500">({r.drug_a.drugbank_id})</span> ↔ <span className="text-sky-700">{r.drug_b.name}</span> <span className="text-stone-500">({r.drug_b.drugbank_id})</span>
                </div>
              </div>
            </div>
            {r.description && <div className="bg-amber-100/60 border border-amber-300 rounded-lg p-3.5 text-amber-900 text-[13px] leading-relaxed">{r.description}</div>}
          </div>
        );
      })()}

      {result?.mode === 'pair' && (
        <>
          <DdiRiskCard
            drugA={(result as DdiPairResult).drug_a.drugbank_id}
            drugB={(result as DdiPairResult).drug_b.drugbank_id}
          />
          <ProximityCard
            drugA={(result as DdiPairResult).drug_a.drugbank_id}
            drugB={(result as DdiPairResult).drug_b.drugbank_id}
          />
        </>
      )}

      {result?.mode === 'single' && (() => {
        const r = result as DdiSingleResult;
        return (
          <div className={cardCls}>
            <div className="flex justify-between items-center mb-3.5 flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <span className="text-sky-700 font-bold">{r.drug.name}</span>
                <span className="text-stone-500 text-xs font-mono">{r.drug.drugbank_id}</span>
                <Tag tone="blue">{r.interaction_count} interacciones</Tag>
              </div>
              {r.interaction_count > 0 && <PencilButton onClick={exportCsv} icon={<Download className="w-4 h-4 text-amber-800" />}>CSV</PencilButton>}
            </div>
            {r.interaction_count === 0 ? (
              <div className="text-stone-500 text-[13px] font-hand">No se encontraron interacciones DDI para este fármaco.</div>
            ) : (
              <>
                <input className={`${inpCls} mb-3`} placeholder="Buscar por nombre o DrugBank ID…" value={search} onChange={e => setSearch(e.target.value)} />
                <div className="max-h-[460px] overflow-y-auto rounded-lg border border-stone-800/10">
                  <table className="w-full border-collapse text-xs">
                    <thead className="sticky top-0 bg-[#efe7d6] z-10">
                      <tr>{['Fármaco', 'DrugBank ID', 'Descripción'].map(h => <th key={h} className="text-left px-2.5 py-2 text-stone-500 font-mono text-[11px]">{h}</th>)}</tr>
                    </thead>
                    <tbody>
                      {filtered.map((i, idx) => (
                        <tr key={i.drugbank_id} className={`border-t border-stone-800/10 ${idx % 2 ? 'bg-stone-500/5' : ''}`}>
                          <td className="px-2.5 py-2 text-stone-800 font-medium">{i.name}</td>
                          <td className="px-2.5 py-2 text-sky-700 font-mono whitespace-nowrap">{i.drugbank_id}</td>
                          <td className="px-2.5 py-2 text-stone-600 leading-relaxed">{i.description || <span className="text-stone-300">—</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {filtered.length === 0 && search && <div className="text-stone-500 text-[13px] p-4">Sin resultados para "{search}"</div>}
                </div>
              </>
            )}
          </div>
        );
      })()}

      {result && (
        <div className="mt-4">
          <ReportPanel kind="ddi" payload={result} />
        </div>
      )}
    </div>
  );
}
