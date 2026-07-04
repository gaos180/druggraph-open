import api from './client';

export interface DrugSummary {
  _id: string;
  name: string;
  type?: string;
  groups?: string[];
  description?: string;
  'drugbank-id'?: string;
  'average-mass'?: number;
  unii?: string;
}

// Interfaz extendida con TODOS los campos que exige DrugDetailPage
export interface DrugDetail extends DrugSummary {
  indication?: string;
  pharmacodynamics?: string;
  toxicity?: string;
  'mechanism-of-action'?: string;
  biotransformation?: string;
  absorption?: string;

  // Mapeamos ambas variantes (con guion bajo y guion medio) para evitar conflictos en la UI
  half_life?: string;
  'half-life'?: string;

  protein_binding?: string;
  'protein-binding'?: string;

  volume_of_distribution?: string;
  'volume-of-distribution'?: string;

  route_of_elimination?: string;
  'route-of-elimination'?: string;

  metabolism?: string;
  smiles?: string | null;
  category_names?: string[];
  synonyms?: string[];

  // Propiedades complejas y arrays anidados tipados de forma flexible
  'atc-codes'?: any[];
  targets?: any[];
  'drug-interactions'?: any[];
  'food-interactions'?: any[];
  'calculated-properties'?: any[];
}

export interface DrugsResponse {
  page: number;
  per_page: number;
  has_next: boolean;
  has_prev: boolean;
  results: DrugSummary[];
}

export interface FiltersResponse {
  types: string[];
  groups: string[];
}

// ── Interfaces Neo4j Graph ────────────────────────────────────────────────────

/** Nodo Target tal como lo devuelve Neo4j */
export interface GraphTarget {
  drugbank_target_id: string;
  uniprot_id: string;
  name: string;
  organism: string;
}

/** Una interacción Drug→Target con su tipo de relación semántica */
export interface GraphInteraction {
  /** Tipo de relación Cypher: "TARGETS" | "INHIBITS" | "ACTIVATES" | "METABOLIZED_BY" | etc. */
  rel_type: string;
  /** Rol estructural del XML: "targets" | "enzymes" | "carriers" | "transporters" */
  role: string;
  /** "yes" | "no" | "unknown" */
  known_action: string;
  /** Acciones farmacológicas: ["inhibitor", "substrate", ...] */
  actions: string[];
  target: GraphTarget;
}

/** Categoría farmacológica (nodo :Category) */
export interface GraphCategory {
  name: string;
  mesh_id: string;
}

/** Interacción drug-drug (nodo :Drug adyacente) */
export interface GraphDrugInteraction {
  drugbank_id: string;
  name: string;
  description: string;
}

/** Estadísticas de la red del fármaco */
export interface GraphStats {
  total_interactions: number;
  total_categories: number;
  total_ddi: number;
  /** Conteo de relaciones por tipo: { "TARGETS": 3, "INHIBITS": 5, ... } */
  rel_type_counts: Record<string, number>;
}

/** Nodo Drug tal como lo retorna Neo4j */
export interface GraphDrugNode {
  drugbank_id: string;
  name: string;
  type: string;
  groups: string[];
}

/** Respuesta completa del endpoint /api/drugs/<id>/graph/ */
export interface DrugGraphResponse {
  drug: GraphDrugNode;
  interactions: GraphInteraction[];
  categories: GraphCategory[];
  drug_interactions: GraphDrugInteraction[];
  stats: GraphStats;
}

// ── API calls ─────────────────────────────────────────────────────────────────

export interface DrugAdminUpdate {
  name?: string;
  type?: string;
  groups?: string[];
  description?: string;
}

export interface DrugCreateParams {
  name: string;
  drugbank_id: string;
  type?: string;
  groups?: string[];
  description?: string;
}

export const drugsApi = {
  list: (params: {
    search?: string;
    drug_type?: string;
    group?: string;
    page?: number;
  }) => api.get<DrugsResponse>('/drugs/', { params }),

  detail: (id: string) => api.get<DrugDetail>(`/drugs/${id}/`),

  filters: () => api.get<FiltersResponse>('/drugs/filters/'),

  graph: (drugId: string, name?: string) =>
    api.get<DrugGraphResponse>(`/drugs/${drugId}/graph/`, {
      params: name ? { name } : undefined,
    }),

  adminCreate: (data: DrugCreateParams) => api.post('/drugs/', data),

  adminUpdate: (id: string, data: DrugAdminUpdate) =>
    api.patch(`/drugs/${id}/`, data),

  adminDelete: (id: string) => api.delete(`/drugs/${id}/`),
};
