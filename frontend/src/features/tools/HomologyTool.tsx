import React, { useEffect, useState } from 'react';
import { PawPrint } from 'lucide-react';
import { toolsApi, HomologyResult, HomologySpecies } from '../../api/tools';
import { usePageTitle } from '../../hooks/usePageTitle';
import { HandTitle, PencilButton } from '../../components/notebook';

const cardCls = 'bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-5 mb-4 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]';
const inpCls = 'bg-[#faf6ee] border-2 border-[#3f3429] rounded-lg px-3 py-2 text-[13px] font-hand outline-none';

function idColor(v: number | null): string {
  if (v === null) return '#9ca3af';
  return v >= 70 ? '#15803d' : v >= 40 ? '#b45309' : '#dc2626';
}
const DEFAULT_SP = [9615, 9685, 10090, 9913]; // perro, gato, ratón, vaca

export default function HomologyTool() {
  usePageTitle('Homología cross-especies');
  const [drugId, setDrugId] = useState('');
  const [species, setSpecies] = useState<HomologySpecies[]>([]);
  const [selected, setSelected] = useState<number[]>(DEFAULT_SP);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [r, setR] = useState<HomologyResult | null>(null);

  useEffect(() => { toolsApi.homologySpecies().then(res => setSpecies(res.data.species || [])).catch(() => {}); }, []);

  const toggle = (id: number) => setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id]);

  const run = async () => {
    const id = drugId.trim().toUpperCase();
    if (!id) { setError('Ingresa un DrugBank ID'); return; }
    if (selected.length === 0) { setError('Elige al menos una especie'); return; }
    setLoading(true); setError(''); setR(null);
    try { const res = await toolsApi.homology({ drug_id: id, species: selected }); setR(res.data); }
    catch (e: any) { setError(e?.response?.data?.reason || e?.response?.data?.error || 'Error'); }
    finally { setLoading(false); }
  };

  const cols = r?.species || [];
  const th = 'px-2 py-1.5 text-left text-stone-500 font-mono text-[11px]';

  return (
    <div className="max-w-5xl">
      <HandTitle className="text-2xl flex items-center gap-2"><PawPrint className="w-6 h-6 text-amber-800" /> Homología cross-especies</HandTitle>
      <p className="text-stone-500 text-[13px] font-hand mt-1 mb-4">
        ¿El fármaco podría funcionar en <b>otras especies</b> (uso veterinario)? Busca los ortólogos de sus dianas en las especies que elijas y mide la <b>% de identidad</b> — alta conservación (≥70%) sugiere que la diana, y por tanto el fármaco, se conserva.
      </p>

      <div className={cardCls}>
        <div className="flex gap-3 items-end flex-wrap mb-3">
          <div>
            <label className="text-[11px] text-stone-500 block mb-1 font-mono">DRUGBANK ID</label>
            <input className={`${inpCls} w-56`} value={drugId} onChange={e => setDrugId(e.target.value)} placeholder="DC4" onKeyDown={e => e.key === 'Enter' && run()} />
          </div>
          <PencilButton variant="solid" onClick={run} disabled={loading}>{loading ? 'Comparando…' : 'Analizar'}</PencilButton>
        </div>
        <div className="text-[11px] text-stone-500 font-mono mb-1">ESPECIES A ELECCIÓN</div>
        <div className="flex flex-wrap gap-2">
          {species.map(s => (
            <label key={s.organism_id} className={`px-2 py-0.5 rounded-full text-[12px] font-hand cursor-pointer border ${selected.includes(s.organism_id) ? 'bg-[#2d2621] text-[#faf6ee] border-[#1e1814]' : 'bg-transparent text-stone-600 border-stone-400'}`}>
              <input type="checkbox" className="hidden" checked={selected.includes(s.organism_id)} onChange={() => toggle(s.organism_id)} /> {s.name}
            </label>
          ))}
        </div>
        {error && <div className="text-red-600 text-[13px] mt-2">{error}</div>}
      </div>

      {r?.available && (
        <>
          <div className={cardCls}>
            <div className="text-stone-600 text-[12px] font-mono mb-2 uppercase">Veredicto por especie — ¿funcionaría?</div>
            <div className="flex flex-wrap gap-2">
              {(r.summary || []).map(s => (
                <div key={s.organism_id} className="px-3 py-1.5 rounded-lg border-2" style={{ borderColor: `${idColor(s.mean_identity)}40`, background: `${idColor(s.mean_identity)}12` }}>
                  <div className="text-[13px] font-bold text-stone-800">{s.name} {s.likely_works ? '✓' : ''}</div>
                  <div className="text-[11px] font-mono" style={{ color: idColor(s.mean_identity) }}>{s.mean_identity ?? '—'}% media · {s.n_conserved}/{s.n_targets} conservadas</div>
                </div>
              ))}
            </div>
          </div>

          <div className={cardCls}>
            <div className="text-stone-600 text-[12px] font-mono mb-2 uppercase">Identidad por diana y especie (%)</div>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-xs">
                <thead><tr className="border-b border-stone-800/10"><th className={th}>Diana</th><th className={th}>Humano</th>{cols.map(c => <th key={c.organism_id} className={th}>{c.name}</th>)}</tr></thead>
                <tbody>
                  {(r.targets || []).map((t, i) => (
                    <tr key={i} className={`border-b border-stone-800/5 ${i % 2 ? 'bg-stone-500/5' : ''}`}>
                      <td className="px-2 py-1.5 font-mono text-amber-700 font-semibold">{t.gene}</td>
                      <td className="px-2 py-1.5 font-mono text-sky-700">{t.human_uniprot || '—'}</td>
                      {cols.map(c => { const cell = t.by_species[String(c.organism_id)]; return (
                        <td key={c.organism_id} className="px-2 py-1.5 font-mono font-semibold" style={{ color: idColor(cell?.identity ?? null) }}>{cell?.identity != null ? `${cell.identity}` : '—'}</td>
                      ); })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="text-stone-400 text-[11px] font-hand mb-4">{r.note}</div>
        </>
      )}
    </div>
  );
}
