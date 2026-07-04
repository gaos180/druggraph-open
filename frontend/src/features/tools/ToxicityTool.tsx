import React, { useState } from 'react';
import { AlertTriangle, Download, ChevronDown, ChevronUp } from 'lucide-react';
import { toolsApi, ToxicityResult, ToxAlert, CypInteraction, PredictedOfftarget, ClusterPeer } from '../../api/tools';
import { usePageTitle } from '../../hooks/usePageTitle';
import { HandTitle, PencilButton } from '../../components/notebook';
import ReportPanel from '../reports/ReportPanel';

const cardCls = 'bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-5 mb-4 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]';
const LEVEL_COLOR: Record<string, string> = { high: '#b91c1c', medium: '#b45309', low: '#2563eb' };
const LEVEL_BG: Record<string, string> = { high: 'bg-red-50', medium: 'bg-amber-50', low: 'bg-blue-50' };
const RISK_COLOR: Record<string, string> = { sin_datos: '#78716c', bajo: '#15803d', moderado: '#b45309', alto: '#c2410c', muy_alto: '#b91c1c' };
const RISK_LABEL: Record<string, string> = { sin_datos: 'Sin datos', bajo: 'Bajo', moderado: 'Moderado', alto: 'Alto', muy_alto: 'Muy alto' };
const thc = 'px-2 py-1.5 text-left text-stone-500 font-mono text-[11px]';
const pill = (lvl: string) => ({ color: LEVEL_COLOR[lvl], background: `${LEVEL_COLOR[lvl]}1a` });

function RiskMeter({ score, level }: { score: number; level: string }) {
  const color = RISK_COLOR[level] ?? '#78716c';
  return (
    <div className="flex items-center gap-5 flex-wrap">
      <div className="text-center">
        <div className="text-5xl font-extrabold font-hand leading-none" style={{ color }}>{score}</div>
        <div className="text-[11px] text-stone-500">/ 10</div>
      </div>
      <div className="flex-1 min-w-[200px]">
        <div className="text-sm font-bold mb-1.5" style={{ color }}>Riesgo {RISK_LABEL[level]}</div>
        <div className="bg-stone-300/50 rounded-md h-3 overflow-hidden">
          <div className="h-full rounded-md transition-all duration-500" style={{ width: `${(score / 10) * 100}%`, background: color }} />
        </div>
        <div className="flex justify-between mt-1">{['0', '2', '4', '6', '8', '10'].map(v => <span key={v} className="text-[10px] text-stone-500">{v}</span>)}</div>
      </div>
    </div>
  );
}

function AlertCard({ alert }: { alert: ToxAlert }) {
  const [open, setOpen] = useState(false);
  const col = LEVEL_COLOR[alert.level];
  return (
    <div onClick={() => setOpen(o => !o)} className={`rounded-lg p-3 mb-2 cursor-pointer border ${LEVEL_BG[alert.level]}`} style={{ borderColor: `${col}55`, borderLeft: `3px solid ${col}` }}>
      <div className="flex gap-2.5 items-center">
        <span className="text-base">{alert.icon}</span>
        <div className="flex-1">
          <div className="flex gap-2 items-center flex-wrap">
            <span className="text-[11px] font-bold px-2 py-0.5 rounded-full" style={pill(alert.level)}>{alert.level.toUpperCase()}</span>
            <span className="text-[11px] text-stone-500">{alert.category}</span>
            <span className="text-xs text-sky-700 font-mono font-semibold">{alert.gene_name}</span>
            <span className="text-xs text-stone-500">{alert.rel_type}</span>
          </div>
          <div className="text-[13px] text-stone-800 mt-1 font-medium">{alert.target_name}</div>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-stone-500" /> : <ChevronDown className="w-4 h-4 text-stone-500" />}
      </div>
      {open && (
        <div className="mt-2.5 pt-2.5" style={{ borderTop: `1px solid ${col}33` }}>
          <p className="text-stone-600 text-[13px] leading-relaxed m-0">{alert.message}</p>
          {alert.uniprot_id && <div className="mt-2 text-xs text-stone-500">UniProt: <span className="text-sky-700 font-mono">{alert.uniprot_id}</span></div>}
        </div>
      )}
    </div>
  );
}

