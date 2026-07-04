"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()

# Autostart de embeddings ChemBERTa (idempotente, en segundo plano). Ver config/wsgi.py.
try:
    from config.services.chemberta_index import autostart_in_background
    autostart_in_background()
except Exception:
    pass
