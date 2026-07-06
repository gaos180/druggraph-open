import React, { useState } from 'react';
import { Microscope, Target as TargetIcon, Biohazard } from 'lucide-react';
import { toolsApi, MoleculeAnalysisResult, ChempropToxResult, DockingResult, DockingTarget } from '../../api/tools';
import { usePageTitle } from '../../hooks/usePageTitle';
import { HandTitle, PencilButton } from '../../components/notebook';

const cardCls = 'bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-4 mb-4 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]';
const inpCls = 'bg-[#faf6ee] border-2 border-[#3f3429] rounded-lg px-3 py-2 text-[13px] font-hand outline-none';
const H = ({ children }: any) => <div className="text-stone-600 text-[12px] font-mono mb-2 uppercase tracking-wide">{children}</div>;

const ROLE_COLOR: Record<string, string> = { hbond: '#2563eb', hydrophobic: '#b45309', aromatic: '#7c3aed', ionic: '#dc2626', metal: '#0891b2', other: '#6b7280' };
function affColor(a: number) { return a <= -8 ? '#15803d' : a <= -6 ? '#b45309' : '#6b7280'; }
function probColor(v: number) { return v >= 0.66 ? '#dc2626' : v >= 0.33 ? '#b45309' : '#15803d'; }

export default function MoleculeLabTool() {
  usePageTitle('Laboratorio molecular');
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [r, setR] = useState<MoleculeAnalysisResult | null>(null);

  // extras
  const [showTox, setShowTox] = useState(false);
  const [tox, setTox] = useState<ChempropToxResult | null>(null);
  const [showDock, setShowDock] = useState(false);
  const [dockTargets, setDockTargets] = useState<DockingTarget[]>([]);
  const [dockTarget, setDockTarget] = useState('');
  const [dock, setDock] = useState<DockingResult | null>(null);
  const [dockLoading, setDockLoading] = useState(false);

  const analyze = async () => {
    const s = q.trim();
    if (!s) { setError('Ingresa un SMILES o DrugBank ID'); return; }
    setLoading(true); setError(''); setR(null); setTox(null); setDock(null); setShowTox(false); setShowDock(false);
    try {
      const body = /^D[CB]\d+$/i.test(s) ? { drug_id: s } : { smiles: s };
      const res = await toolsApi.moleculeAnalysis(body);
      setR(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.reason || err?.response?.data?.error || 'Error al analizar');
    } finally { setLoading(false); }
  };

  const body = () => (r?.drug_id ? { drug_id: r.drug_id } : { smiles: r?.smiles });

  const toggleTox = async () => {
    const on = !showTox; setShowTox(on);
    if (on && !tox) { try { const res = await toolsApi.chempropTox(body() as any); setTox(res.data); } catch (e: any) { setTox({ available: false, reason: e?.response?.data?.error } as any); } }
  };
  const toggleDock = async () => {
    const on = !showDock; setShowDock(on);
    if (on && dockTargets.length === 0) {
      try { const res = await toolsApi.dockingTargets(); setDockTargets(res.data.targets || []); if (res.data.targets?.[0]) setDockTarget(res.data.targets[0].target); }
      catch { setDockTargets([]); }
    }
  };
  const runDock = async () => {
    if (!dockTarget) return;
    setDockLoading(true); setDock(null);
    try { const res = await toolsApi.docking({ ...(body() as any), target: dockTarget }); setDock(res.data); }
    catch (e: any) { setDock({ available: false, reason: e?.response?.data?.error } as any); }
    finally { setDockLoading(false); }
  };

  const p = r?.properties; const net = r?.network;
  const admetPreds = (r?.admet && (r.admet as any).predictions) || [];
  const phCounts = r?.pharmacophore?.feature_counts || {};

  return (
    <div className="max-w-5xl">
      <HandTitle className="text-2xl flex items-center gap-2"><Microscope className="w-6 h-6 text-amber-800" /> Laboratorio molecular</HandTitle>
      <p className="text-stone-500 text-[13px] font-hand mt-1 mb-4">
        Panel integral: analiza una molécula con todas las herramientas de una vez — propiedades, a quién se parece, espacio químico, pharmacóforo, ADMET, dianas predichas y repurposing. La <b>toxicidad GNN</b> y el <b>docking</b> son extras opcionales.
      </p>

      <div className={cardCls}>
        <div className="flex gap-3 items-end flex-wrap">
          <div className="flex-1 min-w-[260px]">
            <label className="text-[11px] text-stone-500 block mb-1 font-mono">SMILES o DrugBank ID</label>
            <input className={`${inpCls} w-full`} value={q} onChange={e => setQ(e.target.value)}
              placeholder="CC(=O)Oc1ccccc1C(=O)O  ·  DC4" onKeyDown={e => e.key === 'Enter' && analyze()} />
          </div>
          <PencilButton variant="solid" onClick={analyze} disabled={loading}>{loading ? 'Analizando…' : 'Analizar'}</PencilButton>
        </div>
        {error && <div className="text-red-600 text-[13px] mt-2">{error}</div>}
      </div>

      {r?.available && (
        <>
          {/* Identidad + propiedades */}
          {p?.available && (
            <div className={cardCls}>
              <H>Identidad y propiedades {r.drug_id && <span className="text-sky-700">· {r.drug_id}</span>}</H>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
                {[['Fórmula', p.formula], ['MW', p.mw], ['logP', p.logp], ['TPSA', p.tpsa],
                  ['QED', p.qed], ['SA', p.sa_score], ['Rot. bonds', p.rot_bonds], ['Lipinski', `${p.lipinski_ok}/4`]].map(([k, v]: any) => (
                  <div key={k} className="bg-stone-500/5 rounded-lg py-1.5"><div className="text-stone-800 font-mono text-sm font-bold">{v}</div><div className="text-stone-500 text-[10px]">{k}</div></div>
                ))}
              </div>
              {r.chemical_space?.available && <div className="text-stone-400 text-[11px] font-mono mt-2">Espacio químico: cluster {r.chemical_space.cluster} @ ({r.chemical_space.x?.toFixed?.(1)}, {r.chemical_space.y?.toFixed?.(1)})</div>}
            </div>
          )}

          {/* Vecinos */}
          {r.neighbors && r.neighbors.length > 0 && (
            <div className={cardCls}>
              <H>A quién se parece (vecinos estructurales)</H>
              <div className="flex flex-wrap gap-1.5">
                {r.neighbors.map((n, i) => (
                  <span key={i} className="px-2 py-0.5 rounded-full text-[11px] font-mono bg-sky-500/10 text-sky-800 border border-sky-800/20">{n.name || n.drug_id} · {(n.similarity * 100).toFixed(0)}%</span>
                ))}
              </div>
            </div>
          )}

          {/* Pharmacóforo */}
          {Object.keys(phCounts).length > 0 && (
            <div className={cardCls}>
              <H>Pharmacóforo (rasgos 3D)</H>
              <div className="flex flex-wrap gap-1.5">
                {r.pharmacophore?.features && Object.entries(phCounts).map(([fam, cnt]: any) => {
                  const role = (r.pharmacophore?.features?.find(f => f.family === fam)?.role) || 'other';
                  const col = ROLE_COLOR[role];
                  return <span key={fam} className="px-2 py-0.5 rounded-full text-[11px] font-mono" style={{ background: `${col}18`, color: col, border: `1px solid ${col}40` }}>{fam} ×{cnt}</span>;
                })}
              </div>
            </div>
          )}

          {/* ADMET */}
          {admetPreds.length > 0 && (
            <div className={cardCls}>
              <H>ADMET</H>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
                {admetPreds.map((a: any) => (
                  <div key={a.endpoint} className="flex items-center gap-2 text-[13px]">
                    <span className="flex-1 text-stone-700 font-hand truncate">{a.label}</span>
                    {a.task === 'classification'
                      ? <span className="font-mono" style={{ color: probColor(a.proba || 0) }}>{((a.proba || 0) * 100).toFixed(0)}%</span>
                      : <span className="font-mono text-sky-700">{a.value?.toFixed(2)} {a.unit}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Red: dianas + repurposing */}
          {net && (
            <div className={cardCls}>
              <H>Dianas y repurposing {net.proxy_drug && <span className="text-stone-400 normal-case">· vía {net.proxy_drug.name} (proxy, {(net.proxy_drug.similarity * 100).toFixed(0)}%)</span>}</H>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-[12px]">
                <div>
                  <div className="text-stone-500 font-mono text-[11px] mb-1">Documentadas</div>
                  {(net.documented_targets || []).slice(0, 6).map((t, i) => <div key={i} className="text-stone-700"><span className="text-amber-700 font-mono">{t.gene || '—'}</span> {t.name}</div>)}
                  {(!net.documented_targets || net.documented_targets.length === 0) && <div className="text-stone-400">—</div>}
                </div>
                <div>
                  <div className="text-stone-500 font-mono text-[11px] mb-1">Predichas (DTI-GNN)</div>
                  {(net.predicted_targets || []).slice(0, 6).map((t, i) => <div key={i} className="text-stone-700"><span className="text-purple-700 font-mono">{t.gene_name || '—'}</span> {((t.probability || 0) * 100).toFixed(0)}%</div>)}
                </div>
                <div>
                  <div className="text-stone-500 font-mono text-[11px] mb-1">Repurposing (Disease-GNN)</div>
                  {(net.repurposing || []).slice(0, 6).map((d, i) => <div key={i} className="text-stone-700">{d.disease_name} <span className="text-stone-400">{(d.probability * 100).toFixed(0)}%</span></div>)}
                </div>
              </div>
            </div>
          )}

          {/* EXTRAS */}
          <div className={cardCls}>
            <H>Extras (comprobaciones adicionales)</H>
            <label className="flex items-center gap-2 text-[13px] font-hand cursor-pointer mb-1">
              <input type="checkbox" checked={showTox} onChange={toggleTox} /> <Biohazard className="w-4 h-4 text-amber-800" /> Toxicidad GNN (Chemprop, Tox21)
            </label>
            {showTox && (
              <div className="pl-6 mb-2">
                {!tox ? <span className="text-stone-400 text-[12px]">Calculando…</span> :
                  !tox.available ? <span className="text-amber-800 text-[12px]">{tox.reason || 'No disponible'}</span> :
                  <div className="flex flex-wrap gap-1.5">{(tox.predictions || []).slice(0, 8).map((t, i) => <span key={i} className="px-2 py-0.5 rounded text-[11px] font-mono" style={{ background: `${probColor(t.probability || 0)}15`, color: probColor(t.probability || 0) }}>{t.assay} {((t.probability || 0) * 100).toFixed(0)}%</span>)}</div>}
              </div>
            )}
            <label className="flex items-center gap-2 text-[13px] font-hand cursor-pointer">
              <input type="checkbox" checked={showDock} onChange={toggleDock} /> <TargetIcon className="w-4 h-4 text-amber-800" /> Docking estructural (¿se une a una diana?)
            </label>
            {showDock && (
              <div className="pl-6 mt-2">
                <div className="flex gap-2 items-end flex-wrap mb-1">
                  <select className={inpCls} value={dockTarget} onChange={e => setDockTarget(e.target.value)}>
                    {dockTargets.length === 0 && <option value="">(sin receptores preparados)</option>}
                    {dockTargets.map(t => <option key={t.target} value={t.target}>{t.name}{t.pdb_id ? ` (${t.pdb_id})` : ''}</option>)}
                  </select>
                  <PencilButton onClick={runDock} disabled={dockLoading || !dockTarget}>{dockLoading ? 'Acoplando…' : 'Acoplar'}</PencilButton>
                </div>
                {dock && (dock.available
                  ? <div className="text-[13px]">Afinidad a <b>{dock.target_name}</b>: <span className="font-mono font-bold" style={{ color: affColor(dock.affinity_kcal_mol || 0) }}>{dock.affinity_kcal_mol?.toFixed(2)} kcal/mol</span></div>
                  : <div className="text-amber-800 text-[12px]">{(dock as any).reason || 'No disponible'}</div>)}
                <div className="text-stone-400 text-[10px] font-hand mt-1">Para acoplar contra una diana predicha, prepara su receptor con scripts/prepare_receptor.py.</div>
              </div>
            )}
          </div>

          <div className="text-stone-400 text-[11px] font-hand mb-4">Todo es predicción in silico (hipótesis), no validación experimental.</div>
        </>
      )}
    </div>
  );
}
