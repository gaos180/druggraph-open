from pathlib import Path
import os
from dotenv import load_dotenv



BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')   # cargar .env ANTES de leer las variables

_DEV_SECRET = 'druggraph-dev-secret-change-in-production'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', _DEV_SECRET)
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]

# Nunca usar el SECRET_KEY de desarrollo tal cual: si no se define uno propio, se genera uno
# aleatorio en memoria (no crashea el dev). En producción DEFINE DJANGO_SECRET_KEY para que las
# sesiones/admin persistan entre reinicios.
if SECRET_KEY == _DEV_SECRET:
    import secrets
    SECRET_KEY = secrets.token_urlsafe(64)
    if not DEBUG:
        import warnings
        warnings.warn("DJANGO_SECRET_KEY no definido: usando una clave aleatoria efímera. "
                      "Defínelo en el entorno para producción.")

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'drf_spectacular',
    'users',
    'drugs',
]
 
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
]
 
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request']}}]
WSGI_APPLICATION = 'config.wsgi.application'

# ── Bases de datos ────────────────────────────────────────────────────────────
# DrugGraph no usa el ORM de Django para el dominio: los datos viven en MongoDB
# (documentos) y Neo4j (grafo), accedidos por los servicios singleton de
# config/services/. El alias "default" (sqlite) lo exige Django para admin/
# sessions; no almacena datos del dominio.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    },
}

# Motores NoSQL del dominio, declarados en el mismo estilo (clave ENGINE) para tener
# la configuración de conexión de MongoDB y Neo4j centralizada en un único lugar.
# Se mantienen FUERA de DATABASES a propósito: el test runner de Django intenta cargar
# el backend del ORM de cada alias dentro de DATABASES, y 'pymongo'/'neo4j' no lo son.
# Los consume config/services/ (get_db, get_driver), nunca django.db.connections.
# NOTA: los defaults apuntan al stack Docker AISLADO de DrugGraph Open
# (Mongo 27018, Neo4j Bolt 7688) para no colisionar con un DrugGraph original
# corriendo en la misma máquina (27017 / 7687).
DATABASES_NOSQL = {
    'mongodb': {
        'ENGINE': 'pymongo',
        'URI':  os.environ.get('MONGODB_URI', 'mongodb://localhost:27018/'),
        'NAME': os.environ.get('MONGODB_DB', 'druggraph_open'),
    },
    'neo4j': {
        'ENGINE': 'neo4j',
        'URI':      os.environ.get('NEO4J_URI', 'bolt://localhost:7688'),
        'USER':     os.environ.get('NEO4J_USER', 'neo4j'),
        'PASSWORD': os.environ.get('NEO4J_PASSWORD', 'druggraphopen123'),
    },
    # Capa relacional de STAGING para la ingesta open-source (DrugCentral / ChEMBL
    # se restauran aquí como dumps Postgres nativos; el ETL proyecta a Mongo/Neo4j).
    # NO se usa en runtime de la app — solo scripts/ingest/. Ver config/services/postgres.py.
    'postgres': {
        'ENGINE': 'psycopg',
        'HOST':     os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': int(os.environ.get('POSTGRES_PORT', '5433')),
        'USER':     os.environ.get('POSTGRES_USER', 'druggraph'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'druggraphopen123'),
        'NAME':     os.environ.get('POSTGRES_DB', 'staging'),
    },
}

# Alias planos derivados de DATABASES_NOSQL (retrocompat: algunos scripts standalone y
# código previo leen estas constantes directamente).
MONGODB_URI = DATABASES_NOSQL['mongodb']['URI']
MONGODB_DB  = DATABASES_NOSQL['mongodb']['NAME']
NEO4J_URI      = DATABASES_NOSQL['neo4j']['URI']
NEO4J_USER     = DATABASES_NOSQL['neo4j']['USER']
NEO4J_PASSWORD = DATABASES_NOSQL['neo4j']['PASSWORD']
POSTGRES = DATABASES_NOSQL['postgres']

# ── Esquema de identificadores abierto ────────────────────────────────────────
# DrugGraph Open no usa IDs de DrugBank. El identificador primario de cada fármaco
# es un ID estable derivado de la fuente open-source (por defecto, DrugCentral:
# "DCxxxxx"). El campo interno del documento sigue llamándose 'drugbank-id' por
# compatibilidad con el código heredado, pero contiene el ID abierto. Estos ajustes
# controlan el prefijo aceptado por los validadores de formato.
OPEN_ID_PREFIX = os.environ.get('OPEN_ID_PREFIX', 'DC')


# BLAST (requiere BLAST+ instalado y base de datos construida con build_blast_db.py)
_BLAST_DB_DEFAULT  = str(BASE_DIR.parent / 'data' / 'blast_db' / 'druggraph_targets')
_BLAST_MAP_DEFAULT = str(BASE_DIR.parent / 'data' / 'blast_db' / 'druggraph_targets.map.json')
BLAST_DB_PATH  = os.environ.get('BLAST_DB_PATH', _BLAST_DB_DEFAULT)
BLAST_MAP_PATH = os.environ.get('BLAST_MAP_PATH', _BLAST_MAP_DEFAULT)
BLAST_THREADS  = int(os.environ.get('BLAST_THREADS', '2'))

# JWT
JWT_SECRET = os.environ.get('JWT_SECRET', 'druggraph-jwt-secret-change-in-production')
JWT_EXPIRY_HOURS = 24

# Gemini (reportería IA — opcional; sin GEMINI_API_KEY el endpoint devuelve 503)
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL   = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
 
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['users.authentication.MongoJWTAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # Rate-limiting: protege los endpoints caros (docking, informe Gemini con costo, AlphaFold/
    # ChEMBL/UniProt que pueden banear la IP) contra abuso/DoS. Configurable por env.
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.environ.get('THROTTLE_ANON', '30/min'),
        'user': os.environ.get('THROTTLE_USER', '120/min'),
    },
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'DrugGraph Open API',
    'DESCRIPTION': 'API de DrugGraph Open: fármacos, dianas, grafo molecular y herramientas analíticas, sobre datos 100% open-source (DrugCentral, ChEMBL, Open Targets, PubChem, UniProt, CTD).',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}
 
CORS_ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
CORS_ALLOW_CREDENTIALS = True

# ── Cookie settings ───────────────────────────────────────────────────────────
# dg_auth es una cookie HttpOnly gestionada manualmente (no usa el sistema de
# sesiones de Django). Estos ajustes aplican a las cookies de sesión/CSRF de
# Django — se definen aquí para coherencia y preparar la transición a HTTPS.
SESSION_COOKIE_SECURE   = False  # True en producción (HTTPS)
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE      = False  # True en producción (HTTPS)
CSRF_COOKIE_SAMESITE    = 'Lax'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'