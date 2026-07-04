import React, { useState } from 'react';
import { Share2, Download } from 'lucide-react';
import { toolsApi, DtiGnnResult, DtiPrediction } from '../../api/tools';
import { usePageTitle } from '../../hooks/usePageTitle';
import { HandTitle, PencilButton } from '../../components/notebook';
import ReportPanel from '../reports/ReportPanel';

const cardCls = 'bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-5 mb-4 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]';
const inpCls = 'bg-[#faf6ee] border-2 border-[#3f3429] rounded-lg px-3 py-2 text-[13px] font-hand outline-none';

function ProbBar({ value }: { value: number }) {
  const col = value >= 0.66 ? '#15803d' : value >= 0.33 ? '#b45309' : '#2563eb';
  return (
    <div className="flex items-center gap-2">
      <div className="w-24 bg-stone-300/50 rounded-full h-2 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${value * 100}%`, background: col }} />
      </div>
      <span className="text-xs font-mono min-w-[44px]" style={{ color: col }}>{(value * 100).toFixed(1)}%</span>
    </div>
  );
}

export default function DtiGnnTool() {
  usePageTitle('Predicción DTI (GNN)');
  const [drugId, setDrugId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<DtiGnnResult | null>(null);

  const handleSearch = async () => {
    const id = drugId.trim().toUpperCase();
    if (!id) { setError('Ingresa un DrugBank ID'); return; }
    setLoading(true); setError(''); setResult(null);
    try { const res = await toolsApi.dtiGnn(id); setResult(res.data); }
    catch (err: any) {
      const data = err?.response?.data;
      setError(data?.error || err?.message || 'Error al conectar');
    } finally { setLoading(false); }
  };

  const preds: DtiPrediction[] = result?.predictions || [];
  const m = result?.model || {};

  const exportCsv = () => {
    if (!preds.length) return;
    const header = 'target_id,gene_name,target_name,uniprot_id,probability';
    const rows = preds.map(p => [p.target_id, p.gene_name, `"${p.target_name}"`, p.uniprot_id, p.probability].join(','));
    const blob = new Blob([[header, ...rows].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `dti_gnn_${drugId}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const thc = 'px-2 py-1.5 text-left text-stone-500 font-mono text-[11px]';

  return (
    <div className="max-w-5xl">
      <HandTitle className="text-2xl flex items-center gap-2"><Share2 className="w-6 h-6 text-amber-800" /> Predicción DTI (GNN)</HandTitle>
      <p className="text-stone-500 text-[13px] font-hand mt-1 mb-5">
        Dianas fármaco no documentadas predichas por una red neuronal de grafos (GraphSAGE/FastRP en Neo4j GDS) + cabezal de Link Prediction entrenado. Cada predicción trae probabilidad; el modelo reporta su AUCPR en test.
      </p>

      <div className={cardCls}>
        <div className="flex gap-3 items-end flex-wrap">
          <div>
            <label className="text-[11px] text-stone-500 block mb-1 font-mono">DRUGBANK ID</label>
            <input className={`${inpCls} w-72`} value={drugId} onChange={e => setDrugId(e.target.value)} placeholder="DC1234" onKeyDown={e => e.key === 'Enter' && handleSearch()} />
          </div>
          <PencilButton variant="solid" onClick={handleSearch} disabled={loading}>{loading ? 'Consultando…' : 'Predecir dianas'}</PencilButton>
          {error && <span className="text-red-600 text-[13px]">{error}</span>}
        </div>
      </div>

      {result?.available && (
        <>
          <div className={`${cardCls} flex gap-5 items-center flex-wrap`}>
            <div>
              <div className="text-stone-500 text-[11px] font-mono">FÁRMACO</div>
              <div className="text-stone-900 text-lg font-bold">{result.drug.name}</div>
              <div className="text-sky-700 text-xs font-mono">{result.drug.drugbank_id}</div>
            </div>
            <div className="w-px bg-stone-300 self-stretch" />
            <div className="text-center"><div className="text-2xl font-bold font-hand text-purple-700">{preds.length}</div><div className="text-stone-500 text-xs">Dianas predichas</div></div>
            {m.auc_pr !== undefined && (
              <div className="text-center px-3 py-1.5 rounded-lg bg-green-500/10 border-2 border-green-800/15">
                <div className="text-xl font-bold font-mono text-green-700">{m.auc_pr?.toFixed(3)}</div>
                <div className="text-stone-500 text-[10px]">AUCPR (test)</div>
              </div>
            )}
            <div className="text-[11px] text-stone-500 font-mono">
              embeddings: {m.embedding_method || '—'}<br />ROC-AUC: {m.roc_auc ?? '—'}
            </div>
            <div className="flex-1" />
            {preds.length > 0 && <PencilButton onClick={exportCsv} icon={<Download className="w-4 h-4 text-amber-800" />}>CSV</PencilButton>}
          </div>

          <div className={cardCls}>
            {preds.length === 0 ? (
              <div className="text-stone-500 text-[13px] font-hand">Sin predicciones para este fármaco (no aparece en las top-K escritas por el modelo).</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-xs">
                  <thead><tr className="border-b border-stone-800/10">{['#', 'Gen', 'Diana', 'UniProt', 'Probabilidad'].map((h, i) => <th key={i} className={thc}>{h}</th>)}</tr></thead>
                  <tbody>
                    {preds.map((p, i) => (
                      <tr key={i} className={`border-b border-stone-800/5 ${i % 2 ? 'bg-stone-500/5' : ''}`}>
                        <td className="px-2 py-1.5 text-stone-500">{i + 1}</td>
                        <td className="px-2 py-1.5 font-mono text-amber-700 font-semibold">{p.gene_name || '—'}</td>
                        <td className="px-2 py-1.5 text-stone-800">{p.target_name}</td>
                        <td className="px-2 py-1.5 font-mono text-sky-700">{p.uniprot_id || '—'}</td>
                        <td className="px-2 py-1.5"><ProbBar value={p.probability} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="text-stone-400 text-[11px] font-hand mb-4">
            Hipótesis de interacción in silico (no confirmadas). El AUCPR mide la calidad del modelo en un test held-out.
          </div>
          <div className="mt-2"><ReportPanel kind="dti_gnn" payload={result} /></div>
        </>
      )}
    </div>
  );
}
