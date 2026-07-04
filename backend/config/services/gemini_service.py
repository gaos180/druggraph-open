"""
gemini_service.py — Cliente REST de Google Gemini para la reportería IA de DrugGraph.

Genera informes en lenguaje natural a partir de los resultados de los análisis
(sandbox, reposicionamiento, toxicidad, DEG, DDI). No usa SDK: llama directamente
a la API `generateContent` con `requests` (misma dependencia que string/kegg_service).

Configuración (settings / env):
    GEMINI_API_KEY  — clave de la API (obligatoria; sin ella el servicio no está disponible).
    GEMINI_MODEL    — modelo por defecto (default 'gemini-2.5-flash').

Buenas prácticas replicadas de string_service/kegg_service:
    - flag REQUESTS_OK / disponibilidad,
    - rate limiter global con lock,
    - timeout y manejo de errores explícito.

Dependencias: pip install requests
"""

import logging
import threading
import time

from django.conf import settings

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

log = logging.getLogger(__name__)

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Modelos permitidos (whitelist). Solo flash: gemini-2.5-pro no está disponible en el
# nivel gratuito de la API, así que cualquier petición se normaliza a flash.
ALLOWED_MODELS = ("gemini-2.5-flash",)
DEFAULT_MODEL = "gemini-2.5-flash"

HTTP_TIMEOUT = 120           # los informes pueden tardar
MIN_CALL_INTERVAL = 0.5      # cortesía: no martillar la API
MAX_OUTPUT_TOKENS = 8192     # holgado para que el informe no se corte a medio texto

# Reintentos ante errores transitorios de la API (sobrecarga / rate limit).
RETRY_STATUSES = (429, 500, 503)
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0          # segundos base; crece linealmente por intento

# Rate limiter global
_last_call = [0.0]
_rate_lock = threading.Lock()


class GeminiUnavailable(RuntimeError):
    """La API key no está configurada o el cliente HTTP no está disponible."""
    pass


class GeminiError(RuntimeError):
    """La API respondió con error o una respuesta inesperada."""
    pass


def is_configured() -> bool:
    """True si hay API key y `requests` disponible."""
    return bool(REQUESTS_OK and getattr(settings, "GEMINI_API_KEY", ""))


def resolve_model(model: str | None) -> str:
    """Normaliza el modelo pedido a uno de la whitelist (default si inválido/ausente)."""
    if model in ALLOWED_MODELS:
        return model
    default = getattr(settings, "GEMINI_MODEL", DEFAULT_MODEL)
    return default if default in ALLOWED_MODELS else DEFAULT_MODEL


def _rate_limit():
    with _rate_lock:
        elapsed = time.time() - _last_call[0]
        if elapsed < MIN_CALL_INTERVAL:
            time.sleep(MIN_CALL_INTERVAL - elapsed)
        _last_call[0] = time.time()


def generate(
    prompt: str,
    *,
    model: str | None = None,
    system_instruction: str | None = None,
    temperature: float = 0.25,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
) -> str:
    """
    Llama a Gemini `generateContent` y devuelve el texto generado.

    Lanza:
        GeminiUnavailable — si no hay key/`requests`.
        GeminiError       — si la API responde con error o formato inesperado.
    """
    if not is_configured():
        raise GeminiUnavailable(
            "Gemini no está configurado. Define GEMINI_API_KEY en el entorno."
        )

    resolved = resolve_model(model)
    url = f"{API_BASE}/{resolved}:generateContent"

    body: dict = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
            # gemini-2.5-flash activa "thinking" por defecto y esos tokens cuentan contra
            # maxOutputTokens, dejando el informe a medio texto. Lo desactivamos para que
            # todo el presupuesto de tokens vaya al texto del informe.
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    resp = None
    last_detail = ""
    for attempt in range(1, MAX_RETRIES + 1):
        _rate_limit()
        try:
            resp = requests.post(
                url,
                params={"key": settings.GEMINI_API_KEY},
                json=body,
                timeout=HTTP_TIMEOUT,
                headers={"Content-Type": "application/json"},
            )
        except requests.RequestException as exc:
            log.error("Gemini request falló: %s", exc)
            raise GeminiError(f"No se pudo contactar a Gemini: {exc}")

        if resp.status_code == 200:
            break

        last_detail = resp.text[:500]
        # Errores transitorios (sobrecarga / rate limit): reintentar con backoff.
        if resp.status_code in RETRY_STATUSES and attempt < MAX_RETRIES:
            wait = RETRY_BACKOFF * attempt
            log.warning("Gemini HTTP %s (intento %s/%s), reintentando en %.1fs",
                        resp.status_code, attempt, MAX_RETRIES, wait)
            time.sleep(wait)
            continue

        log.error("Gemini HTTP %s: %s", resp.status_code, last_detail)
        raise GeminiError(f"Gemini respondió {resp.status_code}: {last_detail}")

    try:
        data = resp.json()
    except ValueError as exc:
        raise GeminiError(f"Respuesta de Gemini no es JSON válido: {exc}")

    # Bloqueo por filtros de seguridad
    if not data.get("candidates"):
        feedback = data.get("promptFeedback", {})
        raise GeminiError(
            f"Gemini no devolvió candidatos (posible bloqueo). Detalle: {feedback}"
        )

    candidate = data["candidates"][0]
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts).strip()

    if not text:
        finish = candidate.get("finishReason", "desconocido")
        raise GeminiError(f"Gemini devolvió texto vacío (finishReason={finish}).")

    return text
