import React, { useState } from 'react';
import { Microscope, Target as TargetIcon, Biohazard } from 'lucide-react';
import { toolsApi, MoleculeAnalysisResult, ChempropToxResult, DockingResult, DockingTarget, MolTarget, DockingFunnelResult } from '../../api/tools';
import { usePageTitle } from '../../hooks/usePageTitle';
import { HandTitle, PencilButton } from '../../components/notebook';

const cardCls = 'bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-4 mb-4 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]';
const inpCls = 'bg-[#faf6ee] border-2 border-[#3f3429] rounded-lg px-3 py-2 text-[13px] font-hand outline-none';
const H = ({ children }: any) => <div className="text-stone-600 text-[12px] font-mono mb-2 uppercase tracking-wide">{children}</div>;
const ROLE_COLOR: Record<string, string> = { hbond: '#2563eb', hydrophobic: '#b45309', aromatic: '#7c3aed', ionic: '#dc2626', metal: '#0891b2', other: '#6b7280' };
function affColor(a: number) { return a <= -8 ? '#15803d' : a <= -6 ? '#b45309' : '#6b7280'; }
function probColor(v: number) { return v >= 0.66 ? '#dc2626' : v >= 0.33 ? '#b45309' : '#15803d'; }
const PH_PRESETS = [2.0, 5.0, 7.4, 8.0];

type DockChoice = { kind: 'prepared'; target: string; name: string } | { kind: 'uniprot'; uniprot: string; name: string };

