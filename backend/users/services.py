import bcrypt
import jwt
import datetime
from bson import ObjectId
from django.conf import settings
from config.services.mongo import get_db

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def generate_token(user_id: str, is_admin: bool) -> str:
    payload = {
        'user_id': str(user_id),
        'is_admin': is_admin,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=settings.JWT_EXPIRY_HOURS),
        'iat': datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm='HS256')

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=['HS256'])

def create_user(email: str, name: str, password: str, is_admin: bool = False) -> dict:
    db = get_db()
    if db.users.find_one({'email': email}):
        raise ValueError('Email already registered')
    user = {
        'email': email,
        'name': name,
        'password': hash_password(password),
        'is_admin': is_admin,
        'created_at': datetime.datetime.utcnow(),
    }
    result = db.users.insert_one(user)
    user['_id'] = str(result.inserted_id)
    user.pop('password')
    return user

def authenticate_user(email: str, password: str) -> dict:
    db = get_db()
    user = db.users.find_one({'email': email})
    if not user or not check_password(password, user['password']):
        raise ValueError('Invalid credentials')
    return user

def get_user_by_id(user_id: str) -> dict | None:
    db = get_db()
    try:
        user = db.users.find_one({'_id': ObjectId(user_id)})
        if user:
            user['_id'] = str(user['_id'])
            user.pop('password', None)
            if 'created_at' in user:
                user['created_at'] = user['created_at'].isoformat()
        return user
    except Exception:
        return None


# ── CRUD admin ────────────────────────────────────────────────────────────────

def list_users(page: int = 1, per_page: int = 20, search: str = '') -> dict:
    db = get_db()
    query: dict = {}
    if search:
        import re
        pat = re.escape(search.strip()[:80])
        query['$or'] = [
            {'email': {'$regex': pat, '$options': 'i'}},
            {'name':  {'$regex': pat, '$options': 'i'}},
        ]
    skip = (page - 1) * per_page
    fetch = per_page + 1
    cursor = (
        db.users
        .find(query, {'password': 0})
        .sort('created_at', -1)
        .skip(skip)
        .limit(fetch)
    )
    docs = []
    for doc in cursor:
        doc['_id'] = str(doc['_id'])
        if 'created_at' in doc:
            doc['created_at'] = doc['created_at'].isoformat()
        docs.append(doc)
    has_next = len(docs) > per_page
    return {
        'page': page,
        'per_page': per_page,
        'has_next': has_next,
        'has_prev': page > 1,
        'results': docs[:per_page],
    }


def update_user(user_id: str, name: str | None = None, email: str | None = None, is_admin: bool | None = None) -> dict:
    db = get_db()
    fields: dict = {}
    if name is not None:
        name = name.strip()
        if not name:
            raise ValueError('El nombre no puede estar vacío.')
        fields['name'] = name
    if email is not None:
        email = email.strip().lower()
        if not email:
            raise ValueError('El email no puede estar vacío.')
        if db.users.find_one({'email': email, '_id': {'$ne': ObjectId(user_id)}}):
            raise ValueError('Ese email ya está en uso por otro usuario.')
        fields['email'] = email
    if is_admin is not None:
        fields['is_admin'] = bool(is_admin)
    if not fields:
        raise ValueError('No se proporcionó ningún campo para actualizar.')
    db.users.update_one({'_id': ObjectId(user_id)}, {'$set': fields})
    updated = get_user_by_id(user_id)
    if not updated:
        raise ValueError('Usuario no encontrado tras la actualización.')
    return updated


def delete_user(user_id: str) -> bool:
    db = get_db()
    result = db.users.delete_one({'_id': ObjectId(user_id)})
    return result.deleted_count > 0


def admin_reset_password(user_id: str, new_password: str) -> None:
    if len(new_password) < 6:
        raise ValueError('La contraseña debe tener al menos 6 caracteres.')
    db = get_db()
    if not db.users.find_one({'_id': ObjectId(user_id)}):
        raise ValueError('Usuario no encontrado.')
    db.users.update_one(
        {'_id': ObjectId(user_id)},
        {'$set': {'password': hash_password(new_password)}},
    )


# ── Perfil propio ─────────────────────────────────────────────────────────────

def update_own_profile(user_id: str, name: str | None = None, email: str | None = None) -> dict:
    db = get_db()
    fields: dict = {}
    if name is not None:
        name = name.strip()
        if not name:
            raise ValueError('El nombre no puede estar vacío.')
        fields['name'] = name
    if email is not None:
        email = email.strip().lower()
        if db.users.find_one({'email': email, '_id': {'$ne': ObjectId(user_id)}}):
            raise ValueError('Ese email ya está en uso.')
        fields['email'] = email
    if fields:
        db.users.update_one({'_id': ObjectId(user_id)}, {'$set': fields})
    return get_user_by_id(user_id)


def change_own_password(user_id: str, current_password: str, new_password: str) -> None:
    db = get_db()
    user = db.users.find_one({'_id': ObjectId(user_id)})
    if not user or not check_password(current_password, user['password']):
        raise ValueError('Contraseña actual incorrecta.')
    if len(new_password) < 6:
        raise ValueError('La nueva contraseña debe tener al menos 6 caracteres.')
    db.users.update_one(
        {'_id': ObjectId(user_id)},
        {'$set': {'password': hash_password(new_password)}},
    )