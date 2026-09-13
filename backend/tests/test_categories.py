"""Tests de categorías de Fase 18 (categorías personalizables).

Alcance:
- §18.1: ampliación del pool de categorías default (11 → 19).
- §18.2: pre-siembra de `hidden_categories` en el registro.
- §18.3: categorías "ocultas para mí" (modelo, endpoints POST/DELETE /hide, `is_hidden`).

El fixture `client` del conftest NO dispara el lifespan, así que
`seed_default_categories()` no corre en tests (y usaría SessionLocal → DB real). Los
tests que necesitan categorías de sistema las siembran DIRECTAMENTE contra `db_session`
iterando la constante `DEFAULT_CATEGORIES` (ver `seed_system_categories` abajo).
"""

import pytest
from fastapi.testclient import TestClient

from app.api.transactions import _normalizar_nombre_categoria
from app.core.default_categories import DEFAULT_CATEGORIES
from app.models import models


def _get_categorias(client: TestClient, headers: dict) -> list[dict]:
    response = client.get("/api/v1/categories/", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def seed_system_categories(db_session):
    """Inserta en la sesión las filas `models.Category` del `DEFAULT_CATEGORIES`
    completo (`user_id=None`), con `db_session.commit()`.

    Los tests no pueden depender de `seed_default_categories()` del lifespan (no corre
    bajo `TestClient` sin `with`, ver conftest.py), así que el seed manual contra la
    sesión es la vía canónica para las categorías de sistema en este archivo.
    """

    def _seed() -> None:
        for category_data in DEFAULT_CATEGORIES:
            db_session.add(
                models.Category(
                    name=category_data["name"],
                    type=category_data["type"],
                    icon=category_data["icon"],
                    user_id=None,
                )
            )
        db_session.commit()

    return _seed


class TestPoolDefaultCategories:
    """§18.1 — ampliar el pool de categorías default (11 → 19)."""

    def test_get_categories_returns_all_19_system_categories(self, client, auth_headers, seed_system_categories):
        seed_system_categories()

        categorias = _get_categorias(client, auth_headers)

        assert len(categorias) == len(DEFAULT_CATEGORIES) == 19
        assert all(categoria["user_id"] is None for categoria in categorias)

        nombres = {categoria["name"] for categoria in categorias}
        assert len(nombres) == 19  # sin duplicados de nombre

    def test_default_categories_have_no_normalized_name_type_collisions(self):
        """Ninguna colisión por (name, type) normalizado (case/acento-insensible) dentro del
        `DEFAULT_CATEGORIES` completo — misma comparación que usa
        `_normalizar_nombre_categoria` (`transactions.py:26-30`)."""
        pares = [(_normalizar_nombre_categoria(c["name"]), c["type"]) for c in DEFAULT_CATEGORIES]
        assert len(pares) == len(set(pares))
