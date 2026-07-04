"""
test_disease_evidence.py — Tests de evidencia diana→enfermedad (Open Targets, Tier 2.1).
"""
from unittest.mock import patch

from bson import ObjectId
from django.test import SimpleTestCase
from rest_framework.test import APIClient

from users.services import generate_token


def make_user():
    uid = str(ObjectId())
    return {'_id': uid, 'id': uid, 'email': 'u@test.com', 'name': 'U', 'is_admin': False}


def auth_headers(u):
    return {'HTTP_AUTHORIZATION': f'Bearer {generate_token(u["_id"], u["is_admin"])}'}


EVID = {
    'available': True,
    'genes_mapped': [{'gene': 'EGFR', 'ensembl_id': 'ENSG00000146648'}],
    'genes_unmapped': [],
    'diseases': [{'disease_id': 'MONDO_0005233', 'disease_name': 'non-small cell lung carcinoma',
                  'score': 0.853, 'supporting_genes': ['EGFR'], 'gene_count': 1}],
}


class DiseaseEvidenceTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('drugs.views.tools.disease_evidence.diseases_for_genes', return_value=EVID)
    @patch('drugs.views.tools.disease_evidence._get_drug_info', return_value={'name': 'X', 'drugbank_id': 'DC1'})
    @patch('drugs.views.tools.disease_evidence._get_drug_targets', return_value=[{'gene_name': 'EGFR'}])
    @patch('users.authentication.get_user_by_id')
    def test_success(self, mock_user, mock_targets, mock_info, mock_evid):
        mock_user.return_value = self.user
        res = self.client.get('/api/tools/disease-evidence/DC530/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body['available'])
        self.assertEqual(body['diseases'][0]['disease_name'], 'non-small cell lung carcinoma')

    @patch('drugs.views.tools.disease_evidence._get_drug_targets', return_value=[])
    @patch('users.authentication.get_user_by_id')
    def test_no_genes(self, mock_user, mock_targets):
        mock_user.return_value = self.user
        res = self.client.get('/api/tools/disease-evidence/DCX/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 404)
