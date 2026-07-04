import api from './client';

// ── Propiedades fisicoquímicas calculadas por RDKit ───────────────────────────

export interface SandboxProperties {
  canonical_smiles: string;
  molecular_weight: number;
  logp: number;
  h_bond_donors: number;
  h_bond_acceptors: number;
  tpsa: number;
  rotatable_bonds: number;
  aromatic_rings: number;
  num_heavy_atoms: number;
}

// ── Metadata del compuesto sandbox creado ──────────────────────────────────────

export interface SandboxDrugMeta {
  session_id: string;
  sandbox_id: string;
  name: string;
  smiles: string;
  properties: SandboxProperties;
  linked_targets: string[];
  expires_at: number;
}

// ── Resultados de similitud ───────────────────────────────────────────────────

export interface StructuralSimilarityResult {
  drugbank_id: string;
  name: string;
  /** Score de Tanimoto (0–1) */
  score: number;
}

export interface BehavioralSimilarityResult {
  drugbank_id: string;
  name: string;
  /** Score Jaccard / nodeSimilarity (0–1) */
  score: number;
  shared_target_count?: number;
  shared_targets?: string[];
}

export interface CombinedSimilarityResult {
  drugbank_id: string;
  name: string;
  structural_score: number;
  behavioral_score: number;
  combined_score: number;
  shared_targets?: string[];
}

export type SimilarityMethod = 'gds' | 'jaccard' | 'jaccard_inferred' | 'structural_only' | 'none';

export interface SandboxAnalysisResponse {
  sandbox: SandboxDrugMeta;
  structural_similarity: StructuralSimilarityResult[];
  behavioral_similarity: BehavioralSimilarityResult[];
  combined: CombinedSimilarityResult[];
  method_used: SimilarityMethod;
  targets_inferred?: boolean;
}

// ── Autocompletado de targets candidatos ──────────────────────────────────────

export interface TargetSearchResult {
  drugbank_target_id: string;
  uniprot_id: string;
  gene_name?: string;
  name: string;
  organism: string;
}

export interface TargetSearchResponse {
  results: TargetSearchResult[];
}

// ── SwissTargetPrediction ─────────────────────────────────────────────────────

export interface SwissTargetResult {
  uniprot_id: string;
  gene_name: string;
  target_name: string;
  probability: number;
  target_class: string;
  chembl_id: string;
  known_actives: number;
  /** Disponible solo si in_druggraph=true */
  drugbank_target_id: string | null;
  db_name: string | null;
  db_organism: string | null;
  in_druggraph: boolean;
}

export interface SwissTargetsResponse {
  total: number;
  matched: number;
  organisms: string[];
  results: SwissTargetResult[];
}

// ── Rutas, GO y PPI ───────────────────────────────────────────────────────────

export interface FunctionalTerm {
  term: string;
  description: string;
  gene_count: number;
  genes: string[];
  fdr: number;
}

export interface KeggPathway {
  pathway_id: string;
  name: string;
  target_count: number;
  targets: string[];
  kegg_genes: string[];
}

export interface StringNeighbor {
  partner_protein: string;
  partner_string_id: string;
  max_score: number;
  connected_to: string[];
  connection_count: number;
}

// ── CTD: interacciones químico-gen ──────────────────────────────────────────────

export interface CtdAction {
  action: string;
  count: number;
}

export interface CtdChemical {
  name: string;
  mesh_id?: string;
  cas?: string;
  count: number;
  in_druggraph: boolean;
  drugbank_id: string | null;
}

export interface CtdGene {
  gene: string;
  gene_id: number | null;
  interaction_count: number;
  chemical_count: number;
  actions: CtdAction[];
  top_chemicals: CtdChemical[];
}

export interface CtdSummaryChemical {
  name: string;
  cas: string;
  drugbank_id: string | null;
  in_druggraph: boolean;
  gene_count: number;
  total_count: number;
  genes: string[];
}

export interface CtdData {
  available: boolean;
  genes: CtdGene[];
  summary: {
    genes_with_data: number;
    total_interactions: number;
    top_chemicals: CtdSummaryChemical[];
  } | null;
}

// ── Propagación (efecto en cadena sobre la red PPI de STRING) ────────────────────

export interface PropagationGene {
  gene: string;
  is_target: boolean;
  /** modo difusión (STRING) */
  score?: number;
  /** modo dirigido (KEGG): efecto con signo, magnitud y sentido (+1 activado / -1 inhibido) */
  effect?: number;
  magnitude?: number;
  sign?: 1 | -1;
}

export interface PropagationResponse {
  available: boolean;
  mode?: 'diffusion' | 'directed';
  seeds_used: string[];
  seeds_missing: string[];
  damping?: number;
  seed_sign?: number;
  max_hops?: number;
  downstream: PropagationGene[];
  seed_scores?: PropagationGene[];
  /** modo dirigido: aristas reguladoras del subgrafo (signo +1/-1) */
  edges?: { source: string; target: string; sign: 1 | -1 }[];
  reason?: string;
}

