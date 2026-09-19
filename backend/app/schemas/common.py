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
