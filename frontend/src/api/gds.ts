import api from './client';

// ── Centralidad ────────────────────────────────────────────────────────────

export interface CentralityNode {
  id: string;
  name: string;
  score: number;
  // Solo para targets:
  uniprot_id?: string;
  organism?: string;
  // Solo para fármacos:
  type?: string;
}

export interface CentralityResponse {
  node_label: 'Target' | 'Drug';
  metric: 'pagerank' | 'degree';
  results: CentralityNode[];
}

// ── Comunidades ──────────────────────────────────────────────────────────────

export interface CommunityMember {
  kind: 'Drug' | 'Target';
  id: string;
  name: string;
}

export interface Community {
  community_id: number;
  size: number;
  drug_count: number;
  target_count: number;
  members: CommunityMember[];
}

export interface CommunitiesResponse {
  community_count: number;
  communities: Community[];
}

// ── Predicción de enlaces (por fármaco) ────────────────────────────────────────

export interface LinkPrediction {
  target_id: string;
  target_name: string;
  uniprot_id: string;
  organism: string;
  score: number;
  shared_via_drugs: number;
}

export interface LinkPredictionResponse {
  drugbank_id: string;
  drug_name: string;
  method: string;
  current_target_count: number;
  predictions: LinkPrediction[];
}

// ── Predicción global ──────────────────────────────────────────────────────────

export interface GlobalLinkPrediction {
  drugbank_id: string;
  drug_name: string;
  target_id: string;
  target_name: string;
  organism: string;
  score: number;
}

export interface GlobalLinkPredictionResponse {
  method: string;
  predictions: GlobalLinkPrediction[];
}

// ── API ────────────────────────────────────────────────────────────────────────

export const gdsApi = {
  centrality: (params: {
    node?: 'Target' | 'Drug';
    metric?: 'pagerank' | 'degree';
    top_n?: number;
  }) => api.get<CentralityResponse>('/drugs/gds/centrality/', { params }),

  communities: (params: { max?: number; min_size?: number; members?: number }) =>
    api.get<CommunitiesResponse>('/drugs/gds/communities/', { params }),

  predictForDrug: (drugId: string, params?: { top_n?: number; method?: string }) =>
    api.get<LinkPredictionResponse>(`/drugs/gds/predict/${drugId}/`, { params }),

  predictGlobal: (params?: { top_n?: number }) =>
    api.get<GlobalLinkPredictionResponse>('/drugs/gds/predict-global/', { params }),
};
