/**
 * sandboxGraphs.ts — constructores de grafos Cytoscape para el Sandbox.
 * Transforman la respuesta de rutas en nodos/aristas listos para CytoscapeGraph.
 */
import { CyNode, CyEdge } from '../../components/CytoscapeGraph';
import { SandboxPathwaysResponse } from '../../api/sandbox';

export const MAX_GRAPH_NEIGHBORS = 25;
export const MAX_GRAPH_PATHWAYS = 15;

/**
 * Grafo de "efecto molecular": el compuesto en el centro, conectado a sus
 * targets directos (lo que AFECTA) y, vía aristas punteadas, a los vecinos PPI
 * de STRING (lo que POSIBLEMENTE AFECTA de forma indirecta).
 */
export function buildEffectGraph(
  compoundName: string,
  pw: SandboxPathwaysResponse,
): { nodes: CyNode[]; edges: CyEdge[] } {
  const nodes: CyNode[] = [];
  const edges: CyEdge[] = [];
  const seen = new Set<string>();

  const SANDBOX = '__sandbox__';
  nodes.push({ id: SANDBOX, label: compoundName || 'Compuesto', kind: 'sandbox', weight: 4.5 });
  seen.add(SANDBOX);

  // Genes diana directos
  const directGenes =
    (pw.string_ppi?.direct_genes && pw.string_ppi.direct_genes.length > 0)
      ? pw.string_ppi.direct_genes
      : pw.targets_used.map(t => t.gene_name || t.uniprot_id).filter(Boolean);

  directGenes.forEach((g) => {
    if (!g || seen.has(g)) return;
    seen.add(g);
    const meta = pw.targets_used.find(t => (t.gene_name || t.uniprot_id) === g);
    nodes.push({
      id: g, label: g, kind: 'target', weight: 2.6,
      meta: meta ? { uniprot: meta.uniprot_id, drugbank_target_id: meta.drugbank_target_id, name: meta.name } : undefined,
    });
    edges.push({ id: `s-${g}`, source: SANDBOX, target: g, style: 'solid' });
  });

  // Vecinos PPI (efecto indirecto = "posiblemente afecta")
  (pw.string_ppi?.neighbors ?? []).slice(0, MAX_GRAPH_NEIGHBORS).forEach((n) => {
    if (!seen.has(n.partner_protein)) {
      seen.add(n.partner_protein);
      nodes.push({ id: n.partner_protein, label: n.partner_protein, kind: 'predicted', weight: 1 + n.max_score });
    }
    n.connected_to.forEach((src) => {
      if (seen.has(src)) {
        edges.push({ id: `${src}-${n.partner_protein}`, source: src, target: n.partner_protein, style: 'dashed' });
      }
    });
  });

  return { nodes, edges };
}

/**
 * Grafo de "contextualización de rutas": cada ruta KEGG es un nodo (categoría)
 * conectado a los genes diana que participan en ella. Permite ver en qué
 * procesos biológicos se concentra el efecto del compuesto.
 */
export function buildPathwayGraph(
  pw: SandboxPathwaysResponse,
): { nodes: CyNode[]; edges: CyEdge[] } {
  const nodes: CyNode[] = [];
  const edges: CyEdge[] = [];
  const seen = new Set<string>();

  const pathways = (pw.kegg?.pathways ?? []).slice(0, MAX_GRAPH_PATHWAYS);
  pathways.forEach((p) => {
    const pid = `pw:${p.pathway_id}`;
    if (!seen.has(pid)) {
      seen.add(pid);
      nodes.push({
        id: pid,
        label: p.name.replace(/ - Homo sapiens.*$/i, ''),
        kind: 'category',
        weight: 1.5 + Math.min(5, p.target_count),
        meta: { pathway_id: p.pathway_id.replace('path:', '') },
      });
    }
    p.targets.forEach((g) => {
      if (!g) return;
      if (!seen.has(g)) {
        seen.add(g);
        nodes.push({ id: g, label: g, kind: 'target', weight: 2 });
      }
      edges.push({ id: `${g}-${pid}`, source: g, target: pid, style: 'solid' });
    });
  });

  return { nodes, edges };
}
