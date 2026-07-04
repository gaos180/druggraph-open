"""
test_admet.py — Tests de la predicción ADMET supervisada (Tier 4.3).

Mockean admet_service; verifican validación, degradación 503 y contrato.
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


class AdmetTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('config.services.admet_service.ADMET_OK', False)
    @patch('users.authentication.get_user_by_id')
    def test_unavailable_returns_503(self, mock_user):
        mock_user.return_value = self.user
        res = self.client.post('/api/tools/admet/', {'smiles': 'CCO'}, format='json',
                               **auth_headers(self.user))
        self.assertEqual(res.status_code, 503)

    @patch('config.services.admet_service.ADMET_OK', True)
    @patch('users.authentication.get_user_by_id')
    def test_missing_smiles(self, mock_user):
        mock_user.return_value = self.user
        res = self.client.post('/api/tools/admet/', {}, format='json', **auth_headers(self.user))
        self.assertEqual(res.status_code, 400)

    @patch('config.services.admet_service.predict',
           return_value={'available': False, 'reason': 'Modelos ADMET no entrenados.'})
    @patch('config.services.admet_service.ADMET_OK', True)
    @patch('users.authentication.get_user_by_id')
    def test_models_not_trained_returns_503(self, mock_user, mock_predict):
        mock_user.return_value = self.user
        res = self.client.post('/api/tools/admet/', {'smiles': 'CCO'}, format='json',
                               **auth_headers(self.user))
        self.assertEqual(res.status_code, 503)

    @patch('config.services.admet_service.predict')
    @patch('config.services.admet_service.ADMET_OK', True)
    @patch('users.authentication.get_user_by_id')
    def test_success(self, mock_user, mock_predict):
        mock_user.return_value = self.user
        mock_predict.return_value = {
            'available': True, 'smiles': 'CCO',
            'predictions': [
                {'endpoint': 'bbbp', 'label': 'BBBP', 'task': 'classification',
                 'proba': 0.8, 'model_auc': 0.9, 'n_train': 1500},
                {'endpoint': 'esol', 'label': 'ESOL', 'task': 'regression',
                 'value': -1.2, 'unit': 'log mol/L', 'model_rmse': 0.7, 'n_train': 900},
            ],
        }
        res = self.client.post('/api/tools/admet/', {'smiles': 'CCO'}, format='json',
                               **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body['available'])
        self.assertEqual(len(body['predictions']), 2)
