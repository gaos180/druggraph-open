import api from './client';

// ── Resultado de un fármaco que afecta un target ──────────────────────────────

export interface BlastHitDrug {
  drugbank_id: string;
  name: string;
  rel_types: string[];
  actions: string[];
}

// ── Target homólogo encontrado ─────────────────────────────────────────────────

export interface BlastHitTarget {
  drugbank_target_id: string;
  uniprot_id: string;
  name: string;
  organism: string;
  gene_name: string;
  ncbi_taxonomy_id: string;
}

// ── Datos del alineamiento BLAST ───────────────────────────────────────────────

export interface BlastAlignment {
  /** % de identidad (0–100) */
  pident: number;
  align_length: number;
  evalue: number;
  bitscore: number;
  qstart: number;
  qend: number;
  sstart: number;
  send: number;
}

export interface BlastHit {
  target: BlastHitTarget;
  alignment: BlastAlignment;
  drugs: BlastHitDrug[];
}

export interface BlastSearchResponse {
  query_length: number;
  hit_count: number;
  hits: BlastHit[];
  /** Organismos presentes en los resultados (para poblar el filtro de la UI) */
  organisms: string[];
}

export interface BlastSearchParams {
  sequence: string;
  max_hits?: number;
  evalue?: number;
  organism?: string;
  /** % identidad mínima (0–100) */
  min_identity?: number;
}

export const blastApi = {
  /**
   * Busca targets homólogos a una secuencia de aminoácidos y devuelve los
   * fármacos que los afectan. Acepta texto plano o formato FASTA.
   */
  search: (params: BlastSearchParams) =>
    api.post<BlastSearchResponse>('/drugs/blast/search/', params),
};
