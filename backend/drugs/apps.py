import os

from django.apps import AppConfig


class DrugsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "drugs"

    def ready(self):
        # Arranque automático del poblado de embeddings ChemBERTa (idempotente, en 2º plano)
        # para que la similitud por embedding quede SIEMPRE lista al correr el server.
        # Solo bajo `runserver` (proceso servidor real: RUN_MAIN='true'), nunca en tests,
        # migraciones u otros comandos. En producción se dispara desde config/wsgi.py|asgi.py.
        if os.environ.get("RUN_MAIN") == "true":
            try:
                from config.services.chemberta_index import autostart_in_background
                autostart_in_background()
            except Exception:
                pass  # nunca romper el arranque por esto
