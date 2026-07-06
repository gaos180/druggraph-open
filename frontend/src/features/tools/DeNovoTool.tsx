import React, { useState } from 'react';
import { FlaskConical, Download, AlertTriangle } from 'lucide-react';
import { toolsApi, DeNovoResult, DeNovoCandidate } from '../../api/tools';
import { usePageTitle } from '../../hooks/usePageTitle';
import { HandTitle, PencilButton } from '../../components/notebook';
import ReportPanel from '../reports/ReportPanel';

const cardCls = 'bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-5 mb-4 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]';
const inpCls = 'bg-[#faf6ee] border-2 border-[#3f3429] rounded-lg px-3 py-2 text-[13px] font-hand outline-none';

function ScoreBar({ value, max, color }: { value: number | null; max: number; color: string }) {
  if (value === null || value === undefined) return <span className="text-stone-400 text-xs">—</span>;
  return (
    <div className="flex items-center gap-2">
      <div className="w-14 bg-stone-300/50 rounded-full h-2 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${Math.min(100, (value / max) * 100)}%`, background: color }} />
      </div>
      <span className="text-xs font-mono min-w-[34px]" style={{ color }}>{value.toFixed(2)}</span>
    </div>
  );
}

export default function DeNovoTool() {
  usePageTitle('Diseño de novo');
  const [seed, setSeed] = useState('');
  const [mode, setMode] = useState<'grow' | 'mutate' | 'link'>('mutate');
  const [engine, setEngine] = useState<'crem' | 'synthemol' | 'reinvent' | 'pharma'>('crem');
  const [n, setN] = useState(20);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<DeNovoResult | null>(null);

  const handleGenerate = async () => {
    const s = seed.trim();
    if (!s) { setError('Ingresa un SMILES o DrugBank ID como semilla'); return; }
    setLoading(true); setError(''); setResult(null);
    try {
      const res = await toolsApi.denovo({ seed: s, mode, engine, n });
      setResult(res.data);
    } catch (err: any) {
      const data = err?.response?.data;
      setError(data?.reason || data?.error || err?.message || 'Error al generar');
    } finally { setLoading(false); }
  };

  const candidates: DeNovoCandidate[] = result?.candidates || [];

  const exportSmi = () => {
    if (!candidates.length) return;
    const rows = candidates.map((c, i) => `${c.smiles}\tcand_${i + 1}`);
    const blob = new Blob([rows.join('\n')], { type: 'chemical/x-daylight-smiles' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'denovo_candidates.smi'; a.click();
    URL.revokeObjectURL(url);
  };

  const thc = 'px-2 py-1.5 text-left text-stone-500 font-mono text-[11px]';

  return (
    <div className="max-w-5xl">
      <HandTitle className="text-2xl flex items-center gap-2"><FlaskConical className="w-6 h-6 text-amber-800" /> Diseño de Novo</HandTitle>
      <p className="text-stone-500 text-[13px] font-hand mt-1 mb-5">
        Genera moléculas nuevas y las filtra por propiedades drug-like (QED, sintetizabilidad, similitud). Motor por defecto <b>CReM</b> (Polishchuk 2020); opciones <b>SyntheMol</b> (Stanford, <i>Nat. Mach. Intell.</i> 2024 — síntesis garantizada), <b>REINVENT4</b> (AstraZeneca 2024) y <b>Pharmacóforo (GA)</b> (Tier 5.2 — GA SELFIES que optimiza el match al pharmacóforo de la semilla). SyntheMol y Pharmacóforo ignoran el modo.
      </p>

      <div className={cardCls}>
        <div className="flex gap-3 items-end flex-wrap">
          <div className="flex-1 min-w-[220px]">
            <label className="text-[11px] text-stone-500 block mb-1 font-mono">SEMILLA (SMILES o DrugBank ID)</label>
            <input className={`${inpCls} w-full`} value={seed} onChange={e => setSeed(e.target.value)}
              placeholder="CC(=O)Oc1ccccc1C(=O)O  ·  DC1234" onKeyDown={e => e.key === 'Enter' && handleGenerate()} />
          </div>
          <div>
            <label className="text-[11px] text-stone-500 block mb-1 font-mono">MODO</label>
            <select className={inpCls} value={mode} onChange={e => setMode(e.target.value as any)}>
              <option value="mutate">mutate</option>
              <option value="grow">grow</option>
              <option value="link">link</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] text-stone-500 block mb-1 font-mono">MOTOR</label>
            <select className={inpCls} value={engine} onChange={e => setEngine(e.target.value as any)}>
              <option value="crem">CReM</option>
              <option value="synthemol">SyntheMol</option>
              <option value="reinvent">REINVENT4</option>
              <option value="pharma">Pharmacóforo (GA)</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] text-stone-500 block mb-1 font-mono">N</label>
            <input className={`${inpCls} w-20`} type="number" min={1} max={100} value={n} onChange={e => setN(Number(e.target.value))} />
          </div>
          <PencilButton variant="solid" onClick={handleGenerate} disabled={loading}>{loading ? 'Generando…' : 'Generar'}</PencilButton>
        </div>
        {error && <div className="text-red-600 text-[13px] mt-2">{error}</div>}
      </div>

      {result?.available && (
        <>
          <div className={`${cardCls} flex gap-5 items-center flex-wrap`}>
            <div>
              <div className="text-stone-500 text-[11px] font-mono">MOTOR</div>
              <div className="text-stone-900 text-lg font-bold uppercase">{result.engine}</div>
            </div>
            <div className="w-px bg-stone-300 self-stretch" />
            <div className="text-center"><div className="text-2xl font-bold font-hand text-stone-800">{result.generated}</div><div className="text-stone-500 text-xs">Generadas</div></div>
            <div className="text-center"><div className="text-2xl font-bold font-hand text-purple-700">{candidates.length}</div><div className="text-stone-500 text-xs">Candidatas únicas</div></div>
            <div className="flex-1" />
            {candidates.length > 0 && <PencilButton onClick={exportSmi} icon={<Download className="w-4 h-4 text-amber-800" />}>.smi</PencilButton>}
          </div>

          <div className={cardCls}>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-xs">
                <thead><tr className="border-b border-stone-800/10">{['#', 'SMILES', 'QED', 'SA', 'Sim. seed', 'PM', 'Lipinski'].map((h, i) => <th key={i} className={thc}>{h}</th>)}</tr></thead>
                <tbody>
                  {candidates.map((c, i) => (
                    <tr key={i} className={`border-b border-stone-800/5 ${i % 2 ? 'bg-stone-500/5' : ''}`}>
                      <td className="px-2 py-1.5 text-stone-500">{i + 1}</td>
                      <td className="px-2 py-1.5 font-mono text-[11px] text-stone-800 break-all max-w-[280px]">{c.smiles}</td>
                      <td className="px-2 py-1.5"><ScoreBar value={c.qed} max={1} color="#15803d" /></td>
                      <td className="px-2 py-1.5"><ScoreBar value={c.sa_score} max={10} color="#b45309" /></td>
                      <td className="px-2 py-1.5 font-mono text-stone-600">{c.similarity_to_seed !== null ? c.similarity_to_seed.toFixed(3) : '—'}</td>
                      <td className="px-2 py-1.5 font-mono text-stone-600">{c.mol_weight}</td>
                      <td className="px-2 py-1.5"><span className={`font-mono font-semibold ${c.lipinski_rules >= 4 ? 'text-green-700' : c.lipinski_rules >= 3 ? 'text-amber-700' : 'text-red-600'}`}>{c.lipinski_rules}/4</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className={`${cardCls} bg-amber-50/60 flex gap-2 items-start`}>
            <AlertTriangle className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
            <div className="text-[12px] text-stone-600 font-hand">
              <b>{result.disclaimer}</b>
              {result.paper && <div className="text-[11px] text-stone-500 mt-1">Motor: {result.paper}</div>}
            </div>
          </div>

          <div className="mt-4"><ReportPanel kind="denovo" payload={result} /></div>
        </>
      )}
    </div>
  );
}
