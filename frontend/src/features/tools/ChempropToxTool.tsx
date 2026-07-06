import React, { useState } from 'react';
import { Biohazard, Download } from 'lucide-react';
import { toolsApi, ChempropToxResult, ChempropToxPrediction } from '../../api/tools';
import { usePageTitle } from '../../hooks/usePageTitle';
import { HandTitle, PencilButton } from '../../components/notebook';

const cardCls = 'bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-5 mb-4 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]';
const inpCls = 'bg-[#faf6ee] border-2 border-[#3f3429] rounded-lg px-3 py-2 text-[13px] font-hand outline-none';

function ToxRow({ p }: { p: ChempropToxPrediction }) {
  const v = p.probability ?? 0;
  const col = v >= 0.66 ? '#dc2626' : v >= 0.33 ? '#b45309' : '#15803d';
  return (
    <div className="flex items-center gap-3 py-1.5 border-b border-stone-800/5">
      <div className="flex-1 min-w-0">
        <div className="text-stone-800 text-[13px] font-hand truncate">{p.label}</div>
        <div className="text-stone-400 text-[10px] font-mono">{p.assay}</div>
      </div>
      <div className="w-32 bg-stone-300/50 rounded-full h-2 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${v * 100}%`, background: col }} />
      </div>
      <span className="font-mono text-xs min-w-[46px] text-right" style={{ color: col }}>
        {p.probability === null ? '—' : `${(v * 100).toFixed(1)}%`}
      </span>
    </div>
  );
}

export default function ChempropToxTool() {
  usePageTitle('Toxicidad GNN (Chemprop)');
  const [smiles, setSmiles] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<ChempropToxResult | null>(null);

  const handlePredict = async () => {
    const s = smiles.trim();
    if (!s) { setError('Ingresa un SMILES o DrugBank ID'); return; }
    setLoading(true); setError(''); setResult(null);
    try {
      const body = /^D[CB]\d+$/i.test(s) ? { drug_id: s } : { smiles: s };
      const res = await toolsApi.chempropTox(body);
      setResult(res.data);
    } catch (err: any) {
      const data = err?.response?.data;
      setError(data?.reason || data?.error || err?.message || 'Error al predecir');
    } finally { setLoading(false); }
  };

  const preds: ChempropToxPrediction[] = result?.predictions || [];

  const exportCsv = () => {
    if (!preds.length) return;
    const rows = preds.map(p => `${p.assay},"${p.label}",${p.probability ?? ''}`);
    const blob = new Blob([['assay,label,probability', ...rows].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'chemprop_tox.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-4xl">
      <HandTitle className="text-2xl flex items-center gap-2"><Biohazard className="w-6 h-6 text-amber-800" /> Toxicidad GNN (Chemprop)</HandTitle>
      <p className="text-stone-500 text-[13px] font-hand mt-1 mb-5">
        GNN de paso de mensajes (D-MPNN, Chemprop) que <b>aprende</b> la representación molecular del grafo — a diferencia del ADMET por RandomForest sobre fingerprints fijos. Un solo modelo multi-tarea predice los 12 ensayos de toxicidad de Tox21.
      </p>

      <div className={cardCls}>
        <div className="flex gap-3 items-end flex-wrap">
          <div className="flex-1 min-w-[240px]">
            <label className="text-[11px] text-stone-500 block mb-1 font-mono">SMILES o DrugBank ID</label>
            <input className={`${inpCls} w-full`} value={smiles} onChange={e => setSmiles(e.target.value)}
              placeholder="CC(=O)Oc1ccccc1C(=O)O  ·  DC1234" onKeyDown={e => e.key === 'Enter' && handlePredict()} />
          </div>
          <PencilButton variant="solid" onClick={handlePredict} disabled={loading}>{loading ? 'Prediciendo…' : 'Predecir'}</PencilButton>
        </div>
        {error && <div className="text-red-600 text-[13px] mt-2">{error}</div>}
      </div>

      {result?.available && (
        <>
          <div className={cardCls}>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-amber-800/10 text-amber-800">{result.engine}</span>
              <div className="flex-1" />
              {preds.length > 0 && <PencilButton onClick={exportCsv} icon={<Download className="w-4 h-4 text-amber-800" />}>CSV</PencilButton>}
            </div>
            {preds.map(p => <ToxRow key={p.assay} p={p} />)}
          </div>
          {result.paper && <div className="text-stone-400 text-[10px] font-mono mb-2">{result.paper}</div>}
          <div className="text-stone-400 text-[11px] font-hand mb-4">
            {result.disclaimer || 'Predicción in silico; no sustituye ensayos de toxicidad experimentales.'}
          </div>
        </>
      )}
    </div>
  );
}
