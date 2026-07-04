from unittest.mock import patch
from bson import ObjectId
import datetime

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from users.services import generate_token, hash_password

# ── Helpers ────────────────────────────────────────────────────────────────────

def make_user(is_admin: bool = False) -> dict:
    uid = str(ObjectId())
    return {
        '_id': uid, 'id': uid,
        'email': 'user@test.com', 'name': 'Test User',
        'is_admin': is_admin,
        'password': hash_password('pass'),
        'created_at': datetime.datetime.utcnow().isoformat(),
    }

def auth_headers(user: dict) -> dict:
    token = generate_token(user['_id'], user['is_admin'])
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

SAMPLE_DRUG = {
    '_id': str(ObjectId()),
    'drugbank-id': [{'value': 'DB00001', 'primary': True}],
    'name': 'Lepirudin',
    'description': 'A recombinant form of hirudin.',
    'type': 'biotech',
    'groups': ['approved'],
}

SAMPLE_DRUG_DETAIL = {**SAMPLE_DRUG, 'pharmacology': {}, 'targets': [], 'enzymes': []}

SAMPLE_FILTERS = {'types': ['biotech', 'small molecule'], 'groups': ['approved', 'experimental']}


# ── Listado de fármacos ────────────────────────────────────────────────────────

class DrugListTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.drugs.list_drugs')
    def test_list_drugs_success(self, mock_list, mock_get_user):
        mock_get_user.return_value = self.user
        mock_list.return_value = {
            'results': [SAMPLE_DRUG], 'has_next': False, 'page': 1, 'per_page': 20,
        }
        res = self.client.get('/api/drugs/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        self.assertIn('results', res.json())

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.drugs.list_drugs')
    def test_list_drugs_with_search(self, mock_list, mock_get_user):
        mock_get_user.return_value = self.user
        mock_list.return_value = {'results': [], 'has_next': False, 'page': 1, 'per_page': 20}
        res = self.client.get('/api/drugs/?search=aspirin', **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        _, kwargs = mock_list.call_args
        self.assertEqual(kwargs.get('search'), 'aspirin')

    def test_list_drugs_unauthenticated(self):
        res = self.client.get('/api/drugs/')
        self.assertIn(res.status_code, [401, 403])

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.drugs.list_drugs')
    def test_list_drugs_pagination(self, mock_list, mock_get_user):
        mock_get_user.return_value = self.user
        mock_list.return_value = {'results': [], 'has_next': True, 'page': 2, 'per_page': 20}
        res = self.client.get('/api/drugs/?page=2', **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)


# ── Detalle de fármaco ─────────────────────────────────────────────────────────

class DrugDetailTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.drugs.get_drug')
    def test_drug_detail_found(self, mock_get_drug, mock_get_user):
        mock_get_user.return_value = self.user
        mock_get_drug.return_value = SAMPLE_DRUG_DETAIL
        res = self.client.get('/api/drugs/DB00001/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['name'], 'Lepirudin')

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.drugs.get_drug')
    def test_drug_detail_not_found(self, mock_get_drug, mock_get_user):
        mock_get_user.return_value = self.user
        mock_get_drug.return_value = None
        res = self.client.get('/api/drugs/DBXXXXX/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 404)

    def test_drug_detail_unauthenticated(self):
        res = self.client.get('/api/drugs/DB00001/')
        self.assertIn(res.status_code, [401, 403])


# ── Filtros ────────────────────────────────────────────────────────────────────

class DrugFiltersTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.drugs.get_drug_types')
    @patch('drugs.views.drugs.get_drug_groups')
    def test_filters_endpoint(self, mock_groups, mock_types, mock_get_user):
        mock_get_user.return_value = self.user
        mock_types.return_value = ['biotech', 'small molecule']
        mock_groups.return_value = ['approved', 'experimental']
        res = self.client.get('/api/drugs/filters/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('types', data)
        self.assertIn('groups', data)

    def test_filters_unauthenticated(self):
        res = self.client.get('/api/drugs/filters/')
        self.assertIn(res.status_code, [401, 403])


# ── Sandbox ────────────────────────────────────────────────────────────────────

class SandboxTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    def test_sandbox_requires_auth(self):
        res = self.client.post('/api/drugs/sandbox/analyze/', {'smiles': 'C'}, format='json')
        self.assertIn(res.status_code, [401, 403])

    @patch('users.authentication.get_user_by_id')
    def test_sandbox_missing_smiles(self, mock_get_user):
        mock_get_user.return_value = self.user
        res = self.client.post('/api/drugs/sandbox/analyze/', {}, format='json',
                               **auth_headers(self.user))
        self.assertEqual(res.status_code, 400)

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.sandbox.analyze_sandbox_compound')
    def test_sandbox_invalid_smiles(self, mock_analyze, mock_get_user):
        mock_get_user.return_value = self.user
        mock_analyze.side_effect = ValueError('SMILES inválido')
        res = self.client.post('/api/drugs/sandbox/analyze/', {
            'smiles': 'INVALID', 'name': 'Test',
        }, format='json', **auth_headers(self.user))
        self.assertEqual(res.status_code, 400)


# ── GDS ────────────────────────────────────────────────────────────────────────

class GdsTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.gds.centrality')
    def test_centrality_with_auth(self, mock_centrality, mock_get_user):
        mock_get_user.return_value = self.user
        mock_centrality.return_value = {'drugs': [], 'targets': [], 'node_count': 0, 'rel_count': 0}
        res = self.client.get('/api/drugs/gds/centrality/', **auth_headers(self.user))
        # GDS views usan Django vanilla — no requieren auth en el backend actual
        self.assertIn(res.status_code, [200, 503])

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.gds.communities')
    def test_communities_with_auth(self, mock_communities, mock_get_user):
        mock_get_user.return_value = self.user
        mock_communities.return_value = {'communities': [], 'node_count': 0, 'rel_count': 0}
        res = self.client.get('/api/drugs/gds/communities/', **auth_headers(self.user))
        self.assertIn(res.status_code, [200, 503])

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.gds.predict_links_for_drug')
    def test_link_prediction_not_found(self, mock_pred, mock_get_user):
        mock_get_user.return_value = self.user
        mock_pred.return_value = []
        res = self.client.get('/api/drugs/gds/predict/DB99999/', **auth_headers(self.user))
        self.assertIn(res.status_code, [200, 404, 503])


# ── Target graph ───────────────────────────────────────────────────────────────

SAMPLE_TARGET = {
    '_id': 'BE0000017',
    'name': 'Prothrombin',
    'gene_name': 'F2',
    'organism': 'Humans',
    'drug_refs': [
        {'drugbank_id': 'DB00001', 'drug_name': 'Lepirudin', 'rel_type': 'target'},
    ],
}


class TargetGraphTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    def test_graph_unauthenticated(self):
        res = self.client.get('/api/drugs/targets/BE0000017/graph/')
        self.assertIn(res.status_code, [401, 403])

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.targets._mongo_targets_ready', return_value=True)
    @patch('drugs.views.targets.get_db')
    def test_graph_from_mongo(self, mock_db, _ready, mock_get_user):
        mock_get_user.return_value = self.user
        mock_db.return_value.targets.find_one.return_value = SAMPLE_TARGET
        res = self.client.get('/api/drugs/targets/BE0000017/graph/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('nodes', data)
        self.assertIn('edges', data)
        node_kinds = {n['data']['kind'] for n in data['nodes']}
        self.assertIn('target', node_kinds)
        self.assertIn('drug', node_kinds)

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.targets._mongo_targets_ready', return_value=True)
    @patch('drugs.views.targets.get_db')
    def test_graph_target_not_found(self, mock_db, _ready, mock_get_user):
        mock_get_user.return_value = self.user
        mock_db.return_value.targets.find_one.return_value = None
        mock_driver = mock_db.return_value
        # Simulate Neo4j returning no rows via get_driver
        with patch('drugs.views.targets.get_driver') as mock_neo:
            session = mock_neo.return_value.session.return_value.__enter__.return_value
            session.run.return_value.data.return_value = []
            res = self.client.get('/api/drugs/targets/MISSING/graph/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 404)


# ── Target compare ─────────────────────────────────────────────────────────────

class TargetCompareTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    def test_compare_unauthenticated(self):
        res = self.client.get('/api/drugs/targets/compare/?a=BE0000017&b=BE0000522')
        self.assertIn(res.status_code, [401, 403])

    @patch('users.authentication.get_user_by_id')
    def test_compare_missing_params(self, mock_get_user):
        mock_get_user.return_value = self.user
        res = self.client.get('/api/drugs/targets/compare/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 400)

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.targets._mongo_targets_ready', return_value=True)
    @patch('drugs.views.targets.get_db')
    def test_compare_success(self, mock_db, _ready, mock_get_user):
        mock_get_user.return_value = self.user
        target_a = {**SAMPLE_TARGET, '_id': 'BE0000017',
                    'drug_refs': [{'drugbank_id': 'DB00001', 'drug_name': 'Lepirudin', 'rel_type': 'target'}]}
        target_b = {**SAMPLE_TARGET, '_id': 'BE0000522', 'name': 'Factor X',
                    'drug_refs': [{'drugbank_id': 'DB00001', 'drug_name': 'Lepirudin', 'rel_type': 'target'},
                                  {'drugbank_id': 'DB00002', 'drug_name': 'Bivalirudin', 'rel_type': 'target'}]}
        mock_db.return_value.targets.find_one.side_effect = lambda q, *_: (
            target_a if q.get('_id') == 'BE0000017' else target_b
        )
        res = self.client.get('/api/drugs/targets/compare/?a=BE0000017&b=BE0000522',
                              **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('stats', data)
        self.assertIn('common_drugs', data)
        self.assertIn('jaccard_similarity', data['stats'])
        self.assertGreater(data['stats']['jaccard_similarity'], 0)


# ── DDI checker ────────────────────────────────────────────────────────────────

class DdiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    def test_ddi_unauthenticated(self):
        res = self.client.get('/api/drugs/ddi/?drug_a=DB00001')
        self.assertIn(res.status_code, [401, 403])

    @patch('users.authentication.get_user_by_id')
    def test_ddi_missing_param(self, mock_get_user):
        mock_get_user.return_value = self.user
        res = self.client.get('/api/drugs/ddi/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 400)

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.ddi.get_db')
    def test_ddi_not_found(self, mock_db, mock_get_user):
        mock_get_user.return_value = self.user
        mock_db.return_value.drugs.find_one.return_value = None
        res = self.client.get('/api/drugs/ddi/?drug_a=DB99999', **auth_headers(self.user))
        self.assertEqual(res.status_code, 404)

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.ddi.get_db')
    def test_ddi_all_interactions(self, mock_db, mock_get_user):
        mock_get_user.return_value = self.user
        mock_db.return_value.drugs.find_one.return_value = {
            'name': 'Aspirin',
            'drug-interactions': [
                {'drugbank-id': 'DB00002', 'name': 'Ibuprofen', 'description': 'Bleeding risk'},
            ],
        }
        res = self.client.get('/api/drugs/ddi/?drug_a=DB00945', **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('interactions', data)
        self.assertEqual(len(data['interactions']), 1)

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.ddi.get_db')
    def test_ddi_pairwise_found(self, mock_db, mock_get_user):
        mock_get_user.return_value = self.user
        mock_db.return_value.drugs.find_one.return_value = {
            'name': 'Aspirin',
            'drug-interactions': [
                {'drugbank-id': 'DB00788', 'name': 'Naproxen', 'description': 'Increased bleeding'},
            ],
        }
        res = self.client.get('/api/drugs/ddi/?drug_a=DB00945&drug_b=DB00788',
                              **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get('interacts'))


# ── Stats ──────────────────────────────────────────────────────────────────────

class StatsTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    def test_stats_unauthenticated(self):
        res = self.client.get('/api/drugs/stats/')
        self.assertIn(res.status_code, [401, 403])

    @patch('users.authentication.get_user_by_id')
    @patch('drugs.views.stats.get_driver')
    @patch('drugs.views.stats.get_db')
    def test_stats_success(self, mock_db, mock_driver, mock_get_user):
        mock_get_user.return_value = self.user

        mock_db.return_value.drugs.count_documents.return_value = 16000
        mock_db.return_value.drugs.aggregate.return_value = iter([])

        session = mock_driver.return_value.session.return_value.__enter__.return_value
        session.run.return_value.single.return_value = None
        session.run.return_value.__iter__ = lambda s: iter([])

        res = self.client.get('/api/drugs/stats/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('mongo', data)
        self.assertIn('neo4j', data)
