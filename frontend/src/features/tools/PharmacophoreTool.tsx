import React, { useState } from 'react';
import { Atom } from 'lucide-react';
import { toolsApi, PharmacophoreResult, PharmaFeature } from '../../api/tools';
import { usePageTitle } from '../../hooks/usePageTitle';
import { HandTitle, PencilButton } from '../../components/notebook';

const cardCls = 'bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-5 mb-4 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]';
const inpCls = 'bg-[#faf6ee] border-2 border-[#3f3429] rounded-lg px-3 py-2 text-[13px] font-hand outline-none';

const ROLE_COLOR: Record<string, string> = {
  hbond: '#2563eb', hydrophobic: '#b45309', aromatic: '#7c3aed',
  ionic: '#dc2626', metal: '#0891b2', other: '#6b7280',
};

function Chip({ f }: { f: PharmaFeature }) {
  const col = ROLE_COLOR[f.role] || ROLE_COLOR.other;
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-mono"
      style={{ background: `${col}18`, color: col, border: `1px solid ${col}40` }}>
      {f.label}{f.fraction !== undefined ? ` · ${(f.fraction * 100).toFixed(0)}%` : ''}
    </span>
  );
}

export default function PharmacophoreTool() {
  usePageTitle('Pharmacóforos 3D');
  const [smiles, setSmiles] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<PharmacophoreResult | null>(null);

  const run = async () => {
    const s = smiles.trim();
    if (!s) { setError('Ingresa uno o varios SMILES (separados por |), o un DrugBank ID'); return; }
    setLoading(true); setError(''); setResult(null);
    try {
      const body = /^D[CB]\d+$/i.test(s) ? { drug_id: s } : { smiles: s };
      const res = await toolsApi.pharmacophore(body);
      setResult(res.data);
    } catch (err: any) {
      const data = err?.response?.data;
      setError(data?.reason || data?.error || err?.message || 'Error al construir');
    } finally { setLoading(false); }
  };

  const single = result?.mode === 'single';
  const feats = (single ? result?.features : result?.consensus_features) || [];

  return (
    <div className="max-w-4xl">
      <HandTitle className="text-2xl flex items-center gap-2"><Atom className="w-6 h-6 text-amber-800" /> Pharmacóforos 3D</HandTitle>
      <p className="text-stone-500 text-[13px] font-hand mt-1 mb-5">
        Modelo pharmacofórico <b>ligand-based</b> (RDKit): rasgos estérico-electrónicos (donadores/aceptores de H, hidrofóbicos, aromáticos, ionizables) y su geometría 3D. Un SMILES → rasgos + distancias; varios activos (separados por <code>|</code>) → perfil de consenso. Base del Tier 5 estructural.
      </p>

      <div className={cardCls}>
        <div className="flex gap-3 items-end flex-wrap">
          <div className="flex-1 min-w-[260px]">
            <label className="text-[11px] text-stone-500 block mb-1 font-mono">SMILES (1 o varios con |) · o DrugBank ID</label>
            <input className={`${inpCls} w-full`} value={smiles} onChange={e => setSmiles(e.target.value)}
              placeholder="CC(=O)Oc1ccccc1C(=O)O  ·  DC1234  ·  smi1|smi2|smi3" onKeyDown={e => e.key === 'Enter' && run()} />
          </div>
          <PencilButton variant="solid" onClick={run} disabled={loading}>{loading ? 'Construyendo…' : 'Construir'}</PencilButton>
        </div>
        {error && <div className="text-red-600 text-[13px] mt-2">{error}</div>}
      </div>

      {result?.available && (
        <>
          <div className={cardCls}>
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-amber-800/10 text-amber-800">{result.mode}</span>
              <span className="text-stone-500 text-[12px] font-hand">{result.n_molecules} molécula(s)</span>
              {result.drug_id && <span className="text-sky-700 text-xs font-mono">{result.drug_id}</span>}
            </div>
            <div className="flex flex-wrap gap-1.5">{feats.map((f, i) => <Chip key={i} f={f} />)}</div>
          </div>

          {single && result?.distances && result.distances.length > 0 && (
            <div className={cardCls}>
              <div className="text-stone-600 text-[12px] font-mono mb-2">GEOMETRÍA — distancias par a par más cortas (Å)</div>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-xs">
                  <thead><tr className="border-b border-stone-800/10">{['Rasgo A', 'Rasgo B', 'Distancia (Å)'].map((h, i) => <th key={i} className="px-2 py-1.5 text-left text-stone-500 font-mono text-[11px]">{h}</th>)}</tr></thead>
                  <tbody>
                    {result.distances.slice(0, 12).map((d, i) => (
                      <tr key={i} className={`border-b border-stone-800/5 ${i % 2 ? 'bg-stone-500/5' : ''}`}>
                        <td className="px-2 py-1.5 font-mono text-stone-700">{d.family_a}</td>
                        <td className="px-2 py-1.5 font-mono text-stone-700">{d.family_b}</td>
                        <td className="px-2 py-1.5 font-mono text-amber-700">{d.distance.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="text-stone-400 text-[11px] font-hand mb-2">{result.note}</div>
          {result.references && (
            <details className="text-stone-400 text-[10px] font-mono mb-4">
              <summary className="cursor-pointer">Referencias</summary>
              <ul className="mt-1 list-disc pl-5 space-y-0.5">{result.references.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </details>
          )}
        </>
      )}
    </div>
  );
}