function CypTable({ cyps }: { cyps: CypInteraction[] }) {
  if (!cyps.length) return <p className="text-stone-500 text-[13px] font-hand">Sin interacciones CYP documentadas.</p>;
  return (
    <table className="w-full border-collapse text-xs">
      <thead><tr className="border-b border-stone-800/10">{['Enzima', 'Tipo', 'Riesgo', 'Implicación'].map(h => <th key={h} className={thc}>{h}</th>)}</tr></thead>
      <tbody>
        {cyps.map((c, i) => (
          <tr key={i} className={`border-b border-stone-800/5 ${i % 2 ? 'bg-stone-500/5' : ''}`}>
            <td className="px-2 py-1.5 text-sky-700 font-mono font-semibold">{c.gene}</td>
            <td className="px-2 py-1.5 text-stone-600">{c.rel_type}</td>
            <td className="px-2 py-1.5"><span className="px-2 py-0.5 rounded-full text-[11px] font-semibold" style={pill(c.level)}>{c.level.toUpperCase()}</span></td>
            <td className="px-2 py-1.5 text-stone-500 text-[11px] max-w-[340px]">{c.note.split(':')[0]}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function OfftargetsTable({ items }: { items: PredictedOfftarget[] }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? items : items.slice(0, 12);
  if (!items.length) return <p className="text-stone-500 text-[13px] font-hand">Sin off-targets predichos.</p>;
  return (
    <div>
      <div className="text-stone-500 text-xs mb-2.5 font-hand">Off-targets predichos por similitud topológica (Adamic-Adar). Resaltados = anti-targets conocidos.</div>
      <table className="w-full border-collapse text-xs">
        <thead><tr className="border-b border-stone-800/10">{['Gen', 'Proteína', 'Score AA', 'Vía', 'Anti-target?'].map(h => <th key={h} className={thc}>{h}</th>)}</tr></thead>
        <tbody>
          {visible.map((t, i) => (
            <tr key={i} className={`border-b border-stone-800/5 ${t.is_antitarget ? LEVEL_BG[t.antitarget_level || 'low'] : i % 2 ? 'bg-stone-500/5' : ''}`}>
              <td className="px-2 py-1.5 font-mono" style={{ color: t.is_antitarget ? LEVEL_COLOR[t.antitarget_level || 'low'] : '#0369a1', fontWeight: t.is_antitarget ? 700 : 400 }}>{t.gene_name}</td>
              <td className="px-2 py-1.5 text-stone-600 max-w-[220px]">{t.target_name.length > 38 ? t.target_name.slice(0, 36) + '…' : t.target_name}</td>
              <td className="px-2 py-1.5 text-stone-800 font-mono">{t.score.toFixed(2)}</td>
              <td className="px-2 py-1.5 text-stone-500">{t.shared_via}</td>
              <td className="px-2 py-1.5">{t.is_antitarget ? <span className="px-2 py-0.5 rounded-full text-[11px] font-bold" style={pill(t.antitarget_level || 'low')}>{t.antitarget_category}</span> : <span className="text-stone-300">—</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {items.length > 12 && <PencilButton onClick={() => setShowAll(s => !s)} className="mt-2">{showAll ? 'Mostrar menos' : `Ver ${items.length - 12} más`}</PencilButton>}
    </div>
  );
}

function ClusterTable({ peers }: { peers: ClusterPeer[] }) {
  if (!peers.length) return <p className="text-stone-500 text-[13px] font-hand">Sin fármacos estructuralmente similares (Jaccard ≥ 0.15).</p>;
  return (
    <table className="w-full border-collapse text-xs">
      <thead><tr className="border-b border-stone-800/10">{['Fármaco', 'ID', 'Jaccard', 'Comunes'].map(h => <th key={h} className={thc}>{h}</th>)}</tr></thead>
      <tbody>
        {peers.map((p, i) => (
          <tr key={i} className={`border-b border-stone-800/5 ${i % 2 ? 'bg-stone-500/5' : ''}`}>
            <td className="px-2 py-1.5 text-stone-800 font-medium">{p.name}</td>
            <td className="px-2 py-1.5 text-sky-700 font-mono">{p.drugbank_id}</td>
            <td className="px-2 py-1.5">
              <div className="flex items-center gap-2">
                <div className="w-16 bg-stone-300/50 rounded-full h-1.5"><div className="h-full rounded-full" style={{ width: `${Math.min(100, p.jaccard * 200)}%`, background: p.jaccard >= 0.4 ? '#15803d' : p.jaccard >= 0.25 ? '#b45309' : '#2563eb' }} /></div>
                <span className="text-xs text-stone-600 font-mono">{p.jaccard.toFixed(3)}</span>
              </div>
            </td>
            <td className="px-2 py-1.5 text-amber-700 font-semibold">{p.shared_count}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function downloadCsv(filename: string, headers: string[], rows: (string | number)[][]) {
  const esc = (v: string | number) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const blob = new Blob([[headers.map(esc).join(','), ...rows.map(r => r.map(esc).join(','))].join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url);
}
function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url);
}

function Badge({ count, label, color }: { count: number; label: string; color: string }) {
  return <div className="text-center min-w-[80px]"><div className="text-2xl font-bold font-hand" style={{ color }}>{count}</div><div className="text-[11px] text-stone-500">{label}</div></div>;
}

export default function ToxicityTool() {
  usePageTitle('Evaluación de Toxicidad');
  const [drugId, setDrugId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<ToxicityResult | null>(null);
  const [activeTab, setActiveTab] = useState<'alerts' | 'cyp' | 'predicted' | 'cluster'>('alerts');

  const handleSearch = async () => {
    const id = drugId.trim().toUpperCase();
    if (!id) { setError('Ingresa un DrugBank ID'); return; }
    setLoading(true); setError(''); setResult(null);
    try { const res = await toolsApi.toxicity(id); setResult(res.data); setActiveTab('alerts'); }
    catch (err: unknown) { setError((err as any)?.response?.data?.error || (err as any)?.message || 'Error al conectar con el servidor'); }
    finally { setLoading(false); }
  };

  const tabs = result ? [
    { key: 'alerts', label: `Alertas (${result.alerts.length})` },
    { key: 'cyp', label: `CYPs (${result.cyp_interactions.length})` },
    { key: 'predicted', label: `Off-targets (${result.predicted_offtargets.length})` },
    { key: 'cluster', label: `Cluster (${result.structural_cluster.length})` },
  ] : [];

  const ExpBtn = ({ onClick }: { onClick: () => void }) => <PencilButton onClick={onClick} icon={<Download className="w-4 h-4 text-amber-800" />}>CSV</PencilButton>;

  return (
    <div className="max-w-5xl">
      <HandTitle className="text-2xl flex items-center gap-2"><AlertTriangle className="w-6 h-6 text-amber-800" /> Toxicidad y Off-targets</HandTitle>
      <p className="text-stone-500 text-[13px] font-hand mt-1 mb-5">Perfil de riesgo: anti-targets conocidos (hERG, CYPs, dopamina), off-targets predichos y fármacos similares.</p>

      <div className={cardCls}>
        <div className="flex gap-3 items-end flex-wrap">
          <div>
            <label className="text-[11px] text-stone-500 block mb-1 font-mono">DRUGBANK ID</label>
            <input className="w-72 bg-[#faf6ee] border-2 border-[#3f3429] rounded-lg px-3 py-2 text-[13px] font-hand outline-none" value={drugId} onChange={e => setDrugId(e.target.value)} placeholder="DC1234" onKeyDown={e => e.key === 'Enter' && handleSearch()} />
          </div>
          <PencilButton variant="solid" onClick={handleSearch} disabled={loading}>{loading ? 'Analizando…' : 'Analizar toxicidad'}</PencilButton>
          {error && <span className="text-red-600 text-[13px]">{error}</span>}
        </div>
        <div className="mt-2.5 text-xs text-stone-500 font-hand">Ejemplos: DC1234 (Aspirina) · DB00563 (Metotrexato) · DB01050 (Ibuprofeno) · DB00734 (Risperidona)</div>
      </div>

      {result && (
        <>
          <div className={cardCls}>
            <div className="flex gap-5 items-start flex-wrap">
              <div>
                <div className="text-stone-500 text-[11px] mb-0.5 font-mono">FÁRMACO ANALIZADO</div>
                <div className="text-stone-900 text-xl font-bold">{result.drug.name}</div>
                <div className="text-sky-700 text-xs font-mono">{result.drug.drugbank_id}</div>
                <div className="text-stone-500 text-xs mt-1">{result.target_count} targets documentados</div>
              </div>
              <div className="w-px bg-stone-300 self-stretch" />
              <div className="flex-1 min-w-[260px]"><RiskMeter score={result.risk_score} level={result.risk_level} /></div>
              <div className="w-px bg-stone-300 self-stretch" />
              <div className="flex gap-5 items-center">
                <Badge count={result.alert_counts.high} label="Alto" color="#b91c1c" />
                <Badge count={result.alert_counts.medium} label="Medio" color="#b45309" />
                <Badge count={result.alert_counts.low} label="Bajo" color="#2563eb" />
              </div>
              <PencilButton onClick={() => downloadJson(`toxicity_${result.drug.drugbank_id}.json`, result)} icon={<Download className="w-4 h-4 text-amber-800" />} className="self-center">JSON</PencilButton>
            </div>
          </div>

          <div className="flex gap-1 border-b border-stone-800/10">
            {tabs.map(t => (
              <button key={t.key} onClick={() => setActiveTab(t.key as any)} className={`px-4 py-2 text-[13px] font-hand cursor-pointer border-b-2 ${activeTab === t.key ? 'border-red-600 text-red-700' : 'border-transparent text-stone-500'}`}>{t.label}</button>
            ))}
          </div>

          <div className={`${cardCls} rounded-t-none`}>
            {activeTab === 'alerts' && (
              result.alerts.length === 0 ? <div className="text-emerald-700 text-sm py-2 font-hand">Sin alertas de anti-targets conocidos.</div> : (
                <div>
                  <div className="flex justify-between items-center mb-3.5">
                    <div className="text-stone-500 text-xs font-hand">Clic en cada alerta para ver la explicación. Ordenadas por severidad.</div>
                    <ExpBtn onClick={() => downloadCsv(`alerts_${result.drug.drugbank_id}.csv`, ['level', 'category', 'gene_name', 'target_name', 'uniprot_id', 'rel_type', 'message'], result.alerts.map(a => [a.level, a.category, a.gene_name, a.target_name, a.uniprot_id || '', a.rel_type, a.message || '']))} />
                  </div>
                  {result.alerts.map((a, i) => <AlertCard key={i} alert={a} />)}
                </div>
              )
            )}
            {activeTab === 'cyp' && (
              <div>
                <div className="flex justify-between items-center mb-3">
                  <div className="text-stone-500 text-xs font-hand">Las interacciones con CYP450 determinan el metabolismo y el potencial de interacciones.</div>
                  {result.cyp_interactions.length > 0 && <ExpBtn onClick={() => downloadCsv(`cyp_${result.drug.drugbank_id}.csv`, ['gene', 'rel_type', 'level', 'note'], result.cyp_interactions.map(c => [c.gene, c.rel_type, c.level, c.note]))} />}
                </div>
                <CypTable cyps={result.cyp_interactions} />
              </div>
            )}
            {activeTab === 'predicted' && (
              <div>
                {result.predicted_offtargets.length > 0 && <div className="flex justify-end mb-2"><ExpBtn onClick={() => downloadCsv(`offtargets_${result.drug.drugbank_id}.csv`, ['target_name', 'gene_name', 'uniprot_id', 'score', 'shared_via', 'es_antitarget', 'nivel'], result.predicted_offtargets.map(t => [t.target_name, t.gene_name, t.uniprot_id || '', t.score.toFixed(4), t.shared_via, t.is_antitarget ? 'si' : 'no', t.antitarget_level || '']))} /></div>}
                <OfftargetsTable items={result.predicted_offtargets} />
              </div>
            )}
            {activeTab === 'cluster' && (
              <div>
                <div className="flex justify-between items-center mb-3">
                  <div className="text-stone-500 text-xs font-hand">Fármacos que comparten muchos targets (Jaccard ≥ 0.15); pueden tener toxicidad similar.</div>
                  {result.structural_cluster.length > 0 && <ExpBtn onClick={() => downloadCsv(`cluster_${result.drug.drugbank_id}.csv`, ['drugbank_id', 'name', 'jaccard', 'shared_count'], result.structural_cluster.map(p => [p.drugbank_id, p.name, p.jaccard.toFixed(4), p.shared_count]))} />}
                </div>
                <ClusterTable peers={result.structural_cluster} />
              </div>
            )}
          </div>

          <div className="mt-4">
            <ReportPanel kind="toxicity" payload={result} />
          </div>
        </>
      )}
    </div>
  );
}
