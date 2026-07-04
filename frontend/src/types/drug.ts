/**
 * Tipos para el documento de fármaco tal como se almacena en MongoDB
 * (origen: DrugBank XML → JSON). Todos los campos son opcionales salvo
 * `name` para reflejar que el documento puede estar incompleto.
 */

// ── Sub-tipos reutilizables ───────────────────────────────────────────────────

/** Propiedad calculada o experimental de DrugBank */
export interface DrugProperty {
  kind: string;
  value: string;
  source?: string;
}

/** Enzima dentro de una reacción de DrugBank */
export interface ReactionEnzyme {
  name?: string;
  'drugbank-id'?: string;
  'uniprot-id'?: string;
}

/** Reacción de biotransformación del documento de DrugBank */
export interface DrugReaction {
  enzymes?: ReactionEnzyme[];
}

/** Diana farmacológica embebida en el documento de DrugBank (MongoDB) */
export interface DrugTargetEntry {
  name?: string;
  organism?: string;
  actions?: string[];
  id?: string;
}

/** Vía metabólica SMPDB embebida en el documento de DrugBank */
export interface DrugSmpdbPathway {
  name?: string;
  category?: string;
  'smpdb-id'?: string;
}

/** Efecto de polimorfismo genético (SNP effect) */
export interface SnpEffect {
  'rs-id'?: string;
  'gene-symbol'?: string;
  description?: string;
  'protein-name'?: string;
}

/** Reacción adversa genética (SNP adverse drug reaction) */
export interface SnpAdverseDrugReaction {
  'adverse-reaction'?: string;
  description?: string;
  'gene-symbol'?: string;
}

/** Nivel dentro de un código ATC */
export interface AtcLevel {
  code?: string;
  value?: string;
}

/** Código ATC con sus niveles jerárquicos */
export interface AtcCode {
  code?: string;
  level?: AtcLevel[];
}

/** Interacción fármaco-fármaco embebida en el documento de DrugBank */
export interface EmbeddedDrugInteraction {
  name?: string;
  'drugbank-id'?: string;
  description?: string;
}

/**
 * DrugBank ID — puede ser un string simple o un array con objetos que
 * incluyen `value` y `primary` cuando hay IDs secundarios.
 */
export type DrugBankIdField =
  | string
  | Array<{ value: string; primary: string }>;

/** Clasificación química ClassyFire */
export interface ChemicalClassification {
  description?: string;
  kingdom?: string;
  superclass?: string;
  class?: string;
  'direct-parent'?: string;
}

/** Secuencia FASTA de un biofármaco */
export interface DrugSequence {
  value: string;
  format?: string;
}

/** Referencia bibliográfica de DrugBank */
export interface DrugReference {
  citation?: string;
  title?: string;
  'pubmed-id'?: string;
  url?: string;
}

// ── Tipo principal ────────────────────────────────────────────────────────────

/**
 * Documento de fármaco tal como llega del endpoint `/api/drugs/<id>/`
 * (MongoDB, origen DrugBank XML).
 *
 * `name` es el único campo requerido; todos los demás son opcionales
 * porque distintos documentos de DrugBank tienen distinto nivel de detalle.
 */
export interface DrugRecord {
  _id?: string;
  name: string;

  // ── Identificadores ──────────────────────────────────────────────────────
  'drugbank-id'?: DrugBankIdField;
  'cas-number'?: string;
  unii?: string;

  // ── Clasificación y estado ───────────────────────────────────────────────
  type?: string;
  groups?: string[];
  state?: string;
  classification?: ChemicalClassification;

  // ── Descripción farmacológica ────────────────────────────────────────────
  description?: string;
  'mechanism-of-action'?: string;
  pharmacodynamics?: string;
  absorption?: string;
  metabolism?: string;
  /** Algunas entradas usan guion medio (XML origen), otras guion bajo (normalizado) */
  'half-life'?: string;
  half_life?: string;
  'route-of-elimination'?: string;
  clearance?: string;
  'volume-of-distribution'?: string;

  // ── Clínica ──────────────────────────────────────────────────────────────
  indication?: string;
  toxicity?: string;
  'food-interactions'?: string[];
  'affected-organisms'?: string[];
  'atc-codes'?: AtcCode[];
  'drug-interactions'?: EmbeddedDrugInteraction[];

  // ── Química ──────────────────────────────────────────────────────────────
  'average-mass'?: number | string;
  'monoisotopic-mass'?: number | string;
  'calculated-properties'?: DrugProperty[];
  'synthesis-reference'?: string;
  smiles?: string | null;

  // ── Dianas, enzimas y rutas (TargetsSection) ─────────────────────────────
  targets?: DrugTargetEntry[];
  /**
   * Las reacciones de DrugBank pueden estar anidadas; el componente usa
   * `.flat(2)` antes de iterar. Se tipan como array plano de reacciones
   * (TypeScript acepta `.flat()` sin problemas en un array ya plano).
   */
  reactions?: DrugReaction[];
  /** Vías metabólicas SMPDB embebidas en el documento (≠ rutas KEGG del PathwaysSection) */
  pathways?: DrugSmpdbPathway[];

  // ── Genómica ─────────────────────────────────────────────────────────────
  sequences?: DrugSequence[];
  'snp-effects'?: SnpEffect[];
  'snp-adverse-drug-reactions'?: SnpAdverseDrugReaction[];

  // ── Mercado ──────────────────────────────────────────────────────────────
  /**
   * DrugBank puede anidar precios como array directo o como `{ price: [...] }`.
   * El componente normaliza esto en `rawPrices: any[]` antes de renderizar.
   */
  prices?:
    | Array<Record<string, unknown>>
    | { price?: Array<Record<string, unknown>> | Record<string, unknown> };
  products?:
    | Array<Record<string, unknown>>
    | { product?: Array<Record<string, unknown>> | Record<string, unknown> };
  packagers?:
    | Array<Record<string, unknown>>
    | { packager?: Array<Record<string, unknown>> | Record<string, unknown> };

  // ── Referencias y sinónimos ──────────────────────────────────────────────
  /**
   * Los sinónimos pueden ser strings planos u objetos `{ value: string }`;
   * el componente usa `.flat(2)` y comprueba el tipo antes de usarlos.
   */
  synonyms?: Array<string | { value: string }>;
  /**
   * Las referencias pueden estar anidadas; el componente usa `.flat(5)`.
   */
  'general-references'?: DrugReference[];

  // ── Campos adicionales del listado ───────────────────────────────────────
  category_names?: string[];
}
