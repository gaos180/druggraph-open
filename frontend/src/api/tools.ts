import api from './client';

export interface DegGene {
  symbol:  string;
  log2fc?: number;
  pvalue?: number;
  padj?:   number;
}

export interface DegAnalysisRequest {
  drug_id:              string;
  genes:                DegGene[];
  fc_threshold?:        number;
  pval_threshold?:      number;
  use_fdr?:             boolean;
  organism?:            string;
  go_sources?:          string[];
  significance_method?: string;
}

export interface ProcessedGene {
  symbol:    string;
  log2fc:    number;
  pvalue:    number;
  padj:      number;
  sig_value: number;
  is_sig:    boolean;
  direction: 'up' | 'down' | 'none';
  is_target: boolean;
  target_id:  string;
  gene_name:  string;
  uniprot_id: string;
  rel_type:   string;
}

export interface DegStats {
  total_input:      number;
  significant:      number;
  up:               number;
  down:             number;
  drug_targets:     number;
  overlap:          number;
  overlap_up:       number;
  overlap_down:     number;
  has_quantitative: boolean;
}

export interface GoTerm {
  source:            string;
  term_id:           string;
  term_name:         string;
  p_value:           number;
  fdr:               number;
  intersection_size: number;
  term_size:         number;
  query_size:        number;
  genes:             string[];
}

export interface DrugTarget {
  target_id:  string;
  name:       string;
  gene_name:  string;
  uniprot_id: string;
  rel_type:   string;
}

export interface DegAnalysisResult {
  drug:         { name: string; drugbank_id: string };
  stats:        DegStats;
  genes:        ProcessedGene[];
  drug_targets: DrugTarget[];
  overlap:      ProcessedGene[];
  go_enrichment: GoTerm[];
  notes:        string[];
}

export interface RepurposingCandidate {
  drugbank_id:  string;
  name:         string;
  jaccard:      number;
  shared_count: number;
  shared_genes: string[];
  targets_a:    number;
  targets_b:    number;
}

export interface RepurposingResult {
  drug:       { name: string; drugbank_id: string };
  targets:    DrugTarget[];
  candidates: RepurposingCandidate[];
  go_profile: GoTerm[];
}

// ── Toxicity ──────────────────────────────────────────────────────────────────

export interface ToxAlert {
  level:       'high' | 'medium' | 'low';
  icon:        string;
  category:    string;
  gene_name:   string;
  target_name: string;
  uniprot_id:  string;
  rel_type:    string;
  message:     string;
}

export interface CypInteraction {
  gene:     string;
  rel_type: string;
  level:    'high' | 'medium' | 'low';
  note:     string;
}

export interface PredictedOfftarget {
  target_id:            string;
  target_name:          string;
  gene_name:            string;
  uniprot_id:           string;
  organism:             string;
  score:                number;
  shared_via:           number;
  is_antitarget:        boolean;
  antitarget_level:     string | null;
  antitarget_category:  string | null;
  antitarget_message:   string | null;
}

export interface ClusterPeer {
  drugbank_id:  string;
  name:         string;
  jaccard:      number;
  shared_count: number;
}

export interface ToxicityResult {
  drug:          { name: string; drugbank_id: string };
  risk_score:    number;
  risk_level:    'sin_datos' | 'bajo' | 'moderado' | 'alto' | 'muy_alto';
  alert_counts:  { high: number; medium: number; low: number };
  alerts:        ToxAlert[];
  cyp_interactions:       CypInteraction[];
  predicted_offtargets:   PredictedOfftarget[];
  structural_cluster:     ClusterPeer[];
  target_count:  number;
}

export interface ProximityResult {
  drug_a:         { name: string; drugbank_id: string };
  drug_b:         { name: string; drugbank_id: string };
  genes_a:        string[];
  genes_b:        string[];
  available:      boolean;
  d_c:            number | null;
  d_c_symmetric:  number | null;
  genes_a_used:   string[];
  genes_b_used:   string[];
  reachable_a:    number;
  coverage_a:     number;
  per_source:     { gene: string; distance: number | null }[];
}

