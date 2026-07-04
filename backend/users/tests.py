from unittest.mock import patch
from bson import ObjectId
import datetime

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from users.services import generate_token, hash_password

# ── Helpers ────────────────────────────────────────────────────────────────────

def make_user(is_admin: bool = False, name: str = 'Test User', email: str = 'test@test.com') -> dict:
    uid = str(ObjectId())
    return {
        '_id': uid, 'id': uid,
        'email': email, 'name': name, 'is_admin': is_admin,
        'password': hash_password('password123'),
        'created_at': datetime.datetime.utcnow().isoformat(),
    }

def auth_headers(user: dict) -> dict:
    token = generate_token(user['_id'], user['is_admin'])
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


# ── Registro ───────────────────────────────────────────────────────────────────

class RegisterTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    @patch('users.views.create_user')
    def test_register_success(self, mock_create):
        user = make_user(email='new@test.com')
        mock_create.return_value = user
        with patch('users.authentication.get_user_by_id', return_value=user):
            res = self.client.post('/api/auth/register/', {
                'name': 'Test User', 'email': 'new@test.com', 'password': 'password123',
            }, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertIn('token', res.json())
        self.assertEqual(res.json()['user']['email'], 'new@test.com')

    @patch('users.views.create_user')
    def test_register_missing_fields(self, mock_create):
        res = self.client.post('/api/auth/register/', {'email': 'x@x.com'}, format='json')
        self.assertEqual(res.status_code, 400)
        mock_create.assert_not_called()

    @patch('users.views.create_user')
    def test_register_duplicate_email(self, mock_create):
        mock_create.side_effect = ValueError('email ya registrado')
        res = self.client.post('/api/auth/register/', {
            'name': 'A', 'email': 'dup@test.com', 'password': 'pass123',
        }, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('error', res.json())


# ── Login ──────────────────────────────────────────────────────────────────────

class LoginTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    @patch('users.views.authenticate_user')
    def test_login_success(self, mock_auth):
        user = make_user()
        mock_auth.return_value = user
        res = self.client.post('/api/auth/login/', {
            'email': 'test@test.com', 'password': 'password123',
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertIn('token', res.json())

    @patch('users.views.authenticate_user')
    def test_login_sets_httponly_cookie(self, mock_auth):
        user = make_user()
        mock_auth.return_value = user
        res = self.client.post('/api/auth/login/', {
            'email': 'test@test.com', 'password': 'password123',
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertIn('dg_auth', res.cookies)
        self.assertTrue(res.cookies['dg_auth']['httponly'])

    @patch('users.views.authenticate_user')
    def test_login_wrong_password(self, mock_auth):
        mock_auth.side_effect = ValueError('credenciales inválidas')
        res = self.client.post('/api/auth/login/', {
            'email': 'test@test.com', 'password': 'wrong',
        }, format='json')
        self.assertEqual(res.status_code, 401)

    def test_login_missing_fields(self):
        res = self.client.post('/api/auth/login/', {'email': 'x@x.com'}, format='json')
        self.assertEqual(res.status_code, 400)


# ── Logout ─────────────────────────────────────────────────────────────────────

class LogoutTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    @patch('users.authentication.get_user_by_id')
    def test_logout_success(self, mock_get):
        user = make_user()
        mock_get.return_value = user
        res = self.client.post('/api/auth/logout/', **auth_headers(user))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {'ok': True})
        # La cookie debe estar en la respuesta (con valor vacío al borrarse)
        self.assertIn('dg_auth', res.cookies)

    def test_logout_unauthenticated(self):
        res = self.client.post('/api/auth/logout/')
        self.assertIn(res.status_code, [401, 403])


# ── Autenticación por cookie ───────────────────────────────────────────────────

class CookieAuthTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    @patch('users.authentication.get_user_by_id')
    def test_me_with_cookie_auth(self, mock_get):
        """El endpoint /me/ debe funcionar con la cookie dg_auth (sin header)."""
        user = make_user()
        mock_get.return_value = user
        token = generate_token(user['_id'], user['is_admin'])
        self.client.cookies['dg_auth'] = token
        res = self.client.get('/api/auth/me/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['email'], user['email'])

    @patch('users.authentication.get_user_by_id')
    def test_header_takes_priority_over_cookie(self, mock_get):
        """El header Authorization tiene prioridad sobre la cookie."""
        cookie_user = make_user(email='cookie@test.com')
        header_user = make_user(email='header@test.com')
        # mock_get siempre devuelve header_user (el token del header es el válido)
        mock_get.return_value = header_user
        cookie_token = generate_token(cookie_user['_id'], cookie_user['is_admin'])
        self.client.cookies['dg_auth'] = cookie_token
        res = self.client.get('/api/auth/me/', **auth_headers(header_user))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['email'], header_user['email'])


# ── Me ─────────────────────────────────────────────────────────────────────────

class MeTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    @patch('users.authentication.get_user_by_id')
    def test_me_authenticated(self, mock_get):
        user = make_user()
        mock_get.return_value = user
        res = self.client.get('/api/auth/me/', **auth_headers(user))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['email'], user['email'])

    def test_me_unauthenticated(self):
        # Sin token → 403 (DRF anónimo + IsAuthenticated)
        res = self.client.get('/api/auth/me/')
        self.assertIn(res.status_code, [401, 403])

    @patch('users.authentication.get_user_by_id')
    @patch('users.views.update_own_profile')
    def test_update_me(self, mock_update, mock_get):
        user = make_user()
        mock_get.return_value = user
        mock_update.return_value = {**user, 'name': 'Nuevo Nombre'}
        res = self.client.patch('/api/auth/me/update/', {'name': 'Nuevo Nombre'},
                                format='json', **auth_headers(user))
        self.assertEqual(res.status_code, 200)
        mock_update.assert_called_once()

    @patch('users.authentication.get_user_by_id')
    @patch('users.views.change_own_password')
    def test_change_password(self, mock_change, mock_get):
        user = make_user()
        mock_get.return_value = user
        mock_change.return_value = None
        res = self.client.post('/api/auth/me/password/', {
            'current_password': 'password123', 'new_password': 'newpassword456',
        }, format='json', **auth_headers(user))
        self.assertEqual(res.status_code, 200)

    @patch('users.authentication.get_user_by_id')
    @patch('users.views.change_own_password')
    def test_change_password_wrong_current(self, mock_change, mock_get):
        user = make_user()
        mock_get.return_value = user
        mock_change.side_effect = ValueError('contraseña incorrecta')
        res = self.client.post('/api/auth/me/password/', {
            'current_password': 'wrong', 'new_password': 'new123',
        }, format='json', **auth_headers(user))
        self.assertEqual(res.status_code, 400)


# ── Admin CRUD ─────────────────────────────────────────────────────────────────

class AdminUserTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = make_user(is_admin=True, email='admin@test.com')
        self.regular = make_user(is_admin=False)

    @patch('users.authentication.get_user_by_id')
    @patch('users.views.list_users')
    def test_list_users_as_admin(self, mock_list, mock_get):
        mock_get.return_value = self.admin
        mock_list.return_value = {
            'page': 1, 'per_page': 20, 'has_next': False, 'has_prev': False,
            'results': [self.admin],
        }
        res = self.client.get('/api/auth/users/', **auth_headers(self.admin))
        self.assertEqual(res.status_code, 200)
        self.assertIn('results', res.json())

    @patch('users.authentication.get_user_by_id')
    def test_list_users_as_regular_user(self, mock_get):
        mock_get.return_value = self.regular
        res = self.client.get('/api/auth/users/', **auth_headers(self.regular))
        self.assertEqual(res.status_code, 403)

    def test_list_users_unauthenticated(self):
        res = self.client.get('/api/auth/users/')
        self.assertIn(res.status_code, [401, 403])

    @patch('users.authentication.get_user_by_id')
    @patch('users.views.create_user')
    def test_admin_create_user(self, mock_create, mock_get):
        mock_get.return_value = self.admin
        new_user = make_user(email='created@test.com')
        mock_create.return_value = new_user
        res = self.client.post('/api/auth/users/', {
            'name': 'Created', 'email': 'created@test.com', 'password': 'pass123',
        }, format='json', **auth_headers(self.admin))
        self.assertEqual(res.status_code, 201)

    @patch('users.authentication.get_user_by_id')
    @patch('users.views.delete_user')
    def test_admin_delete_user(self, mock_delete, mock_get):
        target = make_user(email='target@test.com')
        mock_get.return_value = self.admin
        mock_delete.return_value = True
        res = self.client.delete(f"/api/auth/users/{target['_id']}/", **auth_headers(self.admin))
        self.assertEqual(res.status_code, 200)

    @patch('users.authentication.get_user_by_id')
    @patch('users.views.admin_reset_password')
    def test_admin_reset_password(self, mock_reset, mock_get):
        target = make_user(email='target@test.com')
        mock_get.return_value = self.admin
        mock_reset.return_value = None
        res = self.client.post(
            f"/api/auth/users/{target['_id']}/reset-password/",
            {'new_password': 'newpass123'}, format='json', **auth_headers(self.admin),
        )
        self.assertEqual(res.status_code, 200)
