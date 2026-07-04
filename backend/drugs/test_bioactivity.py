"""
test_bioactivity.py — Tests de bioactividad experimental (ChEMBL + PubChem).

Mockean los servicios externos y Mongo; verifican resolución de SMILES,
combinación de fuentes y el caso de fármaco sin SMILES.
"""
from unittest.mock import patch

from bson import ObjectId
from django.test import SimpleTestCase
from rest_framework.test import APIClient

from users.services import generate_token


def make_user() -> dict:
    uid = str(ObjectId())
    return {'_id': uid, 'id': uid, 'email': 'u@test.com', 'name': 'U', 'is_admin': False}


def auth_headers(user: dict) -> dict:
    return {'HTTP_AUTHORIZATION': f'Bearer {generate_token(user["_id"], user["is_admin"])}'}


CHEMBL_PROFILE = {
    'available': True,
    'molecule': {'chembl_id': 'CHEMBL25', 'pref_name': 'ASPIRIN', 'max_phase': 4, 'molecule_type': 'Small molecule'},
    'mechanisms': [{'mechanism_of_action': 'Cyclooxygenase inhibitor', 'action_type': 'INHIBITOR',
                    'target_chembl_id': 'CHEMBL2094253', 'max_phase': 4}],
    'activities': [{'standard_type': 'IC50', 'standard_value': 12500, 'standard_units': 'nM',
                    'pchembl_value': 4.9, 'target_pref_name': 'Prostaglandin G/H synthase 1',
                    'target_organism': 'Homo sapiens', 'assay_description': 'x'}],
}
PUBCHEM_SUMMARY = {'cid': 2244, 'total': 4929, 'active': 125, 'inactive': 2621,
                   'assays': [{'aid': '1', 'activity': 'Active', 'target_gene_id': '', 'target_accession': '',
                               'activity_value_um': '', 'activity_name': '', 'assay_name': 'X', 'assay_type': 'Confirmatory'}]}

DRUG_DOC = {
    '_id': 'DC35', 'drugbank-id': 'DC35', 'name': 'Aspirin',
    'smiles': 'CC(=O)Oc1ccccc1C(=O)O',
    'calculated-properties': [{'kind': 'SMILES', 'value': 'CC(=O)Oc1ccccc1C(=O)O', 'source': 'DrugCentral'}],
}


class DrugBioactivityTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('config.services.pubchem_service.bioassay_summary', return_value=PUBCHEM_SUMMARY)
    @patch('config.services.pubchem_service.cid_from_smiles', return_value=2244)
    @patch('config.services.chembl_service.full_profile', return_value=CHEMBL_PROFILE)
    @patch('drugs.views.bioactivity.get_db')
    @patch('users.authentication.get_user_by_id')
    def test_drug_bioactivity_success(self, mock_user, mock_db, mock_chembl, mock_cid, mock_assay):
        mock_user.return_value = self.user
        mock_db.return_value.drugs.find_one.return_value = DRUG_DOC
        res = self.client.get('/api/drugs/DC35/bioactivity/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body['available'])
        self.assertEqual(body['chembl']['molecule']['chembl_id'], 'CHEMBL25')
        self.assertEqual(body['pubchem']['active'], 125)

    @patch('drugs.views.bioactivity.get_db')
    @patch('users.authentication.get_user_by_id')
    def test_drug_without_smiles(self, mock_user, mock_db):
        mock_user.return_value = self.user
        mock_db.return_value.drugs.find_one.return_value = {'_id': 'DC1234', 'name': 'Lepirudin'}  # biotech, sin SMILES
        res = self.client.get('/api/drugs/DC1234/bioactivity/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()['available'])

    @patch('drugs.views.bioactivity.get_db')
    @patch('users.authentication.get_user_by_id')
    def test_drug_not_found(self, mock_user, mock_db):
        mock_user.return_value = self.user
        mock_db.return_value.drugs.find_one.return_value = None
        res = self.client.get('/api/drugs/DC99999/bioactivity/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 404)

    @patch('config.services.pubchem_service.bioassay_summary', return_value=PUBCHEM_SUMMARY)
    @patch('config.services.pubchem_service.cid_from_smiles', return_value=2244)
    @patch('config.services.chembl_service.full_profile', return_value=CHEMBL_PROFILE)
    @patch('users.authentication.get_user_by_id')
    def test_sandbox_bioactivity_success(self, mock_user, mock_chembl, mock_cid, mock_assay):
        mock_user.return_value = self.user
        res = self.client.post('/api/drugs/sandbox/bioactivity/',
                               {'smiles': 'CC(=O)Oc1ccccc1C(=O)O'}, format='json',
                               **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['available'])

    @patch('users.authentication.get_user_by_id')
    def test_sandbox_requires_smiles(self, mock_user):
        mock_user.return_value = self.user
        res = self.client.post('/api/drugs/sandbox/bioactivity/', {}, format='json', **auth_headers(self.user))
        self.assertEqual(res.status_code, 400)
