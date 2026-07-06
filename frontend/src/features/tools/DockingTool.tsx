import React, { useEffect, useState } from 'react';
import { Target } from 'lucide-react';
import { toolsApi, DockingResult, DockingTarget, DockingScreenHit } from '../../api/tools';
import { usePageTitle } from '../../hooks/usePageTitle';
import { HandTitle, PencilButton } from '../../components/notebook';

const cardCls = 'bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-5 mb-4 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]';
const inpCls = 'bg-[#faf6ee] border-2 border-[#3f3429] rounded-lg px-3 py-2 text-[13px] font-hand outline-none';

// Afinidad Vina: más negativo = mejor. Verde ≤ −8, ámbar −6..−8, gris > −6.
function affColor(a: number): string {
  return a <= -8 ? '#15803d' : a <= -6 ? '#b45309' : '#6b7280';
}

export default function DockingTool() {
  usePageTitle('Docking (AutoDock Vina)');
  const [ligand, setLigand] = useState('');
  const [target, setTarget] = useState('');
  const [targets, setTargets] = useState<DockingTarget[]>([]);
  const [unavailable, setUnavailable] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<DockingResult | null>(null);
  const [hits, setHits] = useState<DockingScreenHit[]>([]);

  useEffect(() => {
    toolsApi.dockingTargets()
      .then(res => { setTargets(res.data.targets || []); if (res.data.targets?.[0]) setTarget(res.data.targets[0].target); })
      .catch(err => setUnavailable(err?.response?.data?.error || 'Docking no disponible.'));
  }, []);

  useEffect(() => {
    if (!target) { setHits([]); return; }
    toolsApi.dockingScreen(target, 15).then(res => setHits(res.data.results || [])).catch(() => setHits([]));
  }, [target]);

  const run = async () => {
    const s = ligand.trim();
    if (!s) { setError('Ingresa un SMILES o DrugBank ID'); return; }
    if (!target) { setError('Selecciona un receptor'); return; }
    setLoading(true); setError(''); setResult(null);
    try {
      const body: any = /^D[CB]\d+$/i.test(s) ? { drug_id: s, target } : { smiles: s, target };
      const res = await toolsApi.docking(body);
      setResult(res.data);
    } catch (err: any) {
      const data = err?.response?.data;
      setError(data?.reason || data?.error || err?.message || 'Error al acoplar');
    } finally { setLoading(false); }
  };

  return (
    <div className="max-w-4xl">
      <HandTitle className="text-2xl flex items-center gap-2"><Target className="w-6 h-6 text-amber-800" /> Docking (AutoDock Vina)</HandTitle>
      <p className="text-stone-500 text-[13px] font-hand mt-1 mb-5">
        Cribado <b>estructural</b>: acopla un ligando al sitio activo 3D de una diana preparada y estima la afinidad de unión (kcal/mol, más negativo = mejor). Ligando por Meeko, receptor por OpenBabel, docking por AutoDock Vina. Cierra el pipeline Tier 5.
      </p>

      {unavailable ? (
        <div className={cardCls}><div className="text-amber-800 text-[13px] font-hand">{unavailable} Instala <code>vina + meeko + openbabel</code> y prepara un receptor con <code>scripts/prepare_receptor.py</code>.</div></div>
      ) : (
        <div className={cardCls}>
          <div className="flex gap-3 items-end flex-wrap">
            <div className="flex-1 min-w-[220px]">
              <label className="text-[11px] text-stone-500 block mb-1 font-mono">LIGANDO — SMILES o DrugBank ID</label>
              <input className={`${inpCls} w-full`} value={ligand} onChange={e => setLigand(e.target.value)}
                placeholder="CC(=O)Oc1ccccc1C(=O)O  ·  DC1234" onKeyDown={e => e.key === 'Enter' && run()} />
            </div>
            <div>
              <label className="text-[11px] text-stone-500 block mb-1 font-mono">RECEPTOR</label>
              <select className={inpCls} value={target} onChange={e => setTarget(e.target.value)}>
                {targets.map(t => <option key={t.target} value={t.target}>{t.name}{t.pdb_id ? ` (${t.pdb_id})` : ''}</option>)}
              </select>
            </div>
            <PencilButton variant="solid" onClick={run} disabled={loading}>{loading ? 'Acoplando…' : 'Acoplar'}</PencilButton>
          </div>
          {error && <div className="text-red-600 text-[13px] mt-2">{error}</div>}
        </div>
      )}

      {result?.available && (
        <>
          <div className={`${cardCls} flex gap-6 items-center flex-wrap`}>
            <div>
              <div className="text-stone-500 text-[11px] font-mono">DIANA</div>
              <div className="text-stone-900 text-lg font-bold">{result.target_name}</div>
              <div className="text-sky-700 text-xs font-mono">{result.pdb_id}</div>
            </div>
            <div className="w-px bg-stone-300 self-stretch" />
            <div className="text-center">
              <div className="text-3xl font-bold font-mono" style={{ color: affColor(result.affinity_kcal_mol ?? 0) }}>
                {result.affinity_kcal_mol?.toFixed(2)}
              </div>
              <div className="text-stone-500 text-[11px]">afinidad (kcal/mol)</div>
            </div>
            <div>
              <div className="text-stone-500 text-[11px] font-mono mb-1">POSES</div>
              <div className="flex gap-1">
                {(result.poses_kcal_mol || []).map((p, i) => (
                  <span key={i} className="px-1.5 py-0.5 rounded text-[11px] font-mono bg-stone-500/10" style={{ color: affColor(p) }}>{p.toFixed(1)}</span>
                ))}
              </div>
            </div>
          </div>
          <div className="text-stone-400 text-[11px] font-hand mb-4">{result.note}</div>
        </>
      )}

      {hits.length > 0 && (
        <div className={cardCls}>
          <div className="text-stone-600 text-[12px] font-mono mb-2">CRIBADO BATCH — top hits del catálogo (repurposing)</div>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-xs">
              <thead><tr className="border-b border-stone-800/10">{['#', 'Fármaco', 'ID', 'Afinidad (kcal/mol)'].map((h, i) => <th key={i} className="px-2 py-1.5 text-left text-stone-500 font-mono text-[11px]">{h}</th>)}</tr></thead>
              <tbody>
                {hits.map((h, i) => (
                  <tr key={i} className={`border-b border-stone-800/5 ${i % 2 ? 'bg-stone-500/5' : ''}`}>
                    <td className="px-2 py-1.5 text-stone-500">{i + 1}</td>
                    <td className="px-2 py-1.5 text-stone-800">{h.name || '—'}</td>
                    <td className="px-2 py-1.5 font-mono text-sky-700">{h.drug_id}</td>
                    <td className="px-2 py-1.5 font-mono" style={{ color: affColor(h.affinity_kcal_mol) }}>{h.affinity_kcal_mol.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="text-stone-400 text-[10px] font-hand mt-1">Resultados precomputados con scripts/run_docking_screen.py.</div>
        </div>
      )}
    </div>
  );
}
