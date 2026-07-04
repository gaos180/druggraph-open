/**
 * sandboxExports.ts — Exportaciones e informe del Laboratorio Virtual.
 *
 * Funciones puras (sin estado React) que toman el resultado del análisis y/o los
 * datos de rutas/propagación y generan CSV, JSON o un informe HTML imprimible.
 * Cada una conserva su guard interno, así que el call site puede invocarla con un
 * valor potencialmente nulo.
 */
import {
  SandboxAnalysisResponse,
  SandboxPathwaysResponse,
  PropagationResponse,
  FunctionalTerm,
  KeggPathway,
} from '../../api/sandbox';
import { downloadCsv, downloadJson } from '../../utils/download';

// ── Resultado del análisis (similitud combinada) ─────────────────────────────
export function exportResultsCsv(result: SandboxAnalysisResponse | null) {
  if (!result) return;
  const name = result.sandbox.name || 'compuesto';
  downloadCsv(
    `sandbox_${name.replace(/\s+/g, '_')}.csv`,
    ['Rank', 'Nombre', 'DrugBank ID', 'Estructural %', 'Comportamiento %', 'Combinado %', 'Targets compartidos'],
    result.combined.map((r, i) => [
      i + 1,
      r.name,
      r.drugbank_id,
      Math.round(r.structural_score * 100),
      Math.round(r.behavioral_score * 100),
      Math.round(r.combined_score * 100),
      (r.shared_targets ?? []).join('; '),
    ]) as any,
  );
}

export function exportResultsJson(result: SandboxAnalysisResponse | null) {
  if (!result) return;
  const name = result.sandbox.name || 'compuesto';
  downloadJson(`sandbox_${name.replace(/\s+/g, '_')}.json`, result);
}

