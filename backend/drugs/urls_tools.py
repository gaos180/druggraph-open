from django.urls import path
from .views import deg_analysis_view, repurposing_view, toxicity_view
from .views.tools import (
    proximity_view, disease_evidence_view, signature_reversion_view,
    chemical_space_view, chemical_space_locate_view, denovo_view, admet_view, dti_gnn_view,
    chemprop_tox_view, disease_gnn_view, pharmacophore_view,
)

urlpatterns = [
    path('deg-analysis/',                   deg_analysis_view,     name='tools-deg'),
    path('repurposing/<str:drug_id>/',      repurposing_view,      name='tools-repurposing'),
    path('toxicity/<str:drug_id>/',         toxicity_view,         name='tools-toxicity'),
    path('proximity/',                      proximity_view,        name='tools-proximity'),
    path('disease-evidence/<str:drug_id>/', disease_evidence_view, name='tools-disease-evidence'),
    path('signature-reversion/',            signature_reversion_view, name='tools-signature-reversion'),
    path('chemical-space/',                 chemical_space_view,   name='tools-chemical-space'),
    path('chemical-space/locate/',          chemical_space_locate_view, name='tools-chemical-space-locate'),
    path('denovo/',                         denovo_view,           name='tools-denovo'),
    path('admet/',                          admet_view,            name='tools-admet'),
    path('dti-gnn/<str:drug_id>/',          dti_gnn_view,          name='tools-dti-gnn'),
    path('chemprop-tox/',                   chemprop_tox_view,     name='tools-chemprop-tox'),
    path('disease-gnn/<str:drug_id>/',      disease_gnn_view,      name='tools-disease-gnn'),
    path('pharmacophore/',                  pharmacophore_view,    name='tools-pharmacophore'),
]
