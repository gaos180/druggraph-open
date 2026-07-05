"""
test_ddi_sql.py — Tests del verificador de DDI sobre la capa SQL (PostgreSQL).

Se mockea la conexión Postgres (`config.services.ddi_service.get_connection`) para
probar `interactions_for` / `check_pair` y la vista sin BD real.
"""
from unittest.mock import MagicMock, patch

from bson import ObjectId
from django.test import SimpleTestCase
from rest_framework.test import APIClient

from users.services import generate_token
from config.services import ddi_service
from config.services.postgres import PostgresUnavailable


# ── Helpers de auth ──────────────────────────────────────────────────────────
def make_user():
    uid = str(ObjectId())
    return {'_id': uid, 'id': uid, 'email': 'u@test.com', 'name': 'U', 'is_admin': False}


def auth_headers(u):
    return {'HTTP_AUTHORIZATION': f'Bearer {generate_token(u["_id"], u["is_admin"])}'}


# ── Fake de conexión psycopg ─────────────────────────────────────────────────
def fake_conn(fetchall=None, fetchone=None):
    """Devuelve un MagicMock que imita psycopg: conn.execute(...) -> cursor."""
    cursor = MagicMock()
    cursor.fetchall.return_value = fetchall or []
    cursor.fetchone.return_value = fetchone
    conn = MagicMock()
    conn.execute.return_value = cursor
    return conn


# ── Tests de servicio (unidad) ───────────────────────────────────────────────
class DdiServiceTests(SimpleTestCase):
    def test_normalize_pair(self):
        self.assertEqual(ddi_service.normalize_pair('DC4', 'DC1579'), ('DC1579', 'DC4'))
        self.assertEqual(ddi_service.normalize_pair('DC1579', 'DC4'), ('DC1579', 'DC4'))

    @patch('config.services.ddi_service.get_connection')
    def test_interactions_for(self, mock_get_conn):
        # SQL ya devuelve el "otro" fármaco + description/severity/source ordenado.
        rows = [
            ('DC824', 'DDI: Tachycardia', 30.0, 'TWOSIDES'),
            ('DC1579', 'DDI: Bradycardia', 20.0, 'TWOSIDES'),
        ]
        mock_get_conn.return_value = fake_conn(fetchall=rows)

        res = ddi_service.interactions_for('DC4', enrich_names=False)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]['drugbank_id'], 'DC824')
        self.assertEqual(res[0]['severity'], 30.0)
        self.assertEqual(res[0]['source'], 'TWOSIDES')
        self.assertEqual(res[0]['description'], 'DDI: Tachycardia')

    @patch('config.services.ddi_service.get_connection')
    def test_check_pair_found(self, mock_get_conn):
        row = ('DC1579', 'DC4', 'DDI: Bradycardia', 20.0, 'TWOSIDES')
        mock_get_conn.return_value = fake_conn(fetchone=row)

        # Orden invertido en la llamada; el par se normaliza internamente.
        res = ddi_service.check_pair('DC4', 'DC1579')
        self.assertIsNotNone(res)
        self.assertEqual(res['drug_a'], 'DC1579')
        self.assertEqual(res['drug_b'], 'DC4')
        self.assertEqual(res['severity'], 20.0)

    @patch('config.services.ddi_service.get_connection')
    def test_check_pair_not_found(self, mock_get_conn):
        mock_get_conn.return_value = fake_conn(fetchone=None)
        self.assertIsNone(ddi_service.check_pair('DC4', 'DC999999'))


# ── Tests de la vista (integración con mocks) ────────────────────────────────
class DdiViewTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.ddi.get_db')
    @patch('config.services.ddi_service.interactions_for')
    def test_single_mode(self, mock_ix, mock_db, mock_user):
        mock_user.return_value = self.user
        mock_db.return_value.drugs.find_one.return_value = {'name': 'levobupivacaine'}
        mock_ix.return_value = [
            {'drugbank_id': 'DC824', 'name': 'dexamethasone',
             'description': 'DDI: Tachycardia', 'severity': 30.0, 'source': 'TWOSIDES'},
        ]
        res = self.client.get('/api/drugs/ddi/?drug_a=DC4', **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['mode'], 'single')
        self.assertEqual(body['drug'], {'drugbank_id': 'DC4', 'name': 'levobupivacaine'})
        self.assertEqual(body['interaction_count'], 1)
        # Forma histórica: solo drugbank_id, name, description (sin severity/source).
        self.assertEqual(set(body['interactions'][0].keys()),
                         {'drugbank_id', 'name', 'description'})
        self.assertEqual(body['interactions'][0]['drugbank_id'], 'DC824')

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.ddi.get_db')
    @patch('config.services.ddi_service.check_pair')
    def test_pair_mode_interacts(self, mock_check, mock_db, mock_user):
        mock_user.return_value = self.user
        mock_db.return_value.drugs.find_one.side_effect = [
            {'name': 'levobupivacaine'}, {'name': 'lidocaine'}]
        mock_check.return_value = {
            'drug_a': 'DC1579', 'drug_b': 'DC4',
            'description': 'DDI: Bradycardia', 'severity': 20.0, 'source': 'TWOSIDES'}
        res = self.client.get('/api/drugs/ddi/?drug_a=DC4&drug_b=DC1579',
                              **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body['mode'], 'pair')
        self.assertTrue(body['interacts'])
        self.assertEqual(body['description'], 'DDI: Bradycardia')
        self.assertEqual(set(body.keys()),
                         {'mode', 'drug_a', 'drug_b', 'interacts', 'description'})

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.ddi.get_db')
    @patch('config.services.ddi_service.check_pair')
    def test_pair_mode_no_interaction(self, mock_check, mock_db, mock_user):
        mock_user.return_value = self.user
        mock_db.return_value.drugs.find_one.side_effect = [
            {'name': 'A'}, {'name': 'B'}]
        mock_check.return_value = None
        res = self.client.get('/api/drugs/ddi/?drug_a=DC4&drug_b=DC2',
                              **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertFalse(body['interacts'])
        self.assertIsNone(body['description'])

    @patch('users.authentication.get_user_by_id')
    def test_invalid_id(self, mock_user):
        mock_user.return_value = self.user
        res = self.client.get('/api/drugs/ddi/?drug_a=INVALID', **auth_headers(self.user))
        self.assertEqual(res.status_code, 400)

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.ddi.get_db')
    def test_drug_not_found(self, mock_db, mock_user):
        mock_user.return_value = self.user
        mock_db.return_value.drugs.find_one.return_value = None
        res = self.client.get('/api/drugs/ddi/?drug_a=DC999999', **auth_headers(self.user))
        self.assertEqual(res.status_code, 404)

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.ddi.get_db')
    @patch('config.services.ddi_service.interactions_for',
           side_effect=PostgresUnavailable('down'))
    def test_postgres_unavailable_degrades_503(self, mock_ix, mock_db, mock_user):
        mock_user.return_value = self.user
        mock_db.return_value.drugs.find_one.return_value = {'name': 'X'}
        res = self.client.get('/api/drugs/ddi/?drug_a=DC4', **auth_headers(self.user))
        self.assertEqual(res.status_code, 503)
