"""Excepciones de dominio, desacopladas de HTTPException.

Un router captura una condición de negocio (`la cuenta no existe o no es tuya`) sin
tener que saber en el mismo lugar que eso es un 404 HTTP — el mapeo status/detail vive
acá, una sola vez, y un único exception handler en main.py lo traduce a respuesta HTTP.
Nacido en Fase 25 §25.3 como piloto acotado a transactions.py; extendido en Fase 28 a
los 10 routers restantes de `app/api/` con una taxonomía genérica por status code.
"""

from typing import Any


class DomainError(Exception):
    """Base de cualquier error de reglas de negocio. Nunca se instancia directo."""

    status_code = 400
    detail: Any = "Error de dominio."

    def __init__(self, detail: Any = None):
        self.detail = detail if detail is not None else self.detail
        super().__init__(self.detail)


class BadRequestError(DomainError):
    status_code = 400


class UnauthorizedError(DomainError):
    status_code = 401


class ForbiddenError(DomainError):
    status_code = 403


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409


class ValidationError(DomainError):
    status_code = 422


class InternalServerError(DomainError):
    # 🔧 No está en el diseño original del spec de Fase 28 (que solo cubre 400-422): hace
    # falta para los ~5 sitios existentes con status_code=500 (errores internos ya
    # capturados por un except genérico, no reglas de negocio) en transactions.py y
    # dashboard.py — sin esta clase esos sitios no podrían migrar y el conteo final de
    # `raise HTTPException` no llegaría a cero.
    status_code = 500


class ServiceUnavailableError(DomainError):
    # 🔧 Mismo motivo que InternalServerError: falta en el spec, pero auth.py tiene un
    # sitio con status_code=503 (login con Google no configurado en el entorno).
    status_code = 503


class AccountNotFoundError(DomainError):
    status_code = 404
    detail = "La cuenta especificada no existe o no te pertenece."


class CategoryNotFoundError(DomainError):
    status_code = 404
    detail = "La categoría especificada no existe o no tienes permisos para usarla."
