from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .authentication import IsAdminUser
from .services import (
    create_user,
    authenticate_user,
    generate_token,
    get_user_by_id,
    list_users,
    update_user,
    delete_user,
    admin_reset_password,
    update_own_profile,
    change_own_password,
)


# ── Autenticación pública ─────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    data = request.data
    if not all(data.get(f) for f in ('email', 'name', 'password')):
        return Response({'error': 'email, name y password son obligatorios.'}, status=400)
    try:
        user = create_user(data['email'], data['name'], data['password'])
        token = generate_token(user['_id'], user.get('is_admin', False))
        response = Response({'token': token, 'user': user}, status=201)
        response.set_cookie(
            key='dg_auth',
            value=token,
            httponly=True,
            secure=False,   # True en producción (HTTPS)
            samesite='Lax',
            max_age=86400,  # 24 h — igual que JWT_EXPIRY_HOURS
            path='/',
        )
        return response
    except ValueError as e:
        return Response({'error': str(e)}, status=400)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    data = request.data
    if not data.get('email') or not data.get('password'):
        return Response({'error': 'email y password son obligatorios.'}, status=400)
    try:
        user = authenticate_user(data['email'], data['password'])
        token = generate_token(str(user['_id']), user.get('is_admin', False))
        response = Response({
            'token': token,
            'user': {
                '_id':      str(user['_id']),
                'email':    user['email'],
                'name':     user['name'],
                'is_admin': user.get('is_admin', False),
            },
        })
        response.set_cookie(
            key='dg_auth',
            value=token,
            httponly=True,
            secure=False,   # True en producción (HTTPS)
            samesite='Lax',
            max_age=86400,  # 24 h — igual que JWT_EXPIRY_HOURS
            path='/',
        )
        return response
    except ValueError as e:
        return Response({'error': str(e)}, status=401)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """Invalida la sesión borrando la cookie HttpOnly dg_auth."""
    response = Response({'ok': True})
    response.delete_cookie('dg_auth', path='/')
    return response


# ── Perfil propio ─────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    u = request.user
    return Response({
        '_id':      u.id,
        'email':    u.email,
        'name':     u.name,
        'is_admin': u.is_admin,
    })


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_me(request):
    """Actualiza nombre y/o email del usuario autenticado."""
    data = request.data
    try:
        updated = update_own_profile(
            request.user.id,
            name=data.get('name'),
            email=data.get('email'),
        )
        return Response(updated)
    except ValueError as e:
        return Response({'error': str(e)}, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Cambia la propia contraseña (requiere la actual)."""
    data = request.data
    current  = data.get('current_password', '')
    new_pass = data.get('new_password', '')
    if not current or not new_pass:
        return Response({'error': 'current_password y new_password son obligatorios.'}, status=400)
    try:
        change_own_password(request.user.id, current, new_pass)
        return Response({'ok': True})
    except ValueError as e:
        return Response({'error': str(e)}, status=400)


# ── CRUD admin (solo is_admin=True) ──────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def admin_users_list(request):
    """
    GET  — Lista paginada de usuarios. Params: ?search=&page=&per_page=
    POST — Crea un usuario nuevo (puede ser admin).
    """
    if request.method == 'GET':
        search   = request.GET.get('search', '')
        page     = max(1, int(request.GET.get('page', 1)))
        per_page = min(50, max(1, int(request.GET.get('per_page', 20))))
        return Response(list_users(page=page, per_page=per_page, search=search))

    # POST — crear usuario
    data = request.data
    if not all(data.get(f) for f in ('email', 'name', 'password')):
        return Response({'error': 'email, name y password son obligatorios.'}, status=400)
    try:
        user = create_user(
            data['email'], data['name'], data['password'],
            is_admin=bool(data.get('is_admin', False)),
        )
        return Response(user, status=201)
    except ValueError as e:
        return Response({'error': str(e)}, status=400)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAdminUser])
def admin_user_detail(request, user_id: str):
    """
    GET    — Devuelve un usuario por ID.
    PATCH  — Actualiza name / email / is_admin.
    DELETE — Elimina el usuario (no puede borrarse a sí mismo).
    """
    if request.method == 'GET':
        user = get_user_by_id(user_id)
        if not user:
            return Response({'error': 'Usuario no encontrado.'}, status=404)
        return Response(user)

    if request.method == 'PATCH':
        data = request.data
        try:
            updated = update_user(
                user_id,
                name=data.get('name'),
                email=data.get('email'),
                is_admin=data['is_admin'] if 'is_admin' in data else None,
            )
            return Response(updated)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)

    # DELETE
    if user_id == request.user.id:
        return Response({'error': 'No puedes eliminar tu propia cuenta desde el panel.'}, status=400)
    if not delete_user(user_id):
        return Response({'error': 'Usuario no encontrado.'}, status=404)
    return Response({'deleted': True})


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_reset_password_view(request, user_id: str):
    """Restablece la contraseña de cualquier usuario (solo admin)."""
    new_password = request.data.get('new_password', '')
    if not new_password:
        return Response({'error': 'new_password es obligatorio.'}, status=400)
    try:
        admin_reset_password(user_id, new_password)
        return Response({'ok': True})
    except ValueError as e:
        return Response({'error': str(e)}, status=400)