export default function MoleculeLabTool() {
  usePageTitle('Laboratorio molecular');
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [r, setR] = useState<MoleculeAnalysisResult | null>(null);

  const [showTox, setShowTox] = useState(false);
  const [tox, setTox] = useState<ChempropToxResult | null>(null);

  const [showDock, setShowDock] = useState(false);
  const [preparedTargets, setPreparedTargets] = useState<DockingTarget[]>([]);
  const [choice, setChoice] = useState<DockChoice | null>(null);
  const [ph, setPh] = useState(7.4);
  const [dock, setDock] = useState<DockingResult | null>(null);
  const [dockLoading, setDockLoading] = useState(false);
  const [funnel, setFunnel] = useState<DockingFunnelResult | null>(null);
  const [funnelLoading, setFunnelLoading] = useState(false);

  const analyze = async () => {
    const s = q.trim();
    if (!s) { setError('Ingresa un SMILES o DrugBank ID'); return; }
    setLoading(true); setError(''); setR(null); setTox(null); setDock(null); setShowTox(false); setShowDock(false); setChoice(null);
    try {
      const b = /^D[CB]\d+$/i.test(s) ? { drug_id: s } : { smiles: s };
      const res = await toolsApi.moleculeAnalysis(b);
      setR(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.reason || err?.response?.data?.error || 'Error al analizar');
    } finally { setLoading(false); }
  };

  const molBody = () => (r?.drug_id ? { drug_id: r.drug_id } : { smiles: r?.smiles });

  const toggleTox = async () => {
    const on = !showTox; setShowTox(on);
    if (on && !tox) { try { const res = await toolsApi.chempropTox(molBody() as any); setTox(res.data); } catch (e: any) { setTox({ available: false, reason: e?.response?.data?.error } as any); } }
  };

  const openDock = async () => {
    setShowDock(true);
    if (preparedTargets.length === 0) {
      try { const res = await toolsApi.dockingTargets(); setPreparedTargets(res.data.targets || []); } catch { /* */ }
    }
  };

  const choiceBody = (c: DockChoice, atPh: number) => {
    const base: any = molBody();
    return c.kind === 'prepared' ? { ...base, target: c.target, ph: atPh } : { ...base, uniprot: c.uniprot, target_name: c.name, ph: atPh };
  };

  const runDock = async (c: DockChoice, atPh = ph) => {
    setChoice(c); setShowDock(true); setDockLoading(true); setDock(null); setFunnel(null);
    try { const res = await toolsApi.docking(choiceBody(c, atPh)); setDock(res.data); }
    catch (e: any) { setDock({ available: false, reason: e?.response?.data?.error } as any); }
    finally { setDockLoading(false); }
  };

  const runFunnel = async () => {
    if (!choice) return;
    setFunnelLoading(true); setFunnel(null);
    try { const res = await toolsApi.dockingFunnel(choiceBody(choice, ph)); setFunnel(res.data); }
    catch (e: any) { setFunnel({ available: false, reason: e?.response?.data?.error } as any); }
    finally { setFunnelLoading(false); }
  };

  // Botón de docking para una fila de diana (si tiene UniProt).
  const DockBtn = ({ t }: { t: MolTarget }) => {
    const up = t.uniprot || t.uniprot_id;
    const name = t.gene || t.gene_name || up || '';
    if (!up) return null;
    return <button className="ml-1 text-[10px] px-1.5 py-0.5 rounded bg-emerald-600/10 text-emerald-800 border border-emerald-800/20 hover:bg-emerald-600/20" onClick={() => runDock({ kind: 'uniprot', uniprot: up, name })}>dock</button>;
  };

  const p = r?.properties; const net = r?.network;
  const admetPreds = (r?.admet && (r.admet as any).predictions) || [];
  const phCounts = r?.pharmacophore?.feature_counts || {};
  const consensus = net?.mode === 'consensus-3-neighbors';

  return (
    <div className="max-w-5xl">
      <HandTitle className="text-2xl flex items-center gap-2"><Microscope className="w-6 h-6 text-amber-800" /> Laboratorio molecular</HandTitle>
      <p className="text-stone-500 text-[13px] font-hand mt-1 mb-4">
        Panel integral: analiza una molécula con todas las herramientas — propiedades, a quién se parece, pharmacóforo, ADMET, dianas y repurposing. Si no está en el catálogo, las dianas salen del <b>consenso de sus 3 vecinos</b> (las compartidas son las más probables). <b>Toxicidad</b> y <b>docking</b> son extras.
      </p>

      <div className={cardCls}>
        <div className="flex gap-3 items-end flex-wrap">
          <div className="flex-1 min-w-[260px]">
            <label className="text-[11px] text-stone-500 block mb-1 font-mono">SMILES o DrugBank ID</label>
            <input className={`${inpCls} w-full`} value={q} onChange={e => setQ(e.target.value)} placeholder="CC(=O)Oc1ccccc1C(=O)O  ·  DC4" onKeyDown={e => e.key === 'Enter' && analyze()} />
          </div>
          <PencilButton variant="solid" onClick={analyze} disabled={loading}>{loading ? 'Analizando…' : 'Analizar'}</PencilButton>
        </div>
        {error && <div className="text-red-600 text-[13px] mt-2">{error}</div>}
      </div>

      {r?.available && (<>
        {p?.available && (
          <div className={cardCls}>
            <H>Identidad y propiedades {r.drug_id && <span className="text-sky-700">· {r.drug_id}</span>}</H>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
              {[['Fórmula', p.formula], ['MW', p.mw], ['logP', p.logp], ['TPSA', p.tpsa], ['QED', p.qed], ['SA', p.sa_score], ['Rot. bonds', p.rot_bonds], ['Lipinski', `${p.lipinski_ok}/4`]].map(([k, v]: any) => (
                <div key={k} className="bg-stone-500/5 rounded-lg py-1.5"><div className="text-stone-800 font-mono text-sm font-bold">{v}</div><div className="text-stone-500 text-[10px]">{k}</div></div>
              ))}
            </div>
            {r.chemical_space?.available && <div className="text-stone-400 text-[11px] font-mono mt-2">Espacio químico: cluster {r.chemical_space.cluster}</div>}
          </div>
        )}

        {r.neighbors && r.neighbors.length > 0 && (
          <div className={cardCls}>
            <H>A quién se parece</H>
            <div className="flex flex-wrap gap-1.5">{r.neighbors.map((n, i) => <span key={i} className="px-2 py-0.5 rounded-full text-[11px] font-mono bg-sky-500/10 text-sky-800 border border-sky-800/20">{n.name || n.drug_id} · {(n.similarity * 100).toFixed(0)}%</span>)}</div>
          </div>
        )}

        {Object.keys(phCounts).length > 0 && (
          <div className={cardCls}>
            <H>Pharmacóforo</H>
            <div className="flex flex-wrap gap-1.5">{Object.entries(phCounts).map(([fam, cnt]: any) => { const role = r.pharmacophore?.features?.find(f => f.family === fam)?.role || 'other'; const col = ROLE_COLOR[role]; return <span key={fam} className="px-2 py-0.5 rounded-full text-[11px] font-mono" style={{ background: `${col}18`, color: col, border: `1px solid ${col}40` }}>{fam} ×{cnt}</span>; })}</div>
          </div>
        )}

        {admetPreds.length > 0 && (
          <div className={cardCls}>
            <H>ADMET</H>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">{admetPreds.map((a: any) => <div key={a.endpoint} className="flex items-center gap-2 text-[13px]"><span className="flex-1 text-stone-700 font-hand truncate">{a.label}</span>{a.task === 'classification' ? <span className="font-mono" style={{ color: probColor(a.proba || 0) }}>{((a.proba || 0) * 100).toFixed(0)}%</span> : <span className="font-mono text-sky-700">{a.value?.toFixed(2)} {a.unit}</span>}</div>)}</div>
          </div>
        )}

        {net && (
          <div className={cardCls}>
            <H>Dianas y repurposing {consensus && <span className="text-stone-400 normal-case">· consenso de {net.n_neighbors} vecinos: {(net.neighbors_used || []).map(n => n.name).join(', ')}</span>}</H>
            {consensus ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-[12px]">
                <div>
                  <div className="text-stone-500 font-mono text-[11px] mb-1">Dianas compartidas (× = nº de vecinos) — las más probables</div>
                  {(net.consensus_targets || []).map((t, i) => (
                    <div key={i} className="flex items-center gap-1 py-0.5">
                      <span className={`text-[10px] px-1 rounded ${(t.shared || 0) >= 3 ? 'bg-emerald-600/15 text-emerald-800' : (t.shared || 0) === 2 ? 'bg-amber-600/15 text-amber-800' : 'bg-stone-500/10 text-stone-500'}`}>×{t.shared}</span>
                      <span className="text-purple-700 font-mono">{t.gene}</span>
                      <span className="text-stone-600 truncate flex-1">{t.name}</span>
                      <DockBtn t={t} />
                    </div>
                  ))}
                </div>
                <div>
                  <div className="text-stone-500 font-mono text-[11px] mb-1">Enfermedades compartidas (repurposing)</div>
                  {(net.consensus_diseases || []).map((d, i) => <div key={i} className="py-0.5"><span className={`text-[10px] px-1 rounded mr-1 ${(d.shared || 0) >= 3 ? 'bg-emerald-600/15 text-emerald-800' : 'bg-amber-600/15 text-amber-800'}`}>×{d.shared}</span>{d.disease_name}</div>)}
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-[12px]">
                <div><div className="text-stone-500 font-mono text-[11px] mb-1">Documentadas</div>{(net.documented_targets || []).slice(0, 6).map((t, i) => <div key={i} className="text-stone-700"><span className="text-amber-700 font-mono">{t.gene || '—'}</span> {t.name} <DockBtn t={t} /></div>)}</div>
                <div><div className="text-stone-500 font-mono text-[11px] mb-1">Predichas (DTI-GNN)</div>{(net.predicted_targets || []).slice(0, 6).map((t, i) => <div key={i} className="text-stone-700"><span className="text-purple-700 font-mono">{t.gene_name || '—'}</span> {((t.probability || 0) * 100).toFixed(0)}% <DockBtn t={t} /></div>)}</div>
                <div><div className="text-stone-500 font-mono text-[11px] mb-1">Repurposing</div>{(net.repurposing || []).slice(0, 6).map((d, i) => <div key={i} className="text-stone-700">{d.disease_name} <span className="text-stone-400">{((d.probability || 0) * 100).toFixed(0)}%</span></div>)}</div>
              </div>
            )}
          </div>
        )}

        {/* EXTRAS */}
        <div className={cardCls}>
          <H>Extras (comprobaciones adicionales)</H>
          <label className="flex items-center gap-2 text-[13px] font-hand cursor-pointer mb-1">
            <input type="checkbox" checked={showTox} onChange={toggleTox} /> <Biohazard className="w-4 h-4 text-amber-800" /> Toxicidad GNN (Chemprop, Tox21)
          </label>
          {showTox && <div className="pl-6 mb-2">{!tox ? <span className="text-stone-400 text-[12px]">Calculando…</span> : !tox.available ? <span className="text-amber-800 text-[12px]">{tox.reason || 'No disponible'}</span> : <div className="flex flex-wrap gap-1.5">{(tox.predictions || []).slice(0, 8).map((t, i) => <span key={i} className="px-2 py-0.5 rounded text-[11px] font-mono" style={{ background: `${probColor(t.probability || 0)}15`, color: probColor(t.probability || 0) }}>{t.assay} {((t.probability || 0) * 100).toFixed(0)}%</span>)}</div>}</div>}

          <label className="flex items-center gap-2 text-[13px] font-hand cursor-pointer">
            <input type="checkbox" checked={showDock} onChange={() => showDock ? setShowDock(false) : openDock()} /> <TargetIcon className="w-4 h-4 text-amber-800" /> Docking estructural (¿se une a una diana?)
          </label>
          {showDock && (
            <div className="pl-6 mt-2">
              <div className="flex gap-2 items-center flex-wrap mb-2 text-[12px]">
                <span className="text-stone-500 font-mono">pH:</span>
                {PH_PRESETS.map(x => <button key={x} onClick={() => { setPh(x); if (choice) runDock(choice, x); }} className={`px-2 py-0.5 rounded font-mono ${ph === x ? 'bg-[#2d2621] text-[#faf6ee]' : 'bg-stone-500/10 text-stone-600'}`}>{x}</button>)}
                <span className="text-stone-400 mx-2">·</span>
                <span className="text-stone-500 font-mono">receptor preparado:</span>
                {preparedTargets.map(t => <button key={t.target} onClick={() => runDock({ kind: 'prepared', target: t.target, name: t.name })} className="px-2 py-0.5 rounded font-mono bg-sky-600/10 text-sky-800">{t.name}</button>)}
              </div>
              <div className="text-stone-400 text-[11px] font-hand mb-1">Elige un receptor preparado, o pulsa <b>dock</b> junto a una diana de arriba (se prepara su estructura AlphaFold al vuelo). Cambia el pH para reintentar con otra protonación.</div>
              {choice && <div className="text-[12px] mb-1">Diana: <b>{choice.name}</b> · pH {ph}</div>}
              {dockLoading && <div className="text-stone-400 text-[12px]">Acoplando… (si prepara receptor nuevo puede tardar)</div>}
              {dock && (dock.available
                ? <div className="text-[13px]">Afinidad: <span className="font-mono font-bold" style={{ color: affColor(dock.affinity_kcal_mol || 0) }}>{dock.affinity_kcal_mol?.toFixed(2)} kcal/mol</span> {dock.blind && <span className="text-amber-700 text-[11px]">(ciego · AlphaFold, baja confianza)</span>}
                    <button className="ml-2 text-[11px] underline text-stone-500" onClick={() => choice && runDock(choice)}>reintentar</button>
                    <button className="ml-2 text-[11px] px-1.5 py-0.5 rounded bg-purple-600/10 text-purple-800 border border-purple-800/20" onClick={runFunnel} disabled={funnelLoading}>{funnelLoading ? 'funnel…' : '📊 funnel de poses'}</button>
                  </div>
                : <div className="text-amber-800 text-[12px]">{(dock as any).reason || 'No disponible'}</div>)}
              {funnel && (funnel.available
                ? <div className="mt-2">
                    {funnel.plot_png && <img src={funnel.plot_png} alt="funnel de poses" className="max-w-[420px] w-full rounded border border-stone-300" />}
                    {funnel.recommended_pose && <div className="text-[12px] mt-1">Pose recomendada: <b>#{funnel.recommended_pose.pose}</b> (RMSD {funnel.recommended_pose.rmsd} Å · {funnel.recommended_pose.affinity} kcal/mol) — la de abajo-izquierda.</div>}
                    <div className="text-stone-400 text-[10px] font-hand">{funnel.note}</div>
                  </div>
                : funnel && <div className="text-amber-800 text-[12px] mt-1">{(funnel as any).reason || 'Funnel no disponible'}</div>)}
              <div className="text-stone-400 text-[10px] font-hand mt-1"><b>NDM-1</b> es específico de antibióticos; para otras dianas se prepara la estructura AlphaFold al vuelo (docking ciego).</div>
            </div>
          )}
        </div>

        <div className="text-stone-400 text-[11px] font-hand mb-4">Todo es predicción in silico (hipótesis), no validación experimental.</div>
      </>)}
    </div>
  );
}
