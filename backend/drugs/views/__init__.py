"""
drugs.views — Paquete de vistas, una por dominio funcional.

Cada submódulo agrupa las vistas de un área (drugs, graph, blast, gds, pathways,
sandbox, targets, tools, ddi, stats). Se re-exportan aquí para que `drugs/urls.py`
y `drugs/urls_tools.py` las importen desde un único punto (`from .views import ...`).
"""

from .drugs import (
    drug_filters_view,
    list_drugs_view,
    drug_detail,
)
from .graph import drug_graph_view
from .blast import blast_search_view
from .ddi import ddi_check_view
from .stats import stats_view, public_stats_view
from .gds import (
    gds_centrality_view,
    gds_communities_view,
    gds_link_prediction_view,
    gds_link_prediction_global_view,
)
from .pathways import drug_pathways_view
from .sandbox import (
    sandbox_analyze_view,
    sandbox_target_search_view,
    sandbox_cleanup_view,
    sandbox_swiss_targets_view,
    sandbox_pathways_view,
    sandbox_propagation_view,
)
from .targets import (
    targets_list_view,
    target_detail_view,
    target_uniprot_view,
    drugs_by_target_view,
    target_pathways_view,
    kegg_gene_pathways_view,
    target_graph_view,
    target_compare_view,
)
from .tools import deg_analysis_view, repurposing_view, toxicity_view
from .bioactivity import drug_bioactivity_view, sandbox_bioactivity_view
from .similarity import sandbox_similarity_detail_view
from .ddi_risk import ddi_risk_view
from .embedding_similarity import embedding_similarity_view

__all__ = [
    "drug_filters_view", "list_drugs_view", "drug_detail",
    "drug_graph_view", "blast_search_view", "ddi_check_view", "stats_view", "public_stats_view",
    "gds_centrality_view", "gds_communities_view",
    "gds_link_prediction_view", "gds_link_prediction_global_view",
    "drug_pathways_view",
    "sandbox_analyze_view", "sandbox_target_search_view", "sandbox_cleanup_view",
    "sandbox_swiss_targets_view", "sandbox_pathways_view", "sandbox_propagation_view",
    "targets_list_view", "target_detail_view", "target_uniprot_view",
    "drugs_by_target_view", "target_pathways_view", "kegg_gene_pathways_view",
    "target_graph_view", "target_compare_view",
    "deg_analysis_view", "repurposing_view", "toxicity_view",
    "drug_bioactivity_view", "sandbox_bioactivity_view",
    "sandbox_similarity_detail_view", "ddi_risk_view", "embedding_similarity_view",
]
