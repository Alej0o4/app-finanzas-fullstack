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
from app.core.default_categories import BASE_REGISTRATION_CATEGORY_NAMES, DEFAULT_CATEGORIES
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


# ---------------------------------------------------------------------------
# §18.3 — Categorías "ocultas para mí".
# ---------------------------------------------------------------------------
# "Mercado" se usa como categoría de sistema de referencia en varios tests: además de
# existir en el pool ampliado de §18.1, está dentro de BASE_REGISTRATION_CATEGORY_NAMES
# (§18.2), lo que la mantiene `is_hidden: false` para un usuario recién registrado —
# aislando lo que cada test quiere probar de la pre-siembra del registro.
_CATEGORIA_SISTEMA_REFERENCIA = "Mercado"


def _categoria_de_sistema(db_session, nombre: str) -> models.Category:
    return (
        db_session.query(models.Category)
        .filter(models.Category.user_id.is_(None), models.Category.name == nombre)
        .first()
    )


def _post_hide(client: TestClient, headers: dict, category_id: int):
    return client.post(f"/api/v1/categories/{category_id}/hide", headers=headers)


def _delete_hide(client: TestClient, headers: dict, category_id: int):
    return client.delete(f"/api/v1/categories/{category_id}/hide", headers=headers)


class TestPreSiembraRegistro:
    """§18.2 — pre-siembra de `hidden_categories` en el registro (Decisión 18.2.1/Q2).

    Los tests registran un usuario NUEVO (`register_and_login` con email propio) DESPUÉS de
    sembrar las categorías de sistema, porque el pre-marcado ocurre dentro de
    `crear_usuario` (`users.py`) al leer las categorías de sistema ya presentes en la DB.
    """

    def test_registration_pre_seeds_hidden_for_non_base_system_categories(
        self, client, db_session, register_and_login, seed_system_categories
    ):
        seed_system_categories()
        usuario = register_and_login(email="nuevo-registro@example.com")

        categorias = _get_categorias(client, usuario["headers"])
        sistema = [c for c in categorias if c["user_id"] is None]
        assert len(sistema) == len(DEFAULT_CATEGORIES)

        ocultas = {c["name"] for c in sistema if c["is_hidden"]}
        visibles = {c["name"] for c in sistema if not c["is_hidden"]}

        assert ocultas == {c["name"] for c in DEFAULT_CATEGORIES} - BASE_REGISTRATION_CATEGORY_NAMES
        assert visibles == BASE_REGISTRATION_CATEGORY_NAMES

    def test_registration_pre_seed_does_not_hide_own_categories(
        self, client, db_session, register_and_login, seed_system_categories, make_category
    ):
        seed_system_categories()
        usuario = register_and_login(email="nuevo-propia@example.com")
        propia = make_category(usuario["headers"], name="Freelance", type="income")

        categorias = _get_categorias(client, usuario["headers"])
        propia_resp = next(c for c in categorias if c["id"] == propia["id"])
        assert propia_resp["is_hidden"] is False


