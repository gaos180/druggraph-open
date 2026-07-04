from django.urls import path
from . import views
from .views import (
    drug_graph_view,
    blast_search_view,
    ddi_check_view,
    ddi_risk_view,
    stats_view,
    public_stats_view,
    gds_centrality_view,
    gds_communities_view,
    gds_link_prediction_view,
    gds_link_prediction_global_view,
    drug_pathways_view,
    sandbox_analyze_view,
    sandbox_target_search_view,
    sandbox_cleanup_view,
    sandbox_swiss_targets_view,
    sandbox_pathways_view,
    sandbox_propagation_view,
    targets_list_view,
    target_detail_view,
    target_uniprot_view,
    drugs_by_target_view,
    target_pathways_view,
    kegg_gene_pathways_view,
    target_graph_view,
    target_compare_view,
    drug_bioactivity_view,
    sandbox_bioactivity_view,
    sandbox_similarity_detail_view,
    embedding_similarity_view,
)

urlpatterns = [
    path('', views.list_drugs_view, name='list_drugs'),
    path('filters/', views.drug_filters_view, name='drug_filters'),

    # ── Dianas ────────────────────────────────────────────────────────────────
    path('targets/',                              targets_list_view,       name='targets-list'),
    path('targets/compare/',                      target_compare_view,     name='target-compare'),
    path('targets/by-gene/',                      drugs_by_target_view,    name='targets-by-gene'),
    path('targets/kegg-gene/',                    kegg_gene_pathways_view, name='targets-kegg-gene'),
    path('targets/<str:target_id>/graph/',        target_graph_view,       name='target-graph'),
    path('targets/<str:target_id>/uniprot/',      target_uniprot_view,     name='target-uniprot'),
    path('targets/<str:target_id>/pathways/',     target_pathways_view,    name='target-pathways'),
    path('targets/<str:target_id>/',              target_detail_view,      name='target-detail'),

    # ── Estadísticas globales ─────────────────────────────────────────────────
    path('stats/public/', public_stats_view, name='stats-public'),
    path('stats/', stats_view, name='stats'),

    # ── DDI Checker ───────────────────────────────────────────────────────────
    path('ddi/risk/', ddi_risk_view, name='ddi-risk'),
    path('ddi/', ddi_check_view, name='ddi-check'),

    # ── BLAST ────────────────────────────────────────────────────────────────
    path('blast/search/', blast_search_view, name='blast-search'),

    # ── GDS ──────────────────────────────────────────────────────────────────
    path('gds/centrality/',            gds_centrality_view,             name='gds-centrality'),
    path('gds/communities/',           gds_communities_view,            name='gds-communities'),
    path('gds/predict/<str:drug_id>/', gds_link_prediction_view,        name='gds-predict'),
    path('gds/predict-global/',        gds_link_prediction_global_view, name='gds-predict-global'),

    # ── Sandbox ───────────────────────────────────────────────────────────────
    path('sandbox/analyze/',              sandbox_analyze_view,        name='sandbox-analyze'),
    path('sandbox/targets/',              sandbox_target_search_view,  name='sandbox-targets'),
    path('sandbox/pathways/',             sandbox_pathways_view,       name='sandbox-pathways'),
    path('sandbox/propagation/',          sandbox_propagation_view,    name='sandbox-propagation'),
    path('sandbox/swiss-targets/',        sandbox_swiss_targets_view,  name='sandbox-swiss-targets'),
    path('sandbox/bioactivity/',          sandbox_bioactivity_view,    name='sandbox-bioactivity'),
    path('sandbox/similarity-detail/',    sandbox_similarity_detail_view, name='sandbox-similarity-detail'),
    path('sandbox/embedding-similarity/', embedding_similarity_view,   name='sandbox-embedding-similarity'),
    path('sandbox/<str:sandbox_id>/',     sandbox_cleanup_view,        name='sandbox-cleanup'),

    # ── Drug detail, graph y pathways (wildcards al final) ───────────────────
    path('<str:drug_id>/graph/',        drug_graph_view,      name='drug-graph'),
    path('<str:drug_id>/pathways/',     drug_pathways_view,   name='drug-pathways'),
    path('<str:drug_id>/bioactivity/',  drug_bioactivity_view, name='drug-bioactivity'),
    path('<str:drug_id>/',              views.drug_detail,    name='drug_detail'),
]