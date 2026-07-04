"""
test_dti_gnn.py — Tests de la GNN de predicción fármaco-diana (Tier 4.2).

Mockean dti_gnn_service; verifican degradación 503 (GDS/modelo ausente) y contrato.
"""
from unittest.mock import patch

from bson import ObjectId
from django.test import SimpleTestCase
from rest_framework.test import APIClient

from users.services import generate_token
from config.services.dti_gnn_service import DTIUnavailable


def make_user():
    uid = str(ObjectId())
    return {'_id': uid, 'id': uid, 'email': 'u@test.com', 'name': 'U', 'is_admin': False}


def auth_headers(u):
    return {'HTTP_AUTHORIZATION': f'Bearer {generate_token(u["_id"], u["is_admin"])}'}


class DtiGnnTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('config.services.dti_gnn_service.predict_for_drug', side_effect=DTIUnavailable('GDS ausente'))
    @patch('users.authentication.get_user_by_id')
    def test_gds_unavailable_returns_503(self, mock_user, mock_pred):
        mock_user.return_value = self.user
        res = self.client.get('/api/tools/dti-gnn/DB00945/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 503)

    @patch('config.services.dti_gnn_service.predict_for_drug',
           return_value={'available': True, 'drug': {'drugbank_id': 'DB00945', 'name': 'Aspirin'},
                         'predictions': [], 'model': {}})
    @patch('users.authentication.get_user_by_id')
    def test_model_not_trained_returns_503(self, mock_user, mock_pred):
        mock_user.return_value = self.user
        res = self.client.get('/api/tools/dti-gnn/DB00945/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 503)

    @patch('config.services.dti_gnn_service.predict_for_drug')
    @patch('users.authentication.get_user_by_id')
    def test_success(self, mock_user, mock_pred):
        mock_user.return_value = self.user
        mock_pred.return_value = {
            'available': True,
            'drug': {'drugbank_id': 'DB00945', 'name': 'Aspirin'},
            'predictions': [{'target_id': 'BE0001', 'target_name': 'COX-2', 'uniprot_id': 'P35354',
                             'gene_name': 'PTGS2', 'probability': 0.87}],
            'model': {'auc_pr': 0.82, 'roc_auc': 0.8, 'embedding_method': 'fastrp',
                      'trained_at': '2026-07-02T00:00:00+00:00'},
        }
        res = self.client.get('/api/tools/dti-gnn/DB00945/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body['available'])
        self.assertEqual(body['predictions'][0]['gene_name'], 'PTGS2')
        self.assertEqual(body['model']['auc_pr'], 0.82)
