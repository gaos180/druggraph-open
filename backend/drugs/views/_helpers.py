"""_helpers.py — Helpers compartidos por las vistas del paquete drugs."""


def _is_admin(request) -> bool:
    return bool(
        getattr(request.user, 'is_authenticated', False)
        and getattr(request.user, 'is_admin', False)
    )
