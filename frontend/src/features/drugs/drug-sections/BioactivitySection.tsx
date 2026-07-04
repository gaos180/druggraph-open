import React, { useState } from 'react';
import { FlaskConical, Activity, CheckCircle2, XCircle } from 'lucide-react';
import { bioactivityApi, BioactivityResponse } from '../../../api/bioactivity';
import ReportPanel from '../../reports/ReportPanel';

const cardCls = 'bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-4 shadow-[2px_2.5px_0px_rgba(30,25,21,0.06)]';
const thc = 'px-2 py-1.5 text-left text-stone-500 font-mono text-[11px]';

/**
 * BioactivitySection — bioactividad experimental (ChEMBL + PubChem).
 * Carga bajo demanda: potencia (pChEMBL), mecanismo de acción y resumen de bioensayos.
 * `mode` decide el origen: fármaco de la base (drugId) o compuesto sandbox (smiles).
 */
export default function BioactivitySection({
  drugId, smiles, showReport = true,
}: { drugId?: string; smiles?: string; showReport?: boolean }) {
  const [data, setData] = useState<BioactivityResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);

  const load = async () => {
    setLoading(true); setError('');
    try {
      const res = drugId
        ? await bioactivityApi.forDrug(drugId)
        : await bioactivityApi.forSmiles(smiles || '');
      setData(res.data);
      setLoaded(true);
    } catch (err: any) {
      setError(err?.response?.data?.error || 'No se pudo obtener la bioactividad.');
    } finally {
      setLoading(false);
    }
  };

  if (!loaded) {
    return (
      <div className={cardCls}>
        <div className="flex items-center gap-2 mb-2">
          <FlaskConical className="w-5 h-5 text-amber-700" />
          <h3 className="font-hand font-bold text-lg text-stone-900">Bioactividad experimental</h3>
        </div>
        <p className="text-[13px] text-stone-600 mb-3">
          Datos <strong>medidos</strong> de ChEMBL (potencia IC50/Ki, mecanismo de acción) y
          PubChem (bioensayos activo/inactivo). Se consultan en vivo.
        </p>
        <button onClick={load} disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#2d2621] text-[#faf6ee] font-semibold text-sm cursor-pointer disabled:opacity-50">
          <Activity className="w-4 h-4" />
          {loading ? 'Consultando ChEMBL y PubChem…' : 'Cargar bioactividad'}
        </button>
        {error && <div className="mt-3 text-sm text-red-700">{error}</div>}
      </div>
    );
  }

  if (data && data.available === false) {
    return <div className={cardCls}><p className="text-[13px] text-stone-600">{data.notes?.[0] || 'Sin bioactividad estructural disponible.'}</p></div>;
  }

  const chembl = data?.chembl;
  const pubchem = data?.pubchem;

  return (
    <div className="flex flex-col gap-4">
      {/* Mecanismo de acción */}
      {chembl?.available && chembl.mechanisms.length > 0 && (
        <div className={cardCls}>
          <div className="text-[11px] font-bold font-mono tracking-wider text-[#7c2d12] mb-2">MECANISMO DE ACCIÓN (ChEMBL)</div>
          <div className="flex flex-wrap gap-2">
            {chembl.mechanisms.map((m, i) => (
              <span key={i} className="bg-amber-100 text-amber-900 px-2.5 py-1 rounded-lg text-[13px] font-medium">
                {m.mechanism_of_action}{m.action_type ? ` · ${m.action_type}` : ''}
              </span>
            ))}
          </div>
          {chembl.molecule && (
            <div className="text-xs text-stone-500 mt-2 font-mono">
              {chembl.molecule.chembl_id}{chembl.molecule.max_phase != null ? ` · fase máx. ${chembl.molecule.max_phase}` : ''}
            </div>
          )}
        </div>
      )}

      {/* Potencia */}
      {chembl?.available && chembl.activities.length > 0 && (
        <div className={cardCls}>
          <div className="text-[11px] font-bold font-mono tracking-wider text-[#7c2d12] mb-2">POTENCIA MEDIDA (pChEMBL, mayor = más potente)</div>
          <div className="max-h-[320px] overflow-y-auto">
            <table className="w-full border-collapse text-xs">
              <thead><tr className="border-b border-stone-800/10">{['Tipo', 'Valor', 'pChEMBL', 'Diana', 'Organismo'].map(h => <th key={h} className={thc}>{h}</th>)}</tr></thead>
              <tbody>
                {chembl.activities.map((a, i) => (
                  <tr key={i} className={`border-b border-stone-800/5 ${i % 2 ? 'bg-stone-500/5' : ''}`}>
                    <td className="px-2 py-1 text-stone-700 font-mono">{a.standard_type}</td>
                    <td className="px-2 py-1 text-stone-600">{a.standard_value != null ? `${a.standard_value} ${a.standard_units || ''}` : '—'}</td>
                    <td className="px-2 py-1 font-mono font-semibold" style={{ color: (a.pchembl_value || 0) >= 6 ? '#15803d' : '#b45309' }}>{a.pchembl_value ?? '—'}</td>
                    <td className="px-2 py-1 text-sky-800 max-w-[220px]">{a.target_pref_name || '—'}</td>
                    <td className="px-2 py-1 text-stone-500">{a.target_organism || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* PubChem bioassays */}
      {pubchem?.available && (
        <div className={cardCls}>
          <div className="text-[11px] font-bold font-mono tracking-wider text-[#7c2d12] mb-2">BIOENSAYOS PUBCHEM (CID {pubchem.cid})</div>
          <div className="flex gap-5 mb-3">
            <div className="flex items-center gap-1.5 text-emerald-700"><CheckCircle2 className="w-4 h-4" /><strong>{pubchem.active}</strong> activos</div>
            <div className="flex items-center gap-1.5 text-stone-500"><XCircle className="w-4 h-4" /><strong>{pubchem.inactive}</strong> inactivos</div>
            <div className="text-stone-500">{pubchem.total} ensayos totales</div>
          </div>
          {pubchem.assays.filter(a => a.activity === 'Active').length > 0 && (
            <div className="max-h-[260px] overflow-y-auto">
              <table className="w-full border-collapse text-xs">
                <thead><tr className="border-b border-stone-800/10">{['AID', 'Ensayo', 'Tipo'].map(h => <th key={h} className={thc}>{h}</th>)}</tr></thead>
                <tbody>
                  {pubchem.assays.filter(a => a.activity === 'Active').slice(0, 30).map((a, i) => (
                    <tr key={i} className={`border-b border-stone-800/5 ${i % 2 ? 'bg-stone-500/5' : ''}`}>
                      <td className="px-2 py-1 text-sky-800 font-mono">{a.aid}</td>
                      <td className="px-2 py-1 text-stone-600 max-w-[420px]">{a.assay_name?.slice(0, 90) || '—'}</td>
                      <td className="px-2 py-1 text-stone-500">{a.assay_type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {data && showReport && <ReportPanel kind="bioactivity" payload={data} />}
    </div>
  );
}
