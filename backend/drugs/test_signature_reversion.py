"""
test_signature_reversion.py — Tests de reversión de firma LINCS (Tier 3.1).
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


REV = {
    'available': True, 'mode': 'reverse',
    'results': [{'name': 'temsirolimus', 'pert_id': 'x', 'score': 0.4, 'cell_id': 'A549', 'dose': '10'}],
    'share_id': 'abc', 'genes_used': {'up': 5, 'dn': 2},
}


class SignatureReversionTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('drugs.views.tools.signature_reversion.signature_reversion', return_value=REV)
    @patch('users.authentication.get_user_by_id')
    def test_success(self, mock_user, mock_rev):
        mock_user.return_value = self.user
        res = self.client.post('/api/tools/signature-reversion/',
                               {'up_genes': ['STAT1', 'IRF1'], 'dn_genes': ['MYC']}, format='json',
                               **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['results'][0]['name'], 'temsirolimus')

    @patch('users.authentication.get_user_by_id')
    def test_empty_signature(self, mock_user):
        mock_user.return_value = self.user
        res = self.client.post('/api/tools/signature-reversion/', {'up_genes': [], 'dn_genes': []},
                               format='json', **auth_headers(self.user))
        self.assertEqual(res.status_code, 400)