export const toolsApi = {
  degAnalysis: (body: DegAnalysisRequest) =>
    api.post<DegAnalysisResult>('/tools/deg-analysis/', body),

  repurposing: (drugId: string) =>
    api.get<RepurposingResult>(`/tools/repurposing/${drugId}/`),

  toxicity: (drugId: string) =>
    api.get<ToxicityResult>(`/tools/toxicity/${drugId}/`),

  proximity: (drugA: string, drugB: string) =>
    api.get<ProximityResult>('/tools/proximity/', { params: { drug_a: drugA, drug_b: drugB } }),

  diseaseEvidence: (drugId: string) =>
    api.get<DiseaseEvidenceResult>(`/tools/disease-evidence/${drugId}/`),

  signatureReversion: (body: { up_genes: string[]; dn_genes: string[]; reverse?: boolean }) =>
    api.post<SignatureReversionResult>('/tools/signature-reversion/', body),

  chemicalSpace: () =>
    api.get<ChemicalSpaceResult>('/tools/chemical-space/'),

  locateInSpace: (smiles: string) =>
    api.post<ChemicalSpaceLocateResult>('/tools/chemical-space/locate/', { smiles }),

  denovo: (body: DeNovoRequest) =>
    api.post<DeNovoResult>('/tools/denovo/', body),

  admet: (body: { smiles?: string; drug_id?: string }) =>
    api.post<AdmetResult>('/tools/admet/', body),

  dtiGnn: (drugId: string) =>
    api.get<DtiGnnResult>(`/tools/dti-gnn/${drugId}/`),

  chempropTox: (body: { smiles?: string; drug_id?: string }) =>
    api.post<ChempropToxResult>('/tools/chemprop-tox/', body),

  diseaseGnn: (drugId: string, topN = 20) =>
    api.get<DiseaseGnnResult>(`/tools/disease-gnn/${drugId}/?top_n=${topN}`),

  pharmacophore: (body: { smiles?: string; drug_id?: string; min_fraction?: number }) =>
    api.post<PharmacophoreResult>('/tools/pharmacophore/', body),

  dockingTargets: () =>
    api.get<{ available: boolean; targets: DockingTarget[] }>('/tools/docking/targets/'),
  docking: (body: { smiles?: string; drug_id?: string; target: string; exhaustiveness?: number }) =>
    api.post<DockingResult>('/tools/docking/', body),
};

// ── Docking estructural con AutoDock Vina (Tier 5.3) ──────────────────────────────

export interface DockingTarget {
  target: string; name: string; pdb_id?: string;
  center?: number[]; box_size?: number[];
}

export interface DockingResult {
  available:          boolean;
  engine?:            string;
  target?:            string;
  target_name?:       string;
  pdb_id?:            string;
  drug_id?:           string;
  smiles?:            string;
  affinity_kcal_mol?: number | null;
  poses_kcal_mol?:    number[];
  box?:               { center: number[]; box_size: number[] };
  note?:              string;
  reason?:            string;
  error?:             string;
}

// ── Pharmacóforos 3D ligand-based (Tier 5.1) ──────────────────────────────────────

export interface PharmaFeature {
  family: string; label: string; role: string;
  x?: number; y?: number; z?: number;
  present_in?: number; fraction?: number;
}

export interface PharmaDistance {
  a: number; b: number; family_a: string; family_b: string; distance: number;
}

export interface PharmacophoreResult {
  available:  boolean;
  mode?:      string;
  n_molecules?: number;
  drug_id?:   string;
  seed_smiles?: string;
  features?:  PharmaFeature[];
  feature_counts?: Record<string, number>;
  distances?: PharmaDistance[];
  consensus_features?: PharmaFeature[];
  references?: string[];
  note?:      string;
  reason?:    string;
  error?:     string;
}

// ── GNN de repurposing fármaco→enfermedad (Tier 4.7, BiomedGPS) ───────────────────

export interface DiseasePrediction {
  disease_id:   string;
  disease_name: string;
  probability:  number;
}

export interface DiseaseGnnResult {
  available:   boolean;
  drug?:       { drugbank_id: string; name: string };
  predictions?: DiseasePrediction[];
  model?:      DtiModelMetrics;
  error?:      string;
}

// ── GNN Chemprop de toxicidad Tox21 (Tier 4.6) ────────────────────────────────────

export interface ChempropToxPrediction {
  assay:       string;
  label:       string;
  probability: number | null;
}

