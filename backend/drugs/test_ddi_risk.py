"""
test_ddi_risk.py — Tests del riesgo DDI predicho (Tier 2.3).
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


class DdiRiskTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('config.services.proximity_service.closest_proximity',
           return_value={'available': True, 'd_c_symmetric': 1.0})
    @patch('drugs.views.ddi_risk._get_drug_info', side_effect=lambda i: {'name': i, 'drugbank_id': i})
    @patch('drugs.views.ddi_risk._get_drug_targets')
    @patch('users.authentication.get_user_by_id')
    def test_shared_cyp_and_target(self, mock_user, mock_targets, mock_info, mock_prox):
        mock_user.return_value = self.user
        mock_targets.side_effect = [
            [{'gene_name': 'CYP3A4'}, {'gene_name': 'PTGS1'}],  # drug A
            [{'gene_name': 'CYP3A4'}, {'gene_name': 'PTGS1'}, {'gene_name': 'F2'}],  # drug B
        ]
        res = self.client.get('/api/drugs/ddi/risk/?drug_a=DB1&drug_b=DB2', **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn('CYP3A4', body['shared_cyps'])
        self.assertIn('PTGS1', body['shared_targets'])
        self.assertGreater(body['risk_score'], 0)
        self.assertTrue(any(s['type'] == 'PK' for s in body['signals']))

    @patch('users.authentication.get_user_by_id')
    def test_missing_params(self, mock_user):
        mock_user.return_value = self.user
        res = self.client.get('/api/drugs/ddi/risk/?drug_a=DB1', **auth_headers(self.user))
        self.assertEqual(res.status_code, 400)

    @patch('drugs.views.ddi_risk._get_drug_targets', return_value=[])
    @patch('users.authentication.get_user_by_id')
    def test_no_genes(self, mock_user, mock_targets):
        mock_user.return_value = self.user
        res = self.client.get('/api/drugs/ddi/risk/?drug_a=DB1&drug_b=DB2', **auth_headers(self.user))
        self.assertEqual(res.status_code, 404)
