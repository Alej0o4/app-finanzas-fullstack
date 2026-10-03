"""Schemas del dominio presupuestos (Fase 25 §25.2)."""

from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import CURRENCY_PATTERN, MAX_DIGITS_MONEY


# --- PRESUPUESTOS ---
class BudgetBase(BaseModel):
    amount_limit: Decimal = Field(
        ..., gt=0, decimal_places=2, max_digits=MAX_DIGITS_MONEY, description="El presupuesto debe ser mayor a cero"
    )
    # `models.py` lo declara como `String(3)`: un "zzzzzz" pasaba el schema, llegaba al
    # INSERT y volvía como un 500 en texto plano (`StringDataRightTruncation` es un
    # `DataError`), no como un 422 (QA-025, mismo modo de fallo que el rango de dinero de
    # QA-015). El patrón va solo en el schema de REQUEST — ver el comentario de
    # `CURRENCY_PATTERN` en `app/schemas/common.py`.
    currency: str = Field("COP", pattern=CURRENCY_PATTERN)
    month: int = Field(..., ge=1, le=12, description="Mes válido entre 1 y 12")
    year: int = Field(..., ge=2020, le=2100)
    category_id: int
    is_recurring: bool = False


class BudgetCreate(BudgetBase):
    pass


class BudgetResponse(BaseModel):
    """A propósito NO hereda de `BudgetBase` (QA-023), aunque declare los mismos campos.

    `BudgetResponse` heredaba los `ge`/`le` de `BudgetBase.month`/`year`, así que una fila
    con un período fuera de rango — basura que dejó entrar una versión anterior del endpoint
    al no validar el query param — no se podía serializar: `ResponseValidationError` en el
    `GET /budgets/`, o sea un **500 permanente** que dejaba la página de presupuestos en
    skeleton para siempre, sin importar cuántas veces se recargara. Un response model que
    valida convierte cualquier fila heredada en una bomba de 500; las restricciones
    (`gt=0`, `decimal_places`/`max_digits`, el patrón de la moneda, el rango del período)
    son de la FRONTERA DE ENTRADA y quedan en `BudgetBase`/`BudgetCreate`, que es lo que
    valida `POST /budgets/` y `PUT /budgets/{id}`.

    Los campos son los mismos de `BudgetBase` y en el mismo orden (el orden de las claves
    del JSON no cambia), pero SIN validators. `amount_limit` va como `Decimal` pelado: los
    valores salen de `Numeric(14,2)` y no pueden desbordar, mientras que un `gt=0` acá sí
    podría tumbar el listado entero con una fila rara — el mismo criterio de no validar en
    el response que arriba, aplicado también a un campo que hoy es inofensivo.
    """

    amount_limit: Decimal
    currency: str
    month: int
    year: int
    category_id: int
    is_recurring: bool
    id: int
    user_id: int

    class Config:
        from_attributes = True
