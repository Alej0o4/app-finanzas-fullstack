# Fase 28 — Extender `DomainError` a los 10 routers restantes

**Estado**: planeada 2026-09-19. `app/core/exceptions.py` nació en Fase 25 §25.3 como **piloto
acotado** a 4 sitios de `transactions.py` (`docs/specs/fase_25_spec.md`) — decisión explícita de
no reescribir los ~61 `raise HTTPException` restantes en esa fase. La auditoría 2026-09-19
(`CODE_REVIEW.md` §2.2, §2.4) confirma que sigue siendo el mayor bloque de acoplamiento
HTTP↔dominio del backend: 65 `raise HTTPException` repartidos en 10 routers (incluye los 14 que
quedan en `transactions.py` mismo, fuera del piloto original). La propia auditoría recomienda
hacerlo "oportunista, router por router" en vez de como fase dedicada — este spec revierte esa
recomendación a pedido explícito del dueño del producto: cerrar la deuda de arquitectura/
modularidad ahora, antes de retomar el backlog de features de `docs/ROADMAP.md`.

## Objetivo

Todo router de `app/api/` levanta excepciones de dominio (`DomainError` y subclases) en vez de
`HTTPException` directo, salvo los casos que genuinamente pertenecen a la capa HTTP (parsing de
`Request`, no una regla de negocio). Cero cambio de contrato de API: mismo `status_code`, mismo
`detail` (string o dict), verificado por la suite de tests existente.

## Diseño

`app/core/exceptions.py` pasa de 2 subclases puntuales a una taxonomía genérica por status code,
siguiendo el mismo patrón ya establecido (`status_code` de clase + `detail` de clase +
constructor que acepta override):

```python
class DomainError(Exception):
    status_code = 400
    detail: Any = "Error de dominio."  # 🔧 amplía de `str | None` a `Any`: al menos un caso real
                                          # (auth.py, EMAIL_NOT_VERIFIED) usa detail=dict, no str.
    def __init__(self, detail: Any = None): ...

class BadRequestError(DomainError):        # 400 — reemplaza la mayoría de los 400 genéricos
    status_code = 400

class UnauthorizedError(DomainError):      # 401
    status_code = 401

class ForbiddenError(DomainError):         # 403
    status_code = 403

class NotFoundError(DomainError):          # 404 — genérico
    status_code = 404

class ConflictError(DomainError):          # 409 — choques de unicidad (ej. budget duplicado)
    status_code = 409

class ValidationError(DomainError):        # 422 — si algún sitio actual usa 422 fuera de Pydantic
    status_code = 422
```

`AccountNotFoundError`/`CategoryNotFoundError` (ya existentes, usadas en `transactions.py`) se
mantienen tal cual — no hace falta que hereden de `NotFoundError` en vez de `DomainError`
directamente, evitar el churn de tocar esos 4 sitios ya migrados sin necesidad.

Cada `raise HTTPException(status_code=X, detail=Y)` se traduce 1:1 a `raise <Clase>(Y)` con la
clase cuyo `status_code` de default sea `X` — nunca se inventa un mensaje nuevo ni se cambia un
status code existente. Donde `Y` es un dict (caso `EMAIL_NOT_VERIFIED` en `auth.py`), se pasa el
dict igual.

`_domain_error_handler` en `main.py` no cambia — ya devuelve `{"detail": exc.detail}`, shape
idéntico al de `HTTPException`.

## Alcance — routers a migrar (65 sitios totales, conteo 2026-09-19)

| Router | `raise HTTPException` a migrar |
|---|---|
| `transactions.py` | 14 (quedan tras los 4 ya migrados en Fase 25) |
| `auth.py` | 12 |
| `accounts.py` | 8 |
| `categories.py` | 8 |
| `budgets.py` | 7 |
| `users.py` | 3 |
| `dashboard.py` | 3 |
| `api_keys.py` | 2 |
| `push.py` | 2 |
| `notifications.py` | 2 |

`preferences.py` no tiene ninguno — sin cambios.

## Fuera de alcance

- No se toca la firma pública de ningún endpoint ni `backend/docs/API_REFERENCE.md` /
  `frontend/docs/API_CONTRACT.md` — el shape de error no cambia.
- No se inventan nuevos códigos de error ni se homologan mensajes entre routers — cada sitio
  conserva su `detail` exacto, aunque haya inconsistencias preexistentes entre routers (eso sería
  una decisión de producto/UX distinta, no arquitectura).
- `HTTPException` importado por FastAPI/Starlette internamente no se toca; solo los `raise`
  explícitos en `app/api/*.py`.

## Corrección de precisión (post-implementación, 2026-09-19)

La taxonomía de arriba (400–422) no cubría todos los sitios reales: 6 sitios usan
`status_code=500` (errores internos ya capturados por un `except` genérico en `transactions.py`,
`dashboard.py`, `users.py` — no reglas de negocio) y 2 usan `status_code=503` (`auth.py`/
`push.py`, Google/VAPID sin configurar en el entorno). Se agregaron `InternalServerError` (500) y
`ServiceUnavailableError` (503) siguiendo el mismo patrón, para poder llegar a cero
`raise HTTPException` vivos en `app/api/` como pedía el objetivo de la fase. Ver
`docs/CHANGELOG.md` Fase 28 para el detalle.

## Verificación

- `cd backend && pytest` — los 251 tests existentes deben seguir en verde sin modificar ningún
  test (si un test falla, es señal de que un `status_code`/`detail` cambió sin querer, no que el
  test estaba mal).
- `ruff check . && ruff format .` limpio.
- Imports de `HTTPException`/`status` de FastAPI se retiran de cada archivo donde ya no se usen
  para otra cosa (algunos routers seguirán important `status` para `status_code=status.HTTP_204_...`
  en decoradores de ruta — eso se queda).
