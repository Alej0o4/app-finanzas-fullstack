"""Schemas compartidos entre dominios (Fase 25 §25.2).

`PaginatedResponse[T]` y la política de contraseñas (`_COMMON_PASSWORDS` /
`_validate_password_strength`) son los únicos elementos que cruzan dominios
(Hallazgo 6): `users.py` y `auth.py` importan la validación de contraseña desde
acá en vez de duplicar la lista.
"""

from pydantic import BaseModel


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


# --- RANGO DE LOS CAMPOS DE DINERO (Fase 31, Decisión B3) ---
# Ligado a `Numeric(14, 2)` de `models.py`: 14 dígitos totales, 2 de ellos decimales,
# así que 12 dígitos enteros como máximo. Los cuatro campos de entrada con dinero
# (`TransactionBase.amount`, `AccountCreate.balance`, `UserProfileUpdate.monthly_income`,
# `BudgetBase.amount_limit`) usan esta constante en vez de repetir el número — un valor
# que desbordara la columna sin este límite llegaba hasta el `commit()` y volvía como un
# 500 en texto plano (`DataError` sin capturar), no como un 422 de validación (QA-015).
MAX_DIGITS_MONEY = 14


# --- MONEDA (QA-025) ---
# `Account.currency`, `Transaction.currency`, `Budget.currency` y `User.preferred_currency`
# son `String(3)` en `models.py`: un valor más largo ("zzzzzz") llegaba hasta el INSERT y
# volvía como un 500 en texto plano (`StringDataRightTruncation` es un `DataError`), no como
# un 422 de validación — el mismo modo de fallo que QA-015 ya resolvió para el rango de los
# campos de dinero.
#
# El patrón va SOLO en los schemas de REQUEST. Los de response no lo llevan a propósito: si
# una fila heredada tuviera una moneda fuera de patrón, el `ResponseValidationError` dejaría
# ese endpoint en 500 para siempre — exactamente la lección de QA-023 con
# `Budget.month`/`year` (datos que una versión anterior dejó entrar sin validar).
CURRENCY_PATTERN = r"^[A-Z]{3}$"


# --- NOMBRES DE TEXTO (QA-028) ---
def nombre_sin_espacios(nombre: str) -> str:
    """Recorta el nombre y rechaza el que queda vacío.

    `min_length=1` no alcanza: `"   "` tiene longitud 3 y pasaba el filtro, dejando
    categorías y cuentas cuyo nombre en la UI es indistinguible de otro. Se usa como
    `field_validator("name", mode="after")` (el tipo `str` ya está garantizado ahí, y
    `min_length`/`max_length` del `Field` siguen corriendo antes).
    """
    recortado = nombre.strip()
    if not recortado:
        raise ValueError("El nombre no puede estar vacío.")
    return recortado


# --- POLÍTICA DE CONTRASEÑAS (Fase 7, §2.3) ---
# NIST 800-63B recomienda priorizar longitud sobre complejidad artificial — por eso
# min_length=10 en vez de reglas de "1 mayúscula + 1 símbolo", y una lista corta de
# contraseñas comunes en vez de zxcvbn u otra dependencia externa.
_COMMON_PASSWORDS = {
    "12345678",
    "123456789",
    "1234567890",
    "password",
    "password1",
    "password123",
    "qwerty123",
    "qwerty1234",
    "qwerty123456",
    "abc123456",
    "abcd1234",
    "letmein123",
    "welcome123",
    "admin1234",
    "admin123",
    "iloveyou1",
    "123123123",
    "monkey123",
    "football1",
    "baseball1",
    "dragon123",
    "master123",
    "hello1234",
    "freedom123",
    "whatever1",
    "trustno123",
    "superman1",
    "1q2w3e4r5t",
    "zaq12wsx1",
    "qazwsx123",
    "passw0rd1",
    "changeme1",
    "letmein12",
    "sunshine1",
    "princess1",
    "shadow123",
    "starwars1",
    "batman123",
    "michael123",
    "computer1",
}


def _validate_password_strength(value: str) -> str:
    if value.isdigit() or value.isalpha():
        raise ValueError("La contraseña debe combinar letras y números.")
    if value.lower() in _COMMON_PASSWORDS:
        raise ValueError("Esta contraseña es demasiado común.")
    return value
