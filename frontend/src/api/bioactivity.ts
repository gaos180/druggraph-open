import api from './client';

export interface ChemblMechanism {
  mechanism_of_action: string | null;
  action_type:         string | null;
  target_chembl_id:    string | null;
  max_phase:           number | null;
}

export interface ChemblActivity {
  standard_type:     string;
  standard_value:    string | number | null;
  standard_units:    string | null;
  pchembl_value:     number | null;
  target_pref_name:  string | null;
  target_organism:   string | null;
  assay_description: string;
}

export interface ChemblProfile {
  available:  boolean;
  molecule:   { chembl_id: string; pref_name: string | null; max_phase: number | null; molecule_type: string | null } | null;
  mechanisms: ChemblMechanism[];
  activities: ChemblActivity[];
}

export interface PubchemAssay {
  aid:               string;
  activity:          string;
  target_gene_id:    string;
  target_accession:  string;
  activity_value_um: string;
  activity_name:     string;
  assay_name:        string;
  assay_type:        string;
}

export interface PubchemSummary {
  available: boolean;
  cid:       number | null;
  total:     number;
  active:    number;
  inactive:  number;
  assays:    PubchemAssay[];
}

export interface BioactivityResponse {
  available: boolean;
  drug?:     { drugbank_id: string; name: string };
  smiles?:   string;
  chembl?:   ChemblProfile;
  pubchem?:  PubchemSummary;
  notes?:    string[];
}

export const bioactivityApi = {
  forDrug: (drugId: string) =>
    api.get<BioactivityResponse>(`/drugs/${drugId}/bioactivity/`),

  forSmiles: (smiles: string) =>
    api.post<BioactivityResponse>('/drugs/sandbox/bioactivity/', { smiles }),
};
