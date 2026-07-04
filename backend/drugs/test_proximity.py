"""
test_proximity.py — Tests de proximidad de red (Tier 1.3).

Mockean Neo4j (targets) y el servicio de proximidad; verifican validación y contrato.
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


PROX = {
    'available': True, 'd_c': 0.8, 'd_c_symmetric': 1.15,
    'genes_a_used': ['F2', 'F10'], 'genes_b_used': ['F2', 'C3'],
    'reachable_a': 2, 'coverage_a': 1.0,
    'per_source': [{'gene': 'F2', 'distance': 0}, {'gene': 'F10', 'distance': 1}],
}


class ProximityTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('drugs.views.tools.proximity.closest_proximity', return_value=PROX)
    @patch('drugs.views.tools.proximity._get_drug_info', return_value={'name': 'X', 'drugbank_id': 'DC1'})
    @patch('drugs.views.tools.proximity._get_drug_targets')
    @patch('users.authentication.get_user_by_id')
    def test_success(self, mock_user, mock_targets, mock_info, mock_prox):
        mock_user.return_value = self.user
        mock_targets.side_effect = [
            [{'gene_name': 'F2'}, {'gene_name': 'F10'}],
            [{'gene_name': 'F2'}, {'gene_name': 'C3'}],
        ]
        res = self.client.get('/api/tools/proximity/?drug_a=DC14738&drug_b=DC14487',
                              **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['d_c_symmetric'], 1.15)

    @patch('users.authentication.get_user_by_id')
    def test_missing_params(self, mock_user):
        mock_user.return_value = self.user
        res = self.client.get('/api/tools/proximity/?drug_a=DC1', **auth_headers(self.user))
        self.assertEqual(res.status_code, 400)

    @patch('drugs.views.tools.proximity._get_drug_targets', return_value=[])
    @patch('users.authentication.get_user_by_id')
    def test_no_genes(self, mock_user, mock_targets):
        mock_user.return_value = self.user
        res = self.client.get('/api/tools/proximity/?drug_a=DC1&drug_b=DC2', **auth_headers(self.user))
        self.assertEqual(res.status_code, 404)
