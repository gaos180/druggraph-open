"""
test_similarity.py — Tests del desglose multi-fingerprint (Tier 1.2).

named_similarities usa RDKit real (instalado); el modo por drugbank_id mockea Mongo.
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


IBU = 'CC(C)Cc1ccc(cc1)C(C)C(=O)O'
NAPROXEN = 'COc1ccc2cc(ccc2c1)C(C)C(=O)O'


class SimilarityDetailTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('users.authentication.get_user_by_id')
    def test_smiles_pair(self, mock_user):
        mock_user.return_value = self.user
        res = self.client.post('/api/drugs/sandbox/similarity-detail/',
                               {'smiles': IBU, 'smiles_b': NAPROXEN}, format='json',
                               **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body['available'])
        self.assertIn('morgan', body['per_fingerprint'])
        self.assertGreater(body['consensus_score'], 0)

    @patch('users.authentication.get_user_by_id')
    def test_missing_smiles(self, mock_user):
        mock_user.return_value = self.user
        res = self.client.post('/api/drugs/sandbox/similarity-detail/', {}, format='json',
                               **auth_headers(self.user))
        self.assertEqual(res.status_code, 400)

    @patch('drugs.views.similarity.get_db')
    @patch('users.authentication.get_user_by_id')
    def test_by_drugbank_id(self, mock_user, mock_db):
        mock_user.return_value = self.user
        mock_db.return_value.drugs.find_one.return_value = {
            'name': 'Naproxen', 'calculated-properties': [{'kind': 'SMILES', 'value': NAPROXEN}],
        }
        res = self.client.post('/api/drugs/sandbox/similarity-detail/',
                               {'smiles': IBU, 'drugbank_id': 'DC1962'}, format='json',
                               **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['available'])

    @patch('drugs.views.similarity.get_db')
    @patch('users.authentication.get_user_by_id')
    def test_drug_without_smiles(self, mock_user, mock_db):
        mock_user.return_value = self.user
        mock_db.return_value.drugs.find_one.return_value = {'name': 'Lepirudin'}
        res = self.client.post('/api/drugs/sandbox/similarity-detail/',
                               {'smiles': IBU, 'drugbank_id': 'DC1234'}, format='json',
                               **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()['available'])
