"""
test_reports.py — Tests de la reportería IA (Gemini).

No tocan Mongo ni la API real de Gemini: mockean `gemini_service.generate` y
`report_service.save_report`. Verifican validación de entrada, códigos de estado
(400/503/200) y el contrato de la respuesta.
"""
from unittest.mock import patch

from bson import ObjectId
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient

from users.services import generate_token


def make_user() -> dict:
    uid = str(ObjectId())
    return {'_id': uid, 'id': uid, 'email': 'u@test.com', 'name': 'U', 'is_admin': False}


def auth_headers(user: dict) -> dict:
    return {'HTTP_AUTHORIZATION': f'Bearer {generate_token(user["_id"], user["is_admin"])}'}


TOX_PAYLOAD = {
    'drug': {'name': 'Aspirina', 'drugbank_id': 'DB00945'},
    'risk_score': 5, 'risk_level': 'moderado',
    'alerts': [{'gene_name': 'PTGS1', 'level': 'medium', 'category': 'GI', 'message': 'COX-1'}],
}


class ReportGenerateTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('users.authentication.get_user_by_id')
    def test_invalid_kind_returns_400(self, mock_user):
        mock_user.return_value = self.user
        res = self.client.post(
            '/api/reports/generate/',
            {'kind': 'no-existe', 'payload': TOX_PAYLOAD}, format='json',
            **auth_headers(self.user),
        )
        self.assertEqual(res.status_code, 400)

    @patch('users.authentication.get_user_by_id')
    def test_empty_payload_returns_400(self, mock_user):
        mock_user.return_value = self.user
        res = self.client.post(
            '/api/reports/generate/',
            {'kind': 'toxicity', 'payload': {}}, format='json',
            **auth_headers(self.user),
        )
        self.assertEqual(res.status_code, 400)

    @override_settings(GEMINI_API_KEY='')
    @patch('users.authentication.get_user_by_id')
    def test_unconfigured_gemini_returns_503(self, mock_user):
        # Sin GEMINI_API_KEY → GeminiUnavailable → 503 (forzamos key vacía por si el
        # entorno/.env la trae cargada).
        mock_user.return_value = self.user
        res = self.client.post(
            '/api/reports/generate/',
            {'kind': 'toxicity', 'payload': TOX_PAYLOAD}, format='json',
            **auth_headers(self.user),
        )
        self.assertEqual(res.status_code, 503)

    @patch('config.services.report_service.save_report', return_value='rid123')
    @patch('config.services.gemini_service.generate', return_value='## Resumen\nTexto **grounded**.')
    @patch('users.authentication.get_user_by_id')
    def test_success_returns_markdown(self, mock_user, mock_gen, mock_save):
        mock_user.return_value = self.user
        res = self.client.post(
            '/api/reports/generate/',
            {'kind': 'toxicity', 'payload': TOX_PAYLOAD, 'style': 'executive', 'model': 'gemini-2.5-pro'},
            format='json', **auth_headers(self.user),
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn('report_markdown', body)
        self.assertEqual(body['kind'], 'toxicity')
        self.assertEqual(body['style'], 'executive')
        # 'pro' se normaliza a flash (único modelo disponible en el nivel gratuito)
        self.assertEqual(body['model'], 'gemini-2.5-flash')
        # el prompt enviado al modelo contiene los datos del análisis (grounding)
        prompt_arg = mock_gen.call_args.args[0]
        self.assertIn('PTGS1', prompt_arg)
        mock_save.assert_called_once()

    @patch('config.services.report_service.save_report', return_value='rid')
    @patch('config.services.gemini_service.generate', return_value='## X')
    @patch('users.authentication.get_user_by_id')
    def test_invalid_model_falls_back_to_default(self, mock_user, mock_gen, mock_save):
        mock_user.return_value = self.user
        res = self.client.post(
            '/api/reports/generate/',
            {'kind': 'toxicity', 'payload': TOX_PAYLOAD, 'model': 'gpt-malicioso'},
            format='json', **auth_headers(self.user),
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['model'], 'gemini-2.5-flash')

    def test_requires_auth(self):
        res = self.client.post(
            '/api/reports/generate/',
            {'kind': 'toxicity', 'payload': TOX_PAYLOAD}, format='json',
        )
        self.assertIn(res.status_code, (401, 403))


class ReportListTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()

    @patch('config.services.report_service.list_reports')
    @patch('users.authentication.get_user_by_id')
    def test_list_reports(self, mock_user, mock_list):
        mock_user.return_value = self.user
        mock_list.return_value = [{'report_id': 'r1', 'kind': 'toxicity', 'title': 'T'}]
        res = self.client.get('/api/reports/', **auth_headers(self.user))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()['reports']), 1)
