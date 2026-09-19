"""Excepciones de dominio, desacopladas de HTTPException (Fase 25 §25.3 — piloto).

Un router captura una condición de negocio (`la cuenta no existe o no es tuya`) sin
tener que saber en el mismo lugar que eso es un 404 HTTP — el mapeo status/detail vive
acá, una sola vez, y un único exception handler en main.py lo traduce a respuesta HTTP.
Piloto acotado a transactions.py (Decisión X1): no reemplaza los 61 `raise
HTTPException` restantes de los otros 10 routers en esta fase.
"""


class DomainError(Exception):
    """Base de cualquier error de reglas de negocio. Nunca se instancia directo."""

    status_code = 400
    detail = "Error de dominio."

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.detail
        super().__init__(self.detail)


class AccountNotFoundError(DomainError):
    status_code = 404
    detail = "La cuenta especificada no existe o no te pertenece."


class CategoryNotFoundError(DomainError):
    status_code = 404
    detail = "La categoría especificada no existe o no tienes permisos para usarla."