// ── Informe HTML imprimible ──────────────────────────────────────────────────
export function openSandboxReport(
  result: SandboxAnalysisResponse | null,
  pathwayData: SandboxPathwaysResponse | null,
) {
  if (!result) return;
  const p = result.sandbox.properties;
  const rows = result.combined.map((r, i) => `
      <tr>
        <td>${i + 1}</td>
        <td><strong>${r.name}</strong></td>
        <td style="font-family:monospace">${r.drugbank_id}</td>
        <td>${Math.round(r.structural_score * 100)}%</td>
        <td>${Math.round(r.behavioral_score * 100)}%</td>
        <td><strong>${Math.round(r.combined_score * 100)}%</strong></td>
        <td style="font-size:0.8em">${(r.shared_targets ?? []).slice(0, 5).join(', ')}${(r.shared_targets ?? []).length > 5 ? ' …' : ''}</td>
      </tr>`).join('');

  // Sección opcional de rutas y GO (solo si el usuario cargó el análisis de rutas)
  const termRows = (terms: FunctionalTerm[]) => terms.slice(0, 12).map(t => `
      <tr><td style="font-family:monospace">${t.term}</td><td>${t.description}</td>
      <td style="text-align:right">${t.gene_count}</td>
      <td style="text-align:right;font-family:monospace">${t.fdr < 0.001 ? t.fdr.toExponential(1) : t.fdr.toFixed(4)}</td></tr>`).join('');
  const keggRows = (pw: KeggPathway[]) => pw.slice(0, 15).map(k => `
      <tr><td style="font-family:monospace">${k.pathway_id.replace('path:', '')}</td><td>${k.name}</td>
      <td style="text-align:right">${k.target_count}</td>
      <td style="font-size:0.8em">${k.targets.slice(0, 6).join(', ')}${k.targets.length > 6 ? ' …' : ''}</td></tr>`).join('');
  let pathwaySection = '';
  if (pathwayData) {
    const pd = pathwayData;
    const directN   = pd.string_ppi?.direct_genes?.length ?? pd.targets_used.length;
    const indirectN = pd.string_ppi?.neighbors?.length ?? 0;
    const block = (title: string, headers: string[], body: string) => body
      ? `<h2>${title}</h2><table><thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table>`
      : '';
    pathwaySection = `
<h2>Contexto de red molecular</h2>
<div class="props">
  <div class="prop"><div class="val">${directN}</div><div class="lbl">Proteínas que afecta (directas)</div></div>
  <div class="prop"><div class="val">${indirectN}</div><div class="lbl">Posiblemente afecta (PPI)</div></div>
  <div class="prop"><div class="val">${pd.kegg?.pathway_count ?? pd.kegg?.pathways.length ?? 0}</div><div class="lbl">Rutas KEGG asociadas</div></div>
  <div class="prop"><div class="val">${pd.go_process.length}</div><div class="lbl">Procesos GO enriquecidos</div></div>
</div>
${block('Rutas metabólicas (KEGG)', ['ID', 'Nombre', 'Targets', 'Proteínas'], keggRows(pd.kegg?.pathways ?? []))}
${block('GO — Proceso Biológico', ['GO', 'Descripción', 'Genes', 'FDR'], termRows(pd.go_process))}
${block('GO — Función Molecular', ['GO', 'Descripción', 'Genes', 'FDR'], termRows(pd.go_function))}
${block('Reactome', ['ID', 'Descripción', 'Genes', 'FDR'], termRows(pd.reactome))}
${block('WikiPathways', ['ID', 'Descripción', 'Genes', 'FDR'], termRows(pd.wikipathways ?? []))}`;
  }

  const html = `<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>Reporte Sandbox — ${result.sandbox.name}</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; color: #111; }
  h1 { border-bottom: 2px solid #6366f1; padding-bottom: 8px; }
  h2 { color: #6366f1; margin-top: 28px; }
  table { border-collapse: collapse; width: 100%; margin-top: 12px; font-size: 0.9em; }
  th { background: #6366f1; color: #fff; padding: 8px 10px; text-align: left; }
  td { border: 1px solid #e2e8f0; padding: 7px 10px; }
  tr:nth-child(even) td { background: #f8f9fa; }
  .props { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; margin: 12px 0; }
  .prop { border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; text-align: center; }
  .prop .val { font-size: 1.3em; font-weight: bold; color: #6366f1; }
  .prop .lbl { font-size: 0.75em; color: #666; }
  .smiles { font-family: monospace; background: #f1f5f9; padding: 8px; border-radius: 4px; word-break: break-all; }
  .badge { display:inline-block; background:#ede9fe; color:#6366f1; border-radius:4px; padding:2px 8px; font-size:0.8em; font-weight:bold; }
  @media print { @page { margin: 20mm; } }
</style>
</head>
<body>
<h1>🧫 Reporte de Análisis Sandbox</h1>
<p><strong>Compuesto:</strong> ${result.sandbox.name} &nbsp; <span class="badge">${result.method_used}</span></p>
<p class="smiles">${p.canonical_smiles}</p>

<h2>Propiedades fisicoquímicas</h2>
<div class="props">
  <div class="prop"><div class="val">${p.molecular_weight}</div><div class="lbl">Peso Molecular (Da)</div></div>
  <div class="prop"><div class="val">${p.logp}</div><div class="lbl">LogP</div></div>
  <div class="prop"><div class="val">${p.tpsa}</div><div class="lbl">TPSA (Å²)</div></div>
  <div class="prop"><div class="val">${p.h_bond_donors}</div><div class="lbl">Donadores H</div></div>
  <div class="prop"><div class="val">${p.h_bond_acceptors}</div><div class="lbl">Aceptores H</div></div>
  <div class="prop"><div class="val">${p.rotatable_bonds}</div><div class="lbl">Enl. rotables</div></div>
  <div class="prop"><div class="val">${p.aromatic_rings}</div><div class="lbl">Anillos aromát.</div></div>
  <div class="prop"><div class="val">${p.num_heavy_atoms}</div><div class="lbl">Átomos pesados</div></div>
</div>

<h2>Fármacos más similares (${result.combined.length})</h2>
<table>
  <thead><tr><th>#</th><th>Nombre</th><th>ID</th><th>Estructural</th><th>Comportamiento</th><th>Combinado</th><th>Targets compartidos</th></tr></thead>
  <tbody>${rows}</tbody>
</table>
${pathwaySection}

<p style="color:#888;font-size:0.8em;margin-top:32px">Generado por DrugGraph — ${new Date().toLocaleString('es-ES')}</p>
</body></html>`;
  const win = window.open('', '_blank');
  if (win) { win.document.write(html); win.document.close(); }
}

