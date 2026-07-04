import React, { useState, useCallback, useRef } from 'react';
import { BarChart3, Download, CheckCircle2 } from 'lucide-react';
import { toolsApi, DegGene, DegAnalysisResult, DegAnalysisRequest, SignatureReversionResult } from '../../api/tools';
import VolcanoPlot from './components/VolcanoPlot';
import GoEnrichmentChart from './components/GoEnrichmentChart';
import { usePageTitle } from '../../hooks/usePageTitle';
import { HandTitle, PencilButton } from '../../components/notebook';
import ReportPanel from '../reports/ReportPanel';

const cardCls = 'bg-[#faf6ee] border-2 border-stone-800/15 rounded-xl p-5 mb-4 shadow-[2px_2.5px_0_rgba(30,25,21,0.06)]';
const inpCls = 'w-full bg-[#faf6ee] border-2 border-[#3f3429] rounded-lg px-3 py-2 text-[13px] font-hand outline-none';
const lblCls = 'text-[11px] text-stone-500 mb-1 block font-mono';

function pillBtn(active: boolean) {
  return `px-4 py-2 rounded-lg text-sm font-hand border-2 cursor-pointer ${active ? 'bg-[#2d2621] text-[#faf6ee] border-[#1e1814]' : 'bg-white text-stone-600 border-stone-300'}`;
}

