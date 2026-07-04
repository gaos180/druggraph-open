import api from './client';

// ── Target directo ─────────────────────────────────────────────────────────────

export interface DirectTarget {
  drugbank_target_id: string;
  uniprot_id: string;
  name: string;
  gene_name: string;
  organism: string;
  rel_types: string[];
}

// ── Efecto indirecto (STRING) ──────────────────────────────────────────────────

export interface StringNeighbor {
  partner_protein: string;
  partner_string_id: string;
  max_score: number;
  connected_to: string[];
  connection_count: number;
}

export interface StringEdge {
  source: string;
  target: string;
  score: number;
}

export interface IndirectEffect {
  direct_genes: string[];
  neighbors: StringNeighbor[];
  edges: StringEdge[];
  network_image_url: string;
}

// ── Rutas (KEGG) ────────────────────────────────────────────────────────────────

export interface KeggPathway {
  pathway_id: string;
  name: string;
  target_count: number;
  targets: string[];
  kegg_genes: string[];
}

export interface PathwaysResult {
  pathways: KeggPathway[];
  unmapped_targets: string[];
  pathway_count: number;
}

// ── Respuesta combinada ─────────────────────────────────────────────────────────

export interface DrugPathwaysResponse {
  drug: { drugbank_id: string; name: string };
  direct_targets: DirectTarget[];
  indirect: IndirectEffect | null;
  pathways: PathwaysResult | null;
  notes: string[];
}

export interface PathwaysParams {
  /** "string", "kegg" o "string,kegg" */
  include?: string;
  /** NCBI taxon id (default 9606 humano) */
  species?: number;
  /** required_score STRING 0–1000 (default 400) */
  score?: number;
}

export const pathwaysApi = {
  /**
   * Obtiene el efecto directo (targets), indirecto (STRING PPI) y las rutas
   * biológicas (KEGG) de un fármaco.
   */
  forDrug: (drugId: string, params?: PathwaysParams) =>
    api.get<DrugPathwaysResponse>(`/drugs/${drugId}/pathways/`, { params }),
};
