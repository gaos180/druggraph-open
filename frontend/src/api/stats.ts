import api from './client';

export interface StatBar { label: string; count: number }

export interface MongoStats {
  total_drugs:        number;
  total_ddi_mentions: number;
  by_type:            StatBar[];
  by_group:           StatBar[];
}

export interface RelType  { label: string; count: number }
export interface TopDrug  { name: string; id: string; targets: number }

export interface Neo4jStats {
  drugs:      number;
  targets:    number;
  categories: number;
  rel_types:  RelType[];
  top_drugs:  TopDrug[];
  error?:     string;
}

export interface StatsResult {
  mongo:  MongoStats;
  neo4j:  Neo4jStats;
}

export interface DdiInteraction {
  drugbank_id: string;
  name:        string;
  description: string | null;
}

export interface DdiPairResult {
  mode:        'pair';
  drug_a:      { drugbank_id: string; name: string };
  drug_b:      { drugbank_id: string; name: string };
  interacts:   boolean;
  description: string | null;
}

export interface DdiSingleResult {
  mode:              'single';
  drug:              { drugbank_id: string; name: string };
  interaction_count: number;
  interactions:      DdiInteraction[];
}

export interface PublicStats {
  total_drugs:   number;
  total_targets: number;
}

export const statsApi = {
  getStats: () => api.get<StatsResult>('/drugs/stats/'),

  getPublicStats: () => api.get<PublicStats>('/drugs/stats/public/'),

  checkDdi: (drugA: string, drugB?: string) => {
    const params = drugB
      ? `drug_a=${drugA}&drug_b=${drugB}`
      : `drug_a=${drugA}`;
    return api.get<DdiPairResult | DdiSingleResult>(`/drugs/ddi/?${params}`);
  },

  ddiRisk: (drugA: string, drugB: string) =>
    api.get<DdiRiskResult>(`/drugs/ddi/risk/?drug_a=${drugA}&drug_b=${drugB}`),
};

export interface DdiRiskSignal {
  type:    'PK' | 'PD';
  level:   'high' | 'medium' | 'low';
  gene:    string | null;
  message: string;
}

export interface DdiRiskResult {
  drug_a:         { name: string; drugbank_id: string };
  drug_b:         { name: string; drugbank_id: string };
  risk_score:     number;
  risk_level:     'sin_señales' | 'bajo' | 'moderado' | 'alto';
  shared_cyps:    string[];
  shared_targets: string[];
  jaccard:        number;
  proximity:      { d_c_symmetric?: number | null; available: boolean; reason?: string } | null;
  signals:        DdiRiskSignal[];
  disclaimer:     string;
}
