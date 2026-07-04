# 08 — Conceptos Transversales

## 8.1 Autenticación y Autorización

### JWT Flow

1. El usuario se autentica vía `POST /api/auth/login/` con email y contraseña.
2. Django verifica la contraseña con `bcrypt`; si coincide, genera un JWT firmado con `JWT_SECRET` (HS256).
3. El token incluye `{ user_id, email, is_admin, exp }` en el payload.
4. El frontend almacena el token en `localStorage['dg_token']`.
5. `api/client.ts` adjunta el token en cada request como `Authorization: Bearer <token>`.
6. `MongoJWTAuthentication` decodifica el token, carga el usuario desde MongoDB, y popula `request.user` con un `SimpleUser`.

### Protección de endpoints

- Todos los endpoints de datos requieren autenticación (configurado en `DEFAULT_AUTHENTICATION_CLASSES`).
- Los endpoints de auth (`/register`, `/login`) usan `AllowAny` explícitamente.
- El frontend redirige a `/login` ante cualquier respuesta 401.

---

## 8.2 Manejo de Errores

### Convención de respuestas de error

| Código | Situación | Cuerpo |
|--------|-----------|--------|
| 400 | Parámetro inválido o faltante | `{"error": "descripción"}` |
| 401 | Sin token o token inválido/expirado | `{"error": "..."}` |
| 404 | Entidad no encontrada | `{"error": "Fármaco 'X' no encontrado."}` |
| 503 | Dependencia externa no disponible | `{"error": "Neo4j GDS no disponible."}` |
| 500 | Error inesperado en el servidor | `{"error": "Error interno."}` |

### Degradación elegante

Los módulos de servicios externos capturan sus propias excepciones y retornan `None` o listas vacías. Los endpoints de pathways pueden devolver respuesta parcial (ej. `"indirect": null` si STRING falla, pero `"pathways"` completo si KEGG sí responde).

---

## 8.3 Caché

| Módulo | Tipo | TTL | Clave |
|--------|------|-----|-------|
| `string_service.py` | In-memory dict | 6 horas | `partners:{species}:{score}:{ids}` |
| `kegg_service.py` | In-memory dict | 24 horas | `u2k:{uniprot}`, `g2p:{gene}`, `pname:{pid}` |

La caché es por proceso (no compartida entre workers de Gunicorn). En producción multi-worker se debería migrar a Redis.

---

## 8.4 Logging

Se usa el sistema estándar `logging` de Python. Cada módulo de servicio tiene su propio logger:

```python
log = logging.getLogger(__name__)
```

Los errores de APIs externas (STRING timeout, KEGG 404) se registran con `log.error()` o `log.warning()` pero no se propagan como excepciones al cliente. El nivel de log se configura en `settings.py`.

---

## 8.5 Seguridad del Sandbox

Los nodos `:SandboxDrug` creados en Neo4j tienen las siguientes salvaguardas:

- **Namespace separado**: la etiqueta `:SandboxDrug` los distingue de los nodos `:Drug` reales.
- **Endpoint de limpieza**: `DELETE /api/drugs/sandbox/{sandbox_id}/` elimina el nodo y todas sus relaciones.
- **Limpieza automática**: `sandbox_service.py` incluye una función `cleanup_old_sandbox_nodes()` que elimina nodos con más de 30 minutos de antigüedad.
- **No persisten datos de usuario**: los nodos solo almacenan el SMILES, el nombre del compuesto y el fingerprint; no hay información personal.

---

## 8.6 CORS y Seguridad HTTP

- `django-cors-headers` permite requests desde `localhost:3000` (configurado en `CORS_ALLOWED_ORIGINS`).
- En producción, `CORS_ALLOWED_ORIGINS` debe restringirse al dominio real del frontend.
- El `JWT_SECRET` debe rotarse antes del despliegue a producción (el default es un placeholder conocido).

---

## 8.7 Rate Limiting de APIs Externas

Para cumplir con las políticas de uso de STRING y KEGG:

- **STRING**: espera mínimo 1 segundo entre llamadas (`MIN_CALL_INTERVAL = 1.0` en `string_service.py`).
- **KEGG**: espera mínimo 0.34 segundos entre llamadas (~3 req/s).
- Ambos usan un lock de threading para serializar las llamadas en entornos multi-hilo.
- La caché reduce el número de llamadas reales a las APIs.