// ── Rutas / red molecular ─────────────────────────────────────────────────────
export function exportGoProcessCsv(pathwayData: SandboxPathwaysResponse | null) {
  if (!pathwayData) return;
  downloadCsv('go_process.csv',
    ['GO Term', 'Descripción', 'N° genes', 'Genes', 'FDR'],
    pathwayData.go_process.map(t => [t.term, t.description, t.gene_count, t.genes.join('; '), t.fdr]) as any,
  );
}

export function exportKeggCsv(pathwayData: SandboxPathwaysResponse | null) {
  if (!pathwayData?.kegg) return;
  downloadCsv('kegg_pathways.csv',
    ['Pathway ID', 'Nombre', 'N° targets', 'Targets', 'KEGG genes'],
    pathwayData.kegg.pathways.map(p => [
      p.pathway_id, p.name, p.target_count, p.targets.join('; '), p.kegg_genes.join('; ')
    ]) as any,
  );
}

export function exportPpiCsv(pathwayData: SandboxPathwaysResponse | null) {
  if (!pathwayData?.string_ppi) return;
  downloadCsv('string_ppi.csv',
    ['Proteína vecina', 'Score STRING', 'N° conexiones', 'Conectado a'],
    pathwayData.string_ppi.neighbors.map(n => [
      n.partner_protein, Math.round(n.max_score * 1000), n.connection_count, n.connected_to.join('; ')
    ]) as any,
  );
}

export function exportPathwaysJson(pathwayData: SandboxPathwaysResponse | null) {
  if (!pathwayData) return;
  downloadJson('sandbox_pathways.json', pathwayData);
}

// ── CTD (interacciones químico-gen) ───────────────────────────────────────────
export function exportCtdSummaryCsv(pathwayData: SandboxPathwaysResponse | null) {
  const s = pathwayData?.ctd?.summary;
  if (!s) return;
  downloadCsv('ctd_quimicos.csv',
    ['Químico', 'CAS', 'DrugBank ID', 'En DrugGraph', 'Genes diana afectados', 'Interacciones totales', 'Genes'],
    s.top_chemicals.map(c => [
      c.name, c.cas, c.drugbank_id ?? '', c.in_druggraph ? 'sí' : 'no',
      c.gene_count, c.total_count, c.genes.join('; '),
    ]) as any,
  );
}

export function exportCtdGenesCsv(pathwayData: SandboxPathwaysResponse | null) {
  const genes = pathwayData?.ctd?.genes;
  if (!genes) return;
  downloadCsv('ctd_genes.csv',
    ['Gen', 'Gene ID', 'N° químicos', 'N° interacciones', 'Acciones (top)', 'Top químicos'],
    genes.map(g => [
      g.gene, g.gene_id ?? '', g.chemical_count, g.interaction_count,
      g.actions.map(a => `${a.action}:${a.count}`).join(' | '),
      g.top_chemicals.map(c => c.name).join('; '),
    ]) as any,
  );
}

export function exportCtdJson(pathwayData: SandboxPathwaysResponse | null) {
  if (!pathwayData?.ctd) return;
  downloadJson('ctd_interactions.json', pathwayData.ctd);
}

// ── Cascada de propagación ────────────────────────────────────────────────────
export function exportPropCsv(propData: PropagationResponse | null) {
  if (!propData) return;
  if (propData.mode === 'directed') {
    downloadCsv('cascada_dirigida.csv',
      ['Rank', 'Gen', 'Sentido', 'Efecto', 'Magnitud', 'Es target DrugGraph'],
      propData.downstream.map((d, i) => [
        i + 1, d.gene, (d.sign ?? 0) > 0 ? 'activado' : 'inhibido', d.effect ?? '', d.magnitude ?? '', d.is_target ? 'sí' : 'no',
      ]) as any,
    );
  } else {
    downloadCsv('cascada_difusion.csv',
      ['Rank', 'Gen', 'Score propagación', 'Es target DrugGraph'],
      propData.downstream.map((d, i) => [i + 1, d.gene, d.score ?? '', d.is_target ? 'sí' : 'no']) as any,
    );
  }
}
