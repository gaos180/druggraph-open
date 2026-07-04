import api from './client';

export interface TargetRecord {
  id: string;
  name: string;
  gene_name: string;
  uniprot_id: string;
  organism: string;
  cellular_location: string;
  chromosome_location: string;
  known_action: string;
  drug_count: number;
}

export interface TargetDrugRef {
  drugbank_id: string;
  drug_name: string;
  rel_type: string;
}

export interface TargetDetail extends TargetRecord {
  drugs: TargetDrugRef[];
}

export interface TargetsListResponse {
  page: number;
  per_page: number;
  total: number;
  has_next: boolean;
  has_prev: boolean;
  results: TargetRecord[];
}

export interface UniProtSubLoc {
  value: string;
  topology: string;
  icon: string;
  sl_id: string;
}

export interface UniProtGoTerm {
  id: string;
  term: string;
  aspect: string;  // P, F, C
}

export interface UniProtDetails {
  accession: string;
  protein_name: string;
  alternative_names: string[];
  gene_names: string[];
  organism: { scientific: string; taxon_id: number };
  function: string;
  activity_regulation: string;
  subunit: string;
  ptm: string;
  subcellular_locations: UniProtSubLoc[];
  sequence: { length: number; mass: number; checksum: string; first_50: string };
  keywords: string[];
  go_terms: UniProtGoTerm[];
  pdb_ids: string[];
  reviewed: boolean;
}

export interface DrugByTargetResult {
  drugbank_id: string;
  name: string;
  targets_matched: Array<{
    target_name: string;
    gene_name: string;
    uniprot_id: string;
    rel_type: string;
  }>;
}

export interface TargetPathwaysKegg {
  pathway_id: string;
  name: string;
  target_count: number;
  targets: string[];
  kegg_genes: string[];
}

export interface TargetPathwaysStringNeighbor {
  partner_protein: string;
  max_score: number;
  connected_to: string[];
  connection_count: number;
}

export interface TargetPathwaysResponse {
  target: { name: string; gene_name: string; uniprot_id: string; organism: string };
  pathways: {
    pathways: TargetPathwaysKegg[];
    unmapped_targets: string[];
    pathway_count: number;
  } | null;
  indirect: {
    direct_genes: string[];
    neighbors: TargetPathwaysStringNeighbor[];
    edges: { source: string; target: string; score: number }[];
    network_image_url: string;
  } | null;
  notes: string[];
}

export interface TargetAdminUpdate {
  name?: string;
  gene_name?: string;
  organism?: string;
  cellular_location?: string;
  known_action?: string;
}

export interface TargetCreateParams {
  name: string;
  drugbank_target_id: string;
  gene_name?: string;
  organism?: string;
  uniprot_id?: string;
  cellular_location?: string;
  known_action?: string;
}

export const targetsApi = {
  list: (params?: { search?: string; organism?: string; page?: number; per_page?: number }) =>
    api.get<TargetsListResponse>('/drugs/targets/', { params }),

  detail: (targetId: string) =>
    api.get<TargetDetail>(`/drugs/targets/${targetId}/`),

  adminCreate: (data: TargetCreateParams) => api.post('/drugs/targets/', data),

  adminUpdate: (id: string, data: TargetAdminUpdate) =>
    api.patch(`/drugs/targets/${id}/`, data),

  adminDelete: (id: string) => api.delete(`/drugs/targets/${id}/`),

  uniprot: (targetId: string) =>
    api.get<UniProtDetails>(`/drugs/targets/${targetId}/uniprot/`),

  pathways: (targetId: string, params?: { score?: number }) =>
    api.get<TargetPathwaysResponse>(`/drugs/targets/${targetId}/pathways/`, { params }),

  keggGene: (gene: string) =>
    api.get<{ gene: string; kegg_id: string; pathways: { pathway_id: string; name: string }[] }>(
      '/drugs/targets/kegg-gene/', { params: { gene } }
    ),

  byGene: (q: string) =>
    api.get<{ query: string; total: number; results: DrugByTargetResult[] }>(
      '/drugs/targets/by-gene/', { params: { q } }
    ),

  graph: (targetId: string) =>
    api.get<TargetGraphResponse>(`/drugs/targets/${targetId}/graph/`),

  compare: (a: string, b: string) =>
    api.get<TargetCompareResponse>('/drugs/targets/compare/', { params: { a, b } }),
};

export interface TargetGraphResponse {
  nodes: { data: { id: string; label: string; kind: 'drug' | 'target' } }[];
  edges: { data: { source: string; target: string; label: string } }[];
}

export interface TargetCompareResponse {
  common_drugs:  TargetDrugRef[];
  only_a_drugs:  TargetDrugRef[];
  only_b_drugs:  TargetDrugRef[];
  stats: {
    count_a: number;
    count_b: number;
    count_common: number;
    jaccard_similarity: number;
  };
}
