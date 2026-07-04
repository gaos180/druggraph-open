import jwt
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission
from django.conf import settings
from .services import get_user_by_id

class SimpleUser:
    def __init__(self, data: dict):
        self.id = data['_id']
        self.email = data['email']
        self.name = data['name']
        self.is_admin = data.get('is_admin', False)
        self.is_authenticated = True

    def __str__(self):
        return self.email

class IsAdminUser(BasePermission):
    """Solo permite acceso a usuarios con is_admin=True."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and getattr(request.user, 'is_authenticated', False)
            and getattr(request.user, 'is_admin', False)
        )


class MongoJWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        # Prioridad: header Authorization primero (compatibilidad con scripts/API),
        # cookie HttpOnly dg_auth segundo.
        token = request.COOKIES.get('dg_auth')
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
        if not token:
            return None
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token expired')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid token')

        user_data = get_user_by_id(payload['user_id'])
        if not user_data:
            raise AuthenticationFailed('User not found')
        return (SimpleUser(user_data), token)