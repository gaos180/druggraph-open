"""
test_chemical_space.py — Tests del mapa de espacio químico (Tier 4.1).

Mockean el servicio; verifican degradación 503 (deps ausentes / nube no construida),
validación y contrato del endpoint.
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


class ChemicalSpaceTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('config.services.chemical_space_service.SPACE_OK', False)
    @patch('users.authentication.get_user_by_id')
    def test_unavailable_returns_503(self, mock_user):
        mock_user.return_value = self.user
        res = self.client.get('/api/tools/chemical-space/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 503)

    @patch('config.services.chemical_space_service.load_points',
           return_value={'available': False, 'points': [], 'clusters': []})
    @patch('config.services.chemical_space_service.SPACE_OK', True)
    @patch('users.authentication.get_user_by_id')
    def test_not_built_returns_503(self, mock_user, mock_load):
        mock_user.return_value = self.user
        res = self.client.get('/api/tools/chemical-space/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 503)

    @patch('config.services.chemical_space_service.load_points')
    @patch('config.services.chemical_space_service.SPACE_OK', True)
    @patch('users.authentication.get_user_by_id')
    def test_success(self, mock_user, mock_load):
        mock_user.return_value = self.user
        mock_load.return_value = {
            'available': True,
            'points': [{'drugbank_id': 'DC35', 'name': 'Aspirin', 'type': 'small molecule',
                        'groups': ['approved'], 'x': 1.0, 'y': 2.0, 'cluster': 0}],
            'clusters': [{'cluster': 0, 'size': 1, 'is_outlier': False,
                          'top_types': ['small molecule'], 'examples': ['Aspirin']}],
        }
        res = self.client.get('/api/tools/chemical-space/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body['available'])
        self.assertEqual(body['points'][0]['drugbank_id'], 'DC35')

    @patch('config.services.chemical_space_service.SPACE_OK', True)
    @patch('users.authentication.get_user_by_id')
    def test_locate_missing_smiles(self, mock_user):
        mock_user.return_value = self.user
        res = self.client.post('/api/tools/chemical-space/locate/', {}, format='json',
                               **auth_headers(self.user))
        self.assertEqual(res.status_code, 400)

    @patch('config.services.chemical_space_service.locate',
           return_value={'available': False, 'reason': 'Mapa no construido.'})
    @patch('config.services.chemical_space_service.SPACE_OK', True)
    @patch('users.authentication.get_user_by_id')
    def test_locate_not_built_returns_503(self, mock_user, mock_locate):
        mock_user.return_value = self.user
        res = self.client.post('/api/tools/chemical-space/locate/', {'smiles': 'CCO'},
                               format='json', **auth_headers(self.user))
        self.assertEqual(res.status_code, 503)

    @patch('config.services.chemical_space_service.locate')
    @patch('config.services.chemical_space_service.SPACE_OK', True)
    @patch('users.authentication.get_user_by_id')
    def test_locate_success(self, mock_user, mock_locate):
        mock_user.return_value = self.user
        mock_locate.return_value = {
            'available': True, 'x': 1.0, 'y': 2.0, 'cluster': 0,
            'neighbors': [{'drugbank_id': 'DC35', 'name': 'Aspirin', 'score': 0.98}],
        }
        res = self.client.post('/api/tools/chemical-space/locate/',
                               {'smiles': 'CC(=O)Oc1ccccc1C(=O)O'}, format='json',
                               **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['cluster'], 0)