function parseGeneFile(text: string): DegGene[] {
  const lines = text.trim().split(/\r?\n/).filter(l => l.trim());
  if (!lines.length) return [];
  const sep = lines[0].includes('\t') ? '\t' : ',';
  const first = lines[0].split(sep);
  const hasHeader = isNaN(Number(first[1]));
  const dataLines = hasHeader ? lines.slice(1) : lines;
  let symCol = 0, fcCol = -1, pvCol = -1, padjCol = -1;
  if (hasHeader) {
    first.forEach((h, i) => {
      const lh = h.toLowerCase().replace(/[^a-z0-9]/g, '');
      if (['gene', 'symbol', 'genename', 'id'].some(k => lh.includes(k))) symCol = i;
      if (['log2fc', 'logfc', 'log2foldchange', 'fc', 'lfc'].some(k => lh.includes(k))) fcCol = i;
      if (['pvalue', 'pval', 'p_value', 'p.value'].some(k => lh === k)) pvCol = i;
      if (['padj', 'fdr', 'adj', 'bh'].some(k => lh.includes(k))) padjCol = i;
    });
  } else {
    fcCol = first.length > 1 ? 1 : -1; pvCol = first.length > 2 ? 2 : -1; padjCol = first.length > 3 ? 3 : -1;
  }
  return dataLines.map(line => {
    const cols = line.split(sep);
    const symbol = (cols[symCol] || '').replace(/['"]/g, '').trim();
    if (!symbol) return null;
    const gene: DegGene = { symbol };
    if (fcCol >= 0 && cols[fcCol]) gene.log2fc = parseFloat(cols[fcCol]);
    if (pvCol >= 0 && cols[pvCol]) gene.pvalue = parseFloat(cols[pvCol]);
    if (padjCol >= 0 && cols[padjCol]) gene.padj = parseFloat(cols[padjCol]);
    return gene;
  }).filter(Boolean) as DegGene[];
}

function StatBox({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="text-center min-w-[80px]">
      <div className="text-xl font-bold font-hand" style={{ color: color || '#292524' }}>{value}</div>
      <div className="text-[11px] text-stone-500">{label}</div>
    </div>
  );
}

export default function DegAnalysisTool() {
  usePageTitle('Análisis DEG');
  const fileRef = useRef<HTMLInputElement>(null);
  const [drugId, setDrugId] = useState('');
  const [genes, setGenes] = useState<DegGene[]>([]);
  const [fileName, setFileName] = useState('');
  const [geneCount, setGeneCount] = useState(0);
  const [fcThr, setFcThr] = useState(1.0);
  const [pvalThr, setPvalThr] = useState(0.05);
  const [useFdr, setUseFdr] = useState(false);
  const [organism, setOrganism] = useState('hsapiens');
  const [sigMethod, setSigMethod] = useState('fdr_bh');
  const [goSources, setGoSources] = useState<string[]>(['GO:BP', 'GO:MF', 'GO:CC', 'KEGG']);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<DegAnalysisResult | null>(null);
  const [activeTab, setActiveTab] = useState<'volcano' | 'overlap' | 'go' | 'genes' | 'reversion'>('volcano');
  const [reversion, setReversion] = useState<SignatureReversionResult | null>(null);
  const [reversionLoading, setReversionLoading] = useState(false);
  const [reversionError, setReversionError] = useState('');

  const loadReversion = async () => {
    if (!result || reversion || reversionLoading) return;
    const sig = result.genes.filter(g => g.is_sig);
    const up = sig.filter(g => g.direction === 'up').map(g => g.symbol);
    const dn = sig.filter(g => g.direction === 'down').map(g => g.symbol);
    if (up.length + dn.length === 0) { setReversionError('No hay genes significativos con dirección para construir la firma.'); return; }
    setReversionLoading(true); setReversionError('');
    try { const res = await toolsApi.signatureReversion({ up_genes: up, dn_genes: dn, reverse: true }); setReversion(res.data); }
    catch (err: any) { setReversionError(err?.response?.data?.error || 'No se pudo consultar LINCS.'); }
    finally { setReversionLoading(false); }
  };

  const handleFile = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = ev => { const parsed = parseGeneFile(ev.target?.result as string); setGenes(parsed); setGeneCount(parsed.length); };
    reader.readAsText(file);
  }, []);

  const toggleGoSource = (src: string) => setGoSources(prev => prev.includes(src) ? prev.filter(s => s !== src) : [...prev, src]);

  const handleAnalyze = async () => {
    if (!drugId.trim()) { setError('Ingresa el ID de fármaco (ej: DC1234)'); return; }
    if (!genes.length) { setError('Carga un archivo de genes primero'); return; }
    setLoading(true); setError(''); setResult(null);
    const body: DegAnalysisRequest = {
      drug_id: drugId.trim().toUpperCase(), genes, fc_threshold: fcThr, pval_threshold: pvalThr,
      use_fdr: useFdr, organism, go_sources: goSources, significance_method: sigMethod,
    };
    try { const res = await toolsApi.degAnalysis(body); setResult(res.data); setActiveTab('volcano'); setReversion(null); setReversionError(''); }
    catch (err: unknown) { setError((err as any)?.response?.data?.error || (err as any)?.message || 'Error al conectar con el servidor'); }
    finally { setLoading(false); }
  };

  const exportOverlap = () => {
    if (!result) return;
    const header = 'symbol,log2fc,pvalue,padj,direction,target_id,gene_name,uniprot_id,rel_type';
    const rows = result.overlap.map(g => [g.symbol, g.log2fc, g.pvalue, g.padj, g.direction, g.target_id, g.gene_name, g.uniprot_id, g.rel_type].join(','));
    const blob = new Blob([[header, ...rows].join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `overlap_${drugId}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const thc = 'px-2 py-1.5 text-left text-stone-500 font-mono text-[11px]';

  return (
    <div className="max-w-5xl">
      <HandTitle className="text-2xl flex items-center gap-2"><BarChart3 className="w-6 h-6 text-amber-800" /> Análisis de Expresión Diferencial</HandTitle>
      <p className="text-stone-500 text-[13px] font-hand mt-1 mb-5">Cruza genes diferencialmente expresados con los targets de un fármaco y calcula enriquecimiento GO/KEGG.</p>

      <div className={cardCls}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <span className={lblCls}>ARCHIVO DE GENES (CSV/TSV)</span>
            <div onClick={() => fileRef.current?.click()} className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer mb-3 ${genes.length ? 'border-emerald-400 bg-emerald-50/50' : 'border-stone-400 bg-stone-500/5'}`}>
              <input ref={fileRef} type="file" accept=".csv,.tsv,.txt" className="hidden" onChange={handleFile} />
              {genes.length ? (
                <div>
                  <div className="text-emerald-700 text-[13px] font-bold flex items-center justify-center gap-1.5"><CheckCircle2 className="w-4 h-4" /> {fileName}</div>
                  <div className="text-stone-500 text-xs mt-1">{geneCount} genes{genes[0]?.log2fc !== undefined ? ' (con log2FC)' : ' (lista simple)'}{genes[0]?.pvalue !== undefined ? ' + p-valor' : ''}</div>
                </div>
              ) : (
                <div className="text-stone-500 text-[13px] font-hand">Clic para cargar CSV/TSV<br /><span className="text-[11px]">Columnas: gene, log2fc, pvalue, padj (opcionales)</span></div>
              )}
            </div>
            <span className={lblCls}>DRUGBANK ID</span>
            <input className={`${inpCls} mb-3`} value={drugId} onChange={e => setDrugId(e.target.value)} placeholder="DC1234" />
            <span className={lblCls}>ORGANISMO</span>
            <select className={inpCls} value={organism} onChange={e => setOrganism(e.target.value)}>
              <option value="hsapiens">Homo sapiens</option><option value="mmusculus">Mus musculus</option>
              <option value="rnorvegicus">Rattus norvegicus</option><option value="dmelanogaster">Drosophila melanogaster</option>
              <option value="scerevisiae">Saccharomyces cerevisiae</option>
            </select>
          </div>
          <div>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div><span className={lblCls}>UMBRAL |log₂FC|</span><input className={inpCls} type="number" step="0.1" min="0" value={fcThr} onChange={e => setFcThr(Number(e.target.value))} /></div>
              <div><span className={lblCls}>UMBRAL p / FDR</span><input className={inpCls} type="number" step="0.01" min="0" max="1" value={pvalThr} onChange={e => setPvalThr(Number(e.target.value))} /></div>
            </div>
            <span className={lblCls}>ESTADÍSTICO</span>
            <div className="flex gap-2 mb-3">
              {[{ key: false, label: 'p-valor crudo' }, { key: true, label: 'FDR (padj)' }].map(opt => (
                <button key={String(opt.key)} onClick={() => setUseFdr(opt.key)} className={`${pillBtn(useFdr === opt.key)} flex-1`}>{opt.label}</button>
              ))}
            </div>
            <span className={lblCls}>CORRECCIÓN MÚLTIPLE (GO)</span>
            <select className={`${inpCls} mb-3`} value={sigMethod} onChange={e => setSigMethod(e.target.value)}>
              <option value="fdr_bh">FDR Benjamini-Hochberg</option><option value="bonferroni">Bonferroni</option>
              <option value="g_SCS">g:SCS (g:Profiler)</option><option value="fdr_by">FDR Benjamini-Yekutieli</option>
            </select>
            <span className={lblCls}>FUENTES GO</span>
            <div className="flex gap-2 flex-wrap">
              {['GO:BP', 'GO:MF', 'GO:CC', 'KEGG', 'REAC'].map(src => <button key={src} onClick={() => toggleGoSource(src)} className={pillBtn(goSources.includes(src))}>{src}</button>)}
            </div>
          </div>
        </div>
        <div className="mt-5 flex gap-3 items-center">
          <PencilButton variant="solid" onClick={handleAnalyze} disabled={loading}>{loading ? 'Analizando…' : 'Analizar'}</PencilButton>
          {error && <span className="text-red-600 text-[13px]">{error}</span>}
        </div>
      </div>

      {result && (
        <>
          {result.notes.length > 0 && (
            <div className="bg-amber-50 border-2 border-amber-400 rounded-xl p-3 mb-4">{result.notes.map((n, i) => <div key={i} className="text-amber-800 text-xs">⚠ {n}</div>)}</div>
          )}
          <div className={cardCls}>
            <div className="text-[13px] text-stone-500 mb-3.5">Fármaco: <span className="text-sky-700 font-bold">{result.drug.name}</span> <span className="text-stone-500 ml-2 font-mono text-xs">{result.drug.drugbank_id}</span></div>
            <div className="flex gap-6 flex-wrap justify-around">
              <StatBox label="Total" value={result.stats.total_input} />
              <StatBox label="Significativos" value={result.stats.significant} />
              <StatBox label="Up" value={result.stats.up} color="#b91c1c" />
              <StatBox label="Down" value={result.stats.down} color="#2563eb" />
              <StatBox label="Targets" value={result.stats.drug_targets} color="#57534e" />
              <StatBox label="Intersección" value={result.stats.overlap} color="#b45309" />
              <StatBox label="Overlap Up" value={result.stats.overlap_up} color="#b45309" />
              <StatBox label="Overlap Down" value={result.stats.overlap_down} color="#2563eb" />
            </div>
          </div>

          <div className="flex gap-1 border-b border-stone-800/10">
            {[{ key: 'volcano', label: 'Volcano Plot' }, { key: 'overlap', label: `Intersección (${result.stats.overlap})` }, { key: 'go', label: `GO (${result.go_enrichment.length})` }, { key: 'genes', label: `Genes (${result.stats.total_input})` }, { key: 'reversion', label: 'Reversión (LINCS)' }].map(t => (
              <button key={t.key} onClick={() => { setActiveTab(t.key as any); if (t.key === 'reversion') loadReversion(); }} className={`px-4 py-2 text-[13px] font-hand cursor-pointer border-b-2 ${activeTab === t.key ? 'border-sky-600 text-sky-700' : 'border-transparent text-stone-500'}`}>{t.label}</button>
            ))}
          </div>

          <div className={`${cardCls} rounded-t-none`}>
            {activeTab === 'volcano' && (
              result.stats.has_quantitative
                ? <VolcanoPlot genes={result.genes} fcThreshold={fcThr} pvalThreshold={pvalThr} useFdr={useFdr} width={740} height={460} />
                : <div className="text-stone-500 text-[13px] font-hand">No hay datos cuantitativos (log2FC/p-valor). El volcano requiere columnas log2fc y pvalue.</div>
            )}
            {activeTab === 'overlap' && (
              <div>
                <div className="flex justify-between items-center mb-3">
                  <h3 className="text-stone-800 text-sm font-hand font-bold m-0">Genes DEG que son targets de {result.drug.name}</h3>
                  {result.overlap.length > 0 && <PencilButton onClick={exportOverlap} icon={<Download className="w-4 h-4 text-amber-800" />}>CSV</PencilButton>}
                </div>
                {result.overlap.length === 0 ? <div className="text-stone-500 text-[13px] font-hand">Sin intersección directa. Revisa el organismo y los símbolos.</div> : (
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-xs">
                      <thead><tr className="border-b border-stone-800/10">{['Símbolo', 'log2FC', 'p-valor', 'FDR', 'Dir.', 'Target ID', 'UniProt', 'Relación'].map(h => <th key={h} className={thc}>{h}</th>)}</tr></thead>
                      <tbody>
                        {result.overlap.map((g, i) => (
                          <tr key={i} className={`border-b border-stone-800/5 ${i % 2 ? 'bg-stone-500/5' : ''}`}>
                            <td className="px-2 py-1.5 text-amber-700 font-semibold">{g.symbol}</td>
                            <td className="px-2 py-1.5" style={{ color: g.log2fc > 0 ? '#b91c1c' : '#2563eb' }}>{g.log2fc.toFixed(3)}</td>
                            <td className="px-2 py-1.5 text-stone-600">{g.pvalue?.toExponential(2)}</td>
                            <td className="px-2 py-1.5 text-stone-600">{g.padj?.toExponential(2)}</td>
                            <td className="px-2 py-1.5" style={{ color: g.direction === 'up' ? '#b91c1c' : g.direction === 'down' ? '#2563eb' : '#78716c' }}>{g.direction === 'up' ? '↑ Up' : g.direction === 'down' ? '↓ Down' : '—'}</td>
                            <td className="px-2 py-1.5 text-sky-700 font-mono">{g.target_id}</td>
                            <td className="px-2 py-1.5 text-sky-700 font-mono">{g.uniprot_id}</td>
                            <td className="px-2 py-1.5 text-stone-500">{g.rel_type}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
            {activeTab === 'go' && <GoEnrichmentChart terms={result.go_enrichment} width={920} maxTerms={25} />}
            {activeTab === 'genes' && (
              <div>
                <div className="text-stone-500 text-xs mb-2.5 font-hand">{result.stats.significant} significativos de {result.stats.total_input}. Ámbar = target del fármaco.</div>
                <div className="max-h-[420px] overflow-y-auto rounded-lg border border-stone-800/10">
                  <table className="w-full border-collapse text-xs">
                    <thead className="sticky top-0 bg-[#efe7d6] z-10"><tr>{['Símbolo', 'log2FC', 'p-valor', 'Sig?', 'Target?'].map(h => <th key={h} className={thc}>{h}</th>)}</tr></thead>
                    <tbody>
                      {result.genes.map((g, i) => (
                        <tr key={i} className={`border-b border-stone-800/5 ${g.is_target ? 'bg-amber-100/50' : i % 2 ? 'bg-stone-500/5' : ''}`}>
                          <td className="px-2 py-1" style={{ color: g.is_target ? '#b45309' : '#292524', fontWeight: g.is_target ? 600 : 400 }}>{g.symbol}</td>
                          <td className="px-2 py-1" style={{ color: g.log2fc > 0 ? '#b91c1c' : '#2563eb' }}>{g.log2fc !== 0 ? g.log2fc.toFixed(3) : '—'}</td>
                          <td className="px-2 py-1 text-stone-600">{g.pvalue < 1 ? g.pvalue.toExponential(2) : '—'}</td>
                          <td className="px-2 py-1" style={{ color: g.is_sig ? '#15803d' : '#a8a29e' }}>{g.is_sig ? '✓' : '—'}</td>
                          <td className="px-2 py-1" style={{ color: g.is_target ? '#b45309' : '#a8a29e' }}>{g.is_target ? '⬟' : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            {activeTab === 'reversion' && (
              <div>
                <div className="text-stone-500 text-xs mb-2.5 font-hand">
                  Fármacos cuyo perfil transcriptómico L1000 <strong>revierte</strong> la firma DEG (Connectivity Map / L1000CDS2). Candidatos de reposicionamiento: mayor score = mejor reversión.
                </div>
                {reversionLoading && <div className="text-stone-500 text-[13px] font-hand">Consultando LINCS L1000…</div>}
                {reversionError && <div className="text-red-600 text-[13px]">{reversionError}</div>}
                {reversion && !reversion.available && !reversionLoading && (
                  <div className="text-stone-500 text-[13px] font-hand">{reversion.reason || 'Sin resultados de reversión.'}</div>
                )}
                {reversion && reversion.available && (
                  <>
                    <div className="text-[12px] text-stone-500 mb-2">Firma: {reversion.genes_used?.up ?? 0} genes ↑ · {reversion.genes_used?.dn ?? 0} genes ↓</div>
                    <table className="w-full border-collapse text-xs">
                      <thead><tr className="border-b border-stone-800/10">{['Fármaco / perturbación', 'Score', 'Línea celular', 'Dosis'].map(h => <th key={h} className={thc}>{h}</th>)}</tr></thead>
                      <tbody>
                        {reversion.results.map((r, i) => (
                          <tr key={i} className={`border-b border-stone-800/5 ${i % 2 ? 'bg-stone-500/5' : ''}`}>
                            <td className="px-2 py-1.5 text-stone-800 font-medium">{r.name}</td>
                            <td className="px-2 py-1.5 font-mono font-semibold text-emerald-700">{r.score.toFixed(3)}</td>
                            <td className="px-2 py-1.5 text-stone-500">{r.cell_id || '—'}</td>
                            <td className="px-2 py-1.5 text-stone-500">{r.dose ?? '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </>
                )}
              </div>
            )}
          </div>

          <div className="mt-4">
            <ReportPanel kind="deg" payload={result} />
          </div>
        </>
      )}
    </div>
  );
}
