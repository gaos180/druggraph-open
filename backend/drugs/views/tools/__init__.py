"""
tools — Herramientas analíticas avanzadas de DrugGraph.

Endpoints:
  POST /api/tools/deg-analysis/        Análisis de Expresión Diferencial (deg.py)
  GET  /api/tools/repurposing/<id>/    Candidatos de reposicionamiento (repurposing.py)
  GET  /api/tools/toxicity/<id>/       Perfil de toxicidad y off-targets (toxicity.py)

Helpers compartidos (lectura de targets/info de un fármaco) en _common.py.
"""

from .deg import deg_analysis_view
from .repurposing import repurposing_view
from .toxicity import toxicity_view
from .proximity import proximity_view
from .disease_evidence import disease_evidence_view
from .signature_reversion import signature_reversion_view
from .chemical_space import chemical_space_view, chemical_space_locate_view
from .denovo import denovo_view
from .admet import admet_view
from .dti_gnn import dti_gnn_view
from .chemprop_tox import chemprop_tox_view
from .disease_gnn import disease_gnn_view
from .pharmacophore import pharmacophore_view
from .docking import (docking_view, docking_targets_view, docking_screen_view,
                      docking_refine_view, docking_funnel_view)
from .molecule_analysis import molecule_analysis_view
from .dossier import dossier_view
from .homology import homology_view, homology_species_view

__all__ = ["deg_analysis_view", "repurposing_view", "toxicity_view", "proximity_view",
           "disease_evidence_view", "signature_reversion_view",
           "chemical_space_view", "chemical_space_locate_view", "denovo_view", "admet_view",
           "dti_gnn_view", "chemprop_tox_view", "disease_gnn_view", "pharmacophore_view",
           "docking_view", "docking_targets_view", "docking_screen_view", "docking_refine_view",
           "docking_funnel_view", "molecule_analysis_view", "dossier_view",
           "homology_view", "homology_species_view"]
