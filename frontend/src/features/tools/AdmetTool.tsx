import React, { useState } from 'react';
import { Beaker } from 'lucide-react';
import { toolsApi, AdmetResult, AdmetPrediction } from '../../api/tools';
import { usePageTitle } from '../../hooks/usePageTitle';
import { HandTitle, PencilButton } from '../../components/notebook';
import ReportPanel from '../reports/ReportPanel';

const cardCls = 'bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-5 mb-4 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]';
const inpCls = 'bg-[#faf6ee] border-2 border-[#3f3429] rounded-lg px-3 py-2 text-[13px] font-hand outline-none';

function PredictionCard({ p }: { p: AdmetPrediction }) {
  const isClf = p.task === 'classification';
  const proba = p.proba ?? 0;
  const col = isClf ? (proba >= 0.66 ? '#dc2626' : proba >= 0.33 ? '#b45309' : '#15803d') : '#2563eb';
  return (
    <div className={cardCls}>
      <div className="text-stone-800 font-bold font-hand text-[15px] mb-1">{p.label}</div>
      {isClf ? (
        <>
          <div className="flex items-center gap-2 mb-1">
            <div className="flex-1 bg-stone-300/50 rounded-full h-2.5 overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${proba * 100}%`, background: col }} />
            </div>
            <span className="font-mono font-semibold text-sm" style={{ color: col }}>{(proba * 100).toFixed(1)}%</span>
          </div>
          <div className="text-stone-500 text-[11px] font-hand">Probabilidad de: {p.positive_meaning || 'clase positiva'}</div>
        </>
      ) : (
        <div className="text-2xl font-bold font-mono" style={{ color: col }}>{p.value?.toFixed(3)} <span className="text-xs text-stone-500 font-hand">{p.unit}</span></div>
      )}
      <div className="text-stone-400 text-[10px] font-mono mt-2">
        {isClf ? `ROC-AUC modelo: ${p.model_auc ?? '—'}` : `RMSE modelo: ${p.model_rmse ?? '—'}`} · n_train {p.n_train ?? '—'}
      </div>
    </div>
  );
}

export default function AdmetTool() {
  usePageTitle('Predicción ADMET');
  const [smiles, setSmiles] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<AdmetResult | null>(null);

  const handlePredict = async () => {
    const s = smiles.trim();
    if (!s) { setError('Ingresa un SMILES o DrugBank ID'); return; }
    setLoading(true); setError(''); setResult(null);
    try {
      const body = s.toUpperCase().startsWith('DB') && /^\D{2}\d+$/.test(s.toUpperCase()) ? { drug_id: s } : { smiles: s };
      const res = await toolsApi.admet(body);
      setResult(res.data);
    } catch (err: any) {
      const data = err?.response?.data;
      setError(data?.reason || data?.error || err?.message || 'Error al predecir');
    } finally { setLoading(false); }
  };

  const preds = result?.predictions || [];

  return (
    <div className="max-w-5xl">
      <HandTitle className="text-2xl flex items-center gap-2"><Beaker className="w-6 h-6 text-amber-800" /> Predicción ADMET</HandTitle>
      <p className="text-stone-500 text-[13px] font-hand mt-1 mb-5">
        Modelos supervisados propios (RandomForest sobre descriptores RDKit + Morgan) entrenados en MoleculeNet (Tox21, BBBP, ESOL). Cada predicción muestra el ROC-AUC/RMSE del modelo.
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
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-0 sm:gap-4">
            {preds.map(p => <PredictionCard key={p.endpoint} p={p} />)}
          </div>
          <div className="text-stone-400 text-[11px] font-hand mb-4">
            Predicciones in silico exploratorias, no medidas experimentalmente.
          </div>
          <div className="mt-2"><ReportPanel kind="admet" payload={result} /></div>
        </>
      )}
    </div>
  );
}
