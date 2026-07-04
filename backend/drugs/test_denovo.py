"""
test_denovo.py — Tests del diseño de novo (Tier 4.4).

Mockean denovo_service.generate; verifican validación, degradación 503 y contrato.
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


class DeNovoTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('users.authentication.get_user_by_id')
    def test_missing_seed(self, mock_user):
        mock_user.return_value = self.user
        res = self.client.post('/api/tools/denovo/', {}, format='json', **auth_headers(self.user))
        self.assertEqual(res.status_code, 400)

    @patch('users.authentication.get_user_by_id')
    def test_invalid_mode(self, mock_user):
        mock_user.return_value = self.user
        res = self.client.post('/api/tools/denovo/', {'seed': 'CCO', 'mode': 'bogus'},
                               format='json', **auth_headers(self.user))
        self.assertEqual(res.status_code, 400)

    @patch('config.services.denovo_service.generate',
           return_value={'available': False, 'reason': 'CReM no disponible.'})
    @patch('users.authentication.get_user_by_id')
    def test_engine_unavailable_returns_503(self, mock_user, mock_gen):
        mock_user.return_value = self.user
        res = self.client.post('/api/tools/denovo/', {'seed': 'CCO'}, format='json',
                               **auth_headers(self.user))
        self.assertEqual(res.status_code, 503)

    @patch('config.services.denovo_reinvent.prior_ready', return_value=False)
    @patch('users.authentication.get_user_by_id')
    def test_reinvent_unavailable_returns_503(self, mock_user, mock_ready):
        """Ruta real del motor REINVENT4 sin instalar → 503 limpio (Tier 4.4b)."""
        mock_user.return_value = self.user
        res = self.client.post('/api/tools/denovo/', {'seed': 'CCO', 'engine': 'reinvent'},
                               format='json', **auth_headers(self.user))
        self.assertEqual(res.status_code, 503)
        self.assertFalse(res.json()['available'])

    @patch('config.services.denovo_service.generate')
    @patch('users.authentication.get_user_by_id')
    def test_success(self, mock_user, mock_gen):
        mock_user.return_value = self.user
        mock_gen.return_value = {
            'available': True, 'engine': 'crem', 'paper': 'Polishchuk 2020',
            'seed_smiles': 'CCO', 'mode': 'mutate', 'generated': 3,
            'candidates': [{'smiles': 'CCCO', 'qed': 0.5, 'sa_score': 2.1,
                            'similarity_to_seed': 0.6, 'mol_weight': 60.1, 'logp': 0.1,
                            'lipinski_rules': 4}],
            'disclaimer': 'in silico',
        }
        res = self.client.post('/api/tools/denovo/',
                               {'seed': 'CCO', 'mode': 'mutate', 'engine': 'crem', 'n': 10},
                               format='json', **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body['available'])
        self.assertEqual(body['candidates'][0]['smiles'], 'CCCO')
        mock_gen.assert_called_once()