export interface SandboxPathwaysResponse {
  targets_used: { drugbank_target_id: string; gene_name: string; uniprot_id: string; name: string }[];
  kegg: { pathways: KeggPathway[]; unmapped_targets: string[]; pathway_count: number } | null;
  string_ppi: { direct_genes: string[]; neighbors: StringNeighbor[]; edges: any[] } | null;
  go_process: FunctionalTerm[];
  go_function: FunctionalTerm[];
  go_component: FunctionalTerm[];
  string_kegg: FunctionalTerm[];
  reactome: FunctionalTerm[];
  wikipathways: FunctionalTerm[];
  ctd: CtdData | null;
  notes: string[];
}

// ── API calls ──────────────────────────────────────────────────────────────────

export interface AnalyzeSandboxParams {
  smiles: string;
  name?: string;
  target_ids?: string[];
  session_id?: string;
  /** Si true, el nodo no se borra al finalizar (queda sujeto a TTL de 30 min) */
  persist?: boolean;
}

export const sandboxApi = {
  /**
   * Analiza un compuesto: crea un nodo temporal en Neo4j, calcula similitud
   * estructural (Tanimoto) y de comportamiento (targets compartidos) contra
   * fármacos reales, y limpia el nodo al finalizar (salvo persist=true).
   */
  analyze: (params: AnalyzeSandboxParams) =>
    api.post<SandboxAnalysisResponse>('/drugs/sandbox/analyze/', params),

  /**
   * Autocompletado de targets reales por nombre / gen / UniProt ID /
   * drugbank_target_id, para que el usuario seleccione "targets candidatos".
   * Requiere al menos 2 caracteres.
   */
  searchTargets: (search: string) =>
    api.get<TargetSearchResponse>('/drugs/sandbox/targets/', { params: { search } }),

  /** Elimina manualmente un sandbox persistido antes de su expiración. */
  cleanup: (sandboxId: string) =>
    api.delete<{ deleted: number }>(`/drugs/sandbox/${sandboxId}/`),

  /**
   * Importa predicciones de SwissTargetPrediction desde CSV exportado.
   * Devuelve los targets cruzados con Neo4j (drugbank_target_id).
   */
  importSwissCsv: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return api.post<SwissTargetsResponse>('/drugs/sandbox/swiss-targets/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  /**
   * Llama a la API de SwissTargetPrediction en tiempo real con un SMILES.
   */
  predictSwiss: (smiles: string, organism = 'Homo sapiens') =>
    api.get<SwissTargetsResponse>('/drugs/sandbox/swiss-targets/', {
      params: { smiles, organism },
    }),

  /**
   * Calcula KEGG, GO y STRING PPI para un conjunto de targets y/o fármacos.
   * Se puede invocar después del análisis sandbox para enriquecer los resultados.
   */
  getPathways: (body: { target_ids?: string[]; drug_ids?: string[] }) =>
    api.post<SandboxPathwaysResponse>('/drugs/sandbox/pathways/', body),

  /**
   * Propaga el efecto del compuesto por la red PPI local de STRING
   * (Personalized PageRank) y devuelve los genes más alcanzados (efecto en cadena).
   */
  getPropagation: (body: {
    genes?: string[]; target_ids?: string[]; drug_ids?: string[]; top_n?: number;
    mode?: 'diffusion' | 'directed'; seed_sign?: number; max_hops?: number;
  }) => api.post<PropagationResponse>('/drugs/sandbox/propagation/', body),

  /**
   * Desglose de similitud multi-fingerprint (Morgan/MACCS/atom-pair/farmacóforo)
   * entre el compuesto sandbox y un fármaco de la base. Cálculo bajo demanda.
   */
  similarityDetail: (body: { smiles: string; drugbank_id?: string; smiles_b?: string }) =>
    api.post<SimilarityDetailResponse>('/drugs/sandbox/similarity-detail/', body),

  /**
   * Similitud molecular aprendida (embeddings ChemBERTa) por vecino más cercano
   * (índice vectorial de Neo4j). Complementa Tanimoto/fingerprints.
   */
  embeddingSimilarity: (smiles: string, topN = 20) =>
    api.post<EmbeddingSimilarityResponse>('/drugs/sandbox/embedding-similarity/', { smiles, top_n: topN }),
};

export interface EmbeddingSimilarityResponse {
  available: boolean;
  method?:   string;
  results?:  { drugbank_id: string; name: string; score: number }[];
  error?:    string;
}

export interface SimilarityDetailResponse {
  available:       boolean;
  drugbank_id:     string | null;
  name:            string | null;
  per_fingerprint: { morgan?: number | null; maccs?: number | null; atompair?: number | null; pharmacophore?: number | null };
  consensus_score: number;
  notes?:          string[];
}
