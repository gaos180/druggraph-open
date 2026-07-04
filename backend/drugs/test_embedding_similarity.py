"""
test_embedding_similarity.py — Tests de similitud por embedding ChemBERTa (Tier 3.2).

Mockean el modelo (embed) y Neo4j; verifican degradación 503, validación y contrato.
"""
from unittest.mock import patch, MagicMock

from bson import ObjectId
from django.test import SimpleTestCase
from rest_framework.test import APIClient

from users.services import generate_token


def make_user():
    uid = str(ObjectId())
    return {'_id': uid, 'id': uid, 'email': 'u@test.com', 'name': 'U', 'is_admin': False}


def auth_headers(u):
    return {'HTTP_AUTHORIZATION': f'Bearer {generate_token(u["_id"], u["is_admin"])}'}


class EmbeddingSimilarityTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('config.services.chemberta_service.EMBEDDINGS_OK', False)
    @patch('users.authentication.get_user_by_id')
    def test_unavailable_returns_503(self, mock_user):
        mock_user.return_value = self.user
        res = self.client.post('/api/drugs/sandbox/embedding-similarity/',
                               {'smiles': 'CCO'}, format='json', **auth_headers(self.user))
        self.assertEqual(res.status_code, 503)

    @patch('config.services.chemberta_service.EMBEDDINGS_OK', True)
    @patch('users.authentication.get_user_by_id')
    def test_missing_smiles(self, mock_user):
        mock_user.return_value = self.user
        res = self.client.post('/api/drugs/sandbox/embedding-similarity/', {}, format='json',
                               **auth_headers(self.user))
        self.assertEqual(res.status_code, 400)

    @patch('drugs.views.embedding_similarity._session')
    @patch('config.services.chemberta_service.embed', return_value=[0.1] * 768)
    @patch('config.services.chemberta_service.EMBEDDINGS_OK', True)
    @patch('users.authentication.get_user_by_id')
    def test_success(self, mock_user, mock_embed, mock_session):
        mock_user.return_value = self.user
        session = MagicMock()
        session.run.return_value.data.return_value = [
            {'drugbank_id': 'DC35', 'name': 'Aspirin', 'score': 0.98},
        ]
        mock_session.return_value.__enter__.return_value = session
        res = self.client.post('/api/drugs/sandbox/embedding-similarity/',
                               {'smiles': 'CC(=O)Oc1ccccc1C(=O)O'}, format='json',
                               **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body['available'])
        self.assertEqual(body['results'][0]['drugbank_id'], 'DC35')

    @patch('drugs.views.embedding_similarity._session')
    @patch('config.services.chemberta_service.embed', return_value=[0.1] * 768)
    @patch('config.services.chemberta_service.EMBEDDINGS_OK', True)
    @patch('users.authentication.get_user_by_id')
    def test_index_not_populated(self, mock_user, mock_embed, mock_session):
        mock_user.return_value = self.user
        session = MagicMock()
        session.run.side_effect = Exception("There is no such vector schema index: drug_chemberta")
        mock_session.return_value.__enter__.return_value = session
        res = self.client.post('/api/drugs/sandbox/embedding-similarity/',
                               {'smiles': 'CCO'}, format='json', **auth_headers(self.user))
        self.assertEqual(res.status_code, 503)