class TestHiddenCategories:
    """§18.3 — endpoints POST/DELETE /hide e `is_hidden` en CategoryResponse.

    Todas las pruebas — incluida la por-usuario — se hacen con dos usuarios reales
    (`test_user`/`other_user`), no con una segunda sesión simulada, porque la ocultación
    es estrictamente por filas de `hidden_categories` scoped a `user_id`.
    """

    def test_hide_system_category_only_hides_for_that_user(
        self, client, test_user, other_user, db_session, seed_system_categories
    ):
        seed_system_categories()
        mercado = _categoria_de_sistema(db_session, _CATEGORIA_SISTEMA_REFERENCIA)
        assert mercado is not None

        response = _post_hide(client, test_user["headers"], mercado.id)
        assert response.status_code == 204

        categorias_owner = _get_categorias(client, test_user["headers"])
        owner_mercado = next(c for c in categorias_owner if c["id"] == mercado.id)
        assert owner_mercado["is_hidden"] is True

        # Un segundo usuario sigue viendo la misma categoría de sistema sin ocultar.
        categorias_otro = _get_categorias(client, other_user["headers"])
        otro_mercado = next(c for c in categorias_otro if c["id"] == mercado.id)
        assert otro_mercado["is_hidden"] is False

    def test_hide_own_category_hides_for_that_user_only(self, client, test_user, other_user, make_category):
        propia = make_category(test_user["headers"], name="Freelance", type="income")

        response = _post_hide(client, test_user["headers"], propia["id"])
        assert response.status_code == 204

        categorias_owner = _get_categorias(client, test_user["headers"])
        assert next(c for c in categorias_owner if c["id"] == propia["id"])["is_hidden"] is True

        # Las categorías propias de un usuario no son visibles para otro — el "por usuario"
        # de las propias queda garantizado por el ownership, no por la visibilidad: el otro
        # usuario simplemente no la ve en su listado.
        categorias_otro = {c["id"] for c in _get_categorias(client, other_user["headers"])}
        assert propia["id"] not in categorias_otro

    def test_hide_twice_is_idempotent_single_row(self, client, test_user, db_session, seed_system_categories):
        seed_system_categories()
        mercado = _categoria_de_sistema(db_session, _CATEGORIA_SISTEMA_REFERENCIA)

        assert _post_hide(client, test_user["headers"], mercado.id).status_code == 204
        assert _post_hide(client, test_user["headers"], mercado.id).status_code == 204

        filas = (
            db_session.query(models.HiddenCategory).filter_by(user_id=test_user["id"], category_id=mercado.id).count()
        )
        assert filas == 1  # la PK compuesta no puede duplicarse

    def test_delete_hide_on_not_hidden_category_is_noop(self, client, test_user, db_session, seed_system_categories):
        seed_system_categories()
        mercado = _categoria_de_sistema(db_session, _CATEGORIA_SISTEMA_REFERENCIA)

        response = _delete_hide(client, test_user["headers"], mercado.id)
        assert response.status_code == 204

        assert (
            db_session.query(models.HiddenCategory).filter_by(user_id=test_user["id"], category_id=mercado.id).count()
            == 0
        )

    def test_hide_category_owned_by_third_party_returns_404(self, client, test_user, other_user, make_category):
        categoria_del_otro = make_category(other_user["headers"], name="Privada de otro", type="expense")

        response = _post_hide(client, test_user["headers"], categoria_del_otro["id"])
        assert response.status_code == 404

    def test_put_on_own_hidden_category_reports_is_hidden_true(self, client, auth_headers, make_category):
        """Regresión del "Refinamiento" de la Decisión 18.3.2: un PUT sobre una categoría
        propia ya oculta debe reportar `is_hidden: true` — Antes del fix, Pydantic usaba el
        `default=False` del schema al serializar el objeto ORM (que no tiene `is_hidden`)."""
        propia = make_category(auth_headers, name="Ocultable", type="expense")
        assert _post_hide(client, auth_headers, propia["id"]).status_code == 204

        response = client.put(
            f"/api/v1/categories/{propia['id']}",
            json={"name": "Ocultable renombrada", "type": "expense"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["is_hidden"] is True

    def test_hidden_system_category_still_resolves_by_name_in_transactions(
        self, client, auth_headers, db_session, make_account, seed_system_categories
    ):
        """Regresión de la Decisión Q7/18.3.5: ocultar "Uber" no rompe la resolución por
        nombre de Fase 16 §16.2 — los atajos móviles siguen pudiendo capturar la categoría."""
        seed_system_categories()
        uber = _categoria_de_sistema(db_session, "Uber")
        assert uber is not None
        assert _post_hide(client, auth_headers, uber.id).status_code == 204

        cuenta = make_account(auth_headers, balance="1000.00")
        response = client.post(
            "/api/v1/transactions/",
            json={
                "amount": "50.00",
                "type": "expense",
                "description": "viaje por shortcut",
                "account_id": cuenta["id"],
                "category": "Uber",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["category_id"] == uber.id
