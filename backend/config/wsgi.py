"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

# Autostart de embeddings ChemBERTa en producción (gunicorn/uwsgi). Idempotente y en
# segundo plano; no hace nada si torch/transformers no están instalados. En `runserver`
# lo dispara drugs.apps.DrugsConfig.ready().
try:
    from config.services.chemberta_index import autostart_in_background
    autostart_in_background()
except Exception:
    pass