export interface ChempropToxResult {
  available:   boolean;
  engine?:     string;
  paper?:      string;
  smiles?:     string;
  predictions?: ChempropToxPrediction[];
  disclaimer?: string;
  reason?:     string;
}

// ── GNN de predicción fármaco-diana (Tier 4.2) ────────────────────────────────────

export interface DtiPrediction {
  target_id:   string;
  target_name: string;
  uniprot_id:  string;
  gene_name:   string;
  probability: number;
}

export interface DtiModelMetrics {
  auc_pr?:           number;
  roc_auc?:          number;
  embedding_method?: string;
  n_positive?:       number;
  n_edges_written?:  number;
  trained_at?:       string;
}

export interface DtiGnnResult {
  available:    boolean;
  drug:         { name: string; drugbank_id: string };
  predictions:  DtiPrediction[];
  model:        DtiModelMetrics;
}

// ── ADMET supervisado (Tier 4.3) ─────────────────────────────────────────────────

export interface AdmetPrediction {
  endpoint:         string;
  label:            string;
  task:             'classification' | 'regression';
  proba?:           number;
  value?:           number;
  unit?:            string;
  positive_meaning?: string;
  model_auc?:       number | null;
  model_rmse?:      number | null;
  n_train?:         number | null;
}

export interface AdmetResult {
  available:   boolean;
  smiles?:     string;
  predictions?: AdmetPrediction[];
  reason?:     string;
}

// ── De novo design (Tier 4.4) ────────────────────────────────────────────────────

export interface DeNovoRequest {
  seed:    string;
  mode?:   'grow' | 'mutate' | 'link';
  engine?: 'crem' | 'synthemol' | 'reinvent' | 'pharma';
  n?:      number;
}

export interface DeNovoCandidate {
  smiles:              string;
  qed:                 number | null;
  sa_score:            number | null;
  similarity_to_seed:  number | null;
  mol_weight:          number;
  logp:                number;
  lipinski_rules:      number;
  model_score?:        number;  // score del predictor SyntheMol (solo motor synthemol)
  pharma_match?:       number;  // fracción de rasgos del pharmacóforo (solo motor pharma)
  fitness?:            number;  // fitness del GA (solo motor pharma)
}

export interface DeNovoResult {
  available:   boolean;
  engine?:     string;
  paper?:      string;
  seed_smiles?: string;
  mode?:       string;
  generated?:  number;
  candidates?: DeNovoCandidate[];
  disclaimer?: string;
  reason?:     string;
}

// ── Chemical space map (Tier 4.1) ───────────────────────────────────────────────

export interface ChemicalSpacePoint {
  drugbank_id: string;
  name:        string;
  type:        string;
  groups:      string[];
  x:           number;
  y:           number;
  cluster:     number;
}

export interface ChemicalSpaceCluster {
  cluster:    number;
  size:       number;
  is_outlier: boolean;
  top_types:  string[];
  examples:   string[];
}

export interface ChemicalSpaceResult {
  available: boolean;
  points:    ChemicalSpacePoint[];
  clusters:  ChemicalSpaceCluster[];
}

export interface ChemicalSpaceNeighbor {
  drugbank_id: string;
  name:        string;
  score:       number;
}

export interface ChemicalSpaceLocateResult {
  available: boolean;
  x:         number;
  y:         number;
  cluster:   number;
  neighbors: ChemicalSpaceNeighbor[];
  reason?:   string;
}

export interface ReversionHit {
  name:    string;
  pert_id: string | null;
  score:   number;
  cell_id: string | null;
  dose:    string | number | null;
}

export interface SignatureReversionResult {
  available:  boolean;
  mode:       'reverse' | 'mimic';
  results:    ReversionHit[];
  share_id?:  string;
  genes_used?: { up: number; dn: number };
  reason?:    string;
}

export interface DiseaseAssociation {
  disease_id:       string;
  disease_name:     string;
  score:            number;
  supporting_genes: string[];
  gene_count:       number;
}

export interface DiseaseEvidenceResult {
  drug:           { name: string; drugbank_id: string };
  genes:          string[];
  available:      boolean;
  genes_mapped:   { gene: string; ensembl_id: string }[];
  genes_unmapped: string[];
  diseases:       DiseaseAssociation[];
}
