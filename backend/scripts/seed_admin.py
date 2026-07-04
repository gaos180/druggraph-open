import os, sys
# El script vive en backend/scripts/; añade backend/ al path para importar config y users.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django; django.setup()
from users.services import create_user

try:
    user = create_user('admin@druggraph.dev', 'Admin', 'admin1234', is_admin=True)
    print(f"Admin creado: {user['email']}")
except ValueError as e:
    print(f"Admin: {e}")

try:
    demo = create_user('demo@druggraph.dev', 'Usuario Demo', 'demo1234', is_admin=False)
    print(f"Demo creado: {demo['email']}")
except ValueError as e:
    print(f"Demo: {e}")