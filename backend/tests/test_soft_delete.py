"""Tests del borrado lógico y `updated_at` (Fase 8 §6).

Cubre ambas direcciones del riesgo del filtro global: que SÍ filtre lecturas en todos
lados, y que NO interfiera donde no corresponde (los UPDATE de saldo llevan su filtro
manual — Opción A de la Decisión 6.1).
"""

import time
from datetime import UTC, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import update

from app.models import models


def _now_month_year() -> tuple[int, int]:
    now = datetime.now(UTC)
    return now.month, now.year


def _soft_delete_via_raw_sql(db_session, tabla: str, fila_id: int) -> None:
    """Fabrica el estado 'fila borrada' por SQL crudo, fuera del alcance del filtro ORM.

    Necesario porque los endpoints DELETE tienen guards (ej. cuenta con transacciones)
    que impedirían llegar al estado intermedio que el mecanismo debe resistir.
    """
    db_session.execute(sa.text(f"UPDATE {tabla} SET deleted_at = CURRENT_TIMESTAMP WHERE id = :id"), {"id": fila_id})
    db_session.commit()


def _raw_balance(db_session, account_id: int) -> Decimal:
    """Lee el saldo por SQL crudo: un SELECT ORM estaría filtrado y devolvería None,
    enmascarando el resultado."""
    balance = db_session.execute(sa.text("SELECT balance FROM accounts WHERE id = :id"), {"id": account_id}).scalar()
    return Decimal(str(balance))


class TestGlobalFilterMechanism:
    def test_orm_enabled_update_is_not_filtered_globally_by_design(
        self, db_session, client, auth_headers, make_account
    ):
        """Opción A (Decisión 6.1): el filtro global es select-only. Un `update()`
        ORM-enabled ejecutado vía `db.execute()` SIN filtro manual SÍ muta una fila
        soft-deleted — la misma forma de statement usada por las actualizaciones de
        saldo de transactions.py. Este test documenta ese límite: es la razón por la
        que esos tres call-sites llevan `.where(deleted_at.is_(None))` explícito."""
        cuenta = make_account(auth_headers, balance="1000.00")
        _soft_delete_via_raw_sql(db_session, "accounts", cuenta["id"])

        stmt = (
            update(models.Account)
            .where(models.Account.id == cuenta["id"])
            .values(balance=models.Account.balance + Decimal("500.00"))
        )
        db_session.execute(stmt)
        db_session.commit()

        assert _raw_balance(db_session, cuenta["id"]) == Decimal("1500.00")

    def test_create_transaction_against_soft_deleted_account_returns_404(
        self, db_session, client, auth_headers, make_account, make_category
    ):
        """La protección real en el flujo HTTP: el ownership-SELECT filtrado impide
        llegar al UPDATE de saldo contra una cuenta borrada."""
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Comida", type="expense")
        _soft_delete_via_raw_sql(db_session, "accounts", cuenta["id"])

        response = client.post(
            "/api/v1/transactions/",
            json={
                "amount": "100.00",
                "type": "expense",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 404

        # Ni mutación de saldo ni fila huérfana
        assert _raw_balance(db_session, cuenta["id"]) == Decimal("1000.00")
        total_txs = db_session.execute(sa.text("SELECT COUNT(*) FROM transactions")).scalar()
        assert total_txs == 0


class TestSoftDeletedEntitiesDisappear:
    def test_soft_deleted_account_disappears_from_get_and_row_persists(
        self, db_session, client, auth_headers, make_account
    ):
        cuenta = make_account(auth_headers)

        delete_response = client.delete(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers)
        assert delete_response.status_code == 200, delete_response.text

        listado = client.get("/api/v1/accounts/", headers=auth_headers).json()
        # El registro crea una cuenta por defecto ("Efectivo"); solo garantizamos
        # que la cuenta borrada desapareció del listado.
        assert all(c["id"] != cuenta["id"] for c in listado)
        assert client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).status_code == 404

        # Borrado LÓGICO: la fila sigue físicamente, con deleted_at poblado
        fila = db_session.execute(
            sa.text("SELECT deleted_at IS NOT NULL FROM accounts WHERE id = :id"), {"id": cuenta["id"]}
        ).scalar()
        assert fila == 1

    def test_soft_deleted_category_disappears_from_get_and_row_persists(
        self, db_session, client, auth_headers, make_category
    ):
        categoria = make_category(auth_headers, name="Categoría efímera", type="expense")

        delete_response = client.delete(f"/api/v1/categories/{categoria['id']}", headers=auth_headers)
        assert delete_response.status_code == 200, delete_response.text

        listado = client.get("/api/v1/categories/", headers=auth_headers).json()
        # El borrado es lógico: la categoría deja de aparecer en el listado.
        # (Las categorías base del sistema solo existen si corrió el seed de
        #  arranque, que el cliente de tests no ejecuta — no hay lifespan.)
        assert all(c["name"] != "Categoría efímera" for c in listado)

        assert client.get(f"/api/v1/categories/{categoria['id']}", headers=auth_headers).status_code == 404

        fila = db_session.execute(
            sa.text("SELECT deleted_at IS NOT NULL FROM categories WHERE id = :id"), {"id": categoria["id"]}
        ).scalar()
        assert fila == 1

    def test_soft_deleted_transaction_not_in_list_nor_in_progress_aggregates(
        self, client, auth_headers, make_account, make_category
    ):
        cuenta = make_account(auth_headers, balance="5000.00")
        categoria = make_category(auth_headers, name="Comida agregados", type="expense")
        month, year = _now_month_year()

        budget_response = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "1000.00",
                "currency": "COP",
                "month": month,
                "year": year,
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        assert budget_response.status_code == 200, budget_response.text
        budget_id = budget_response.json()["id"]

        creada = client.post(
            "/api/v1/transactions/",
            json={
                "amount": "300.00",
                "type": "expense",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        ).json()

        progreso_antes = next(
            p
            for p in client.get("/api/v1/dashboard/budgets-progress", headers=auth_headers).json()
            if p["budget_id"] == budget_id
        )
        assert Decimal(str(progreso_antes["spent"])) == Decimal("300.00")

        delete_response = client.delete(f"/api/v1/transactions/{creada['id']}", headers=auth_headers)
        assert delete_response.status_code == 200, delete_response.text

        listado = client.get("/api/v1/transactions/", headers=auth_headers).json()
        assert all(t["id"] != creada["id"] for t in listado["items"])

        progreso = next(
            p
            for p in client.get("/api/v1/dashboard/budgets-progress", headers=auth_headers).json()
            if p["budget_id"] == budget_id
        )
        assert Decimal(str(progreso["spent"])) == Decimal("0.00")

    def test_delete_transaction_still_reverts_balance_and_row_persists(
        self, db_session, client, auth_headers, make_account, make_category
    ):
        """La reversión contable de eliminar_transaccion sobrevive al cambio a borrado
        lógico, y la transacción sigue existiendo físicamente con deleted_at."""
        cuenta = make_account(auth_headers, balance="1000.00")
        categoria = make_category(auth_headers, name="Salario revert", type="income")

        creada = client.post(
            "/api/v1/transactions/",
            json={
                "amount": "400.00",
                "type": "income",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        ).json()

        delete_response = client.delete(f"/api/v1/transactions/{creada['id']}", headers=auth_headers)
        assert delete_response.status_code == 200, delete_response.text

        cuenta_final = client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).json()
        assert Decimal(str(cuenta_final["balance"])) == Decimal("1000.00")

        fila = db_session.execute(
            sa.text("SELECT deleted_at IS NOT NULL FROM transactions WHERE id = :id"), {"id": creada["id"]}
        ).scalar()
        assert fila == 1


class TestPartialUniqueIndex:
    def test_soft_deleted_budget_disappears_and_slot_is_reusable(self, db_session, client, auth_headers, make_category):
        """Decisión 6.2: borrar un presupuesto y crear otro para la misma
        categoría/mes/año debe funcionar sin 400 espurio (el índice único parcial ignora
        las filas soft-deleted)."""
        categoria = make_category(auth_headers, name="Comida slot", type="expense")
        month, year = _now_month_year()
        payload = {
            "amount_limit": "500.00",
            "currency": "COP",
            "month": month,
            "year": year,
            "category_id": categoria["id"],
        }

        original = client.post("/api/v1/budgets/", json=payload, headers=auth_headers)
        assert original.status_code == 200, original.text

        delete_response = client.delete(f"/api/v1/budgets/{original.json()['id']}", headers=auth_headers)
        assert delete_response.status_code == 200, delete_response.text

        listado = client.get("/api/v1/budgets/", params={"month": month, "year": year}, headers=auth_headers)
        assert [b for b in listado.json() if b["category_id"] == categoria["id"]] == []

        reemplazo = client.post("/api/v1/budgets/", json=payload, headers=auth_headers)
        assert reemplazo.status_code == 200, reemplazo.text

        viejo, nuevo = db_session.execute(
            sa.text(
                "SELECT deleted_at IS NOT NULL, id = :nuevo_id FROM budgets "
                "WHERE category_id = :cat AND month = :m AND year = :y"
            ),
            {"nuevo_id": reemplazo.json()["id"], "cat": categoria["id"], "m": month, "y": year},
        ).fetchall()
        # La fila vieja quedó soft-deleted y la nueva está viva
        assert viejo[0] == 1 and viejo[1] == 0
        assert nuevo[0] == 0 and nuevo[1] == 1


class TestOwnershipUnderSoftDelete:
    def test_other_user_cannot_see_or_edit_soft_deleted_account_of_owner(
        self, client, db_session, auth_headers, other_user, make_account
    ):
        cuenta = make_account(auth_headers, name="Solo mía")
        client.delete(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers)

        assert client.get(f"/api/v1/accounts/{cuenta['id']}", headers=other_user["headers"]).status_code == 404
        assert client.get(f"/api/v1/accounts/{cuenta['id']}", headers=auth_headers).status_code == 404

        edicion = client.put(
            f"/api/v1/accounts/{cuenta['id']}",
            json={"name": "Intento de resurrección", "type": "cash", "highlighted": False},
            headers=other_user["headers"],
        )
        assert edicion.status_code == 404


class TestUpdatedAt:
    def test_updated_at_changes_on_put_but_not_on_read(
        self, db_session, client, auth_headers, make_account, make_category
    ):
        """CURRENT_TIMESTAMP en SQLite tiene resolución de segundos: un solo sleep antes
        de las mutaciones garantiza que los timestamps difieran de los de creación."""
        cuenta = make_account(auth_headers, name="Cuenta ts")
        categoria = make_category(auth_headers, name="Categoría ts", type="expense")
        creada = client.post(
            "/api/v1/transactions/",
            json={
                "amount": "50.00",
                "type": "expense",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        ).json()
        month, year = _now_month_year()
        presupuesto = client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "900.00",
                "currency": "COP",
                "month": month,
                "year": year,
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        ).json()

        # updated_at es metadata de auditoría: los schemas de respuesta no la exponen,
        # así que se verifica directo contra la fila.
        def _updated_at(tabla: str, fila_id: int):
            return db_session.execute(
                sa.text(f"SELECT updated_at FROM {tabla} WHERE id = :id"), {"id": fila_id}
            ).scalar()

        recursos = {
            "account": ("accounts", cuenta["id"]),
            "category": ("categories", categoria["id"]),
            "transaction": ("transactions", creada["id"]),
            "budget": ("budgets", presupuesto["id"]),
        }
        iniciales = {nombre: _updated_at(tabla, fila_id) for nombre, (tabla, fila_id) in recursos.items()}
        assert iniciales["account"] is not None

        # Leer no mueve updated_at
        assert _updated_at(*recursos["account"]) == iniciales["account"]

        time.sleep(1.1)

        client.put(
            f"/api/v1/accounts/{cuenta['id']}",
            json={"name": "Cuenta ts editada", "type": "cash", "highlighted": False},
            headers=auth_headers,
        )
        client.put(
            f"/api/v1/categories/{categoria['id']}",
            json={"name": "Categoría ts editada", "type": "expense"},
            headers=auth_headers,
        )
        client.put(
            f"/api/v1/transactions/{creada['id']}",
            json={
                "amount": "60.00",
                "currency": "COP",
                "type": "expense",
                "description": "editada",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=auth_headers,
        )
        client.put(
            f"/api/v1/budgets/{presupuesto['id']}",
            json={
                "amount_limit": "950.00",
                "currency": "COP",
                "month": month,
                "year": year,
                "category_id": categoria["id"],
                "is_recurring": False,
            },
            headers=auth_headers,
        )

        finales = {nombre: _updated_at(tabla, fila_id) for nombre, (tabla, fila_id) in recursos.items()}
        for nombre in recursos:
            assert finales[nombre] != iniciales[nombre], f"updated_at de {nombre} no cambió tras el PUT"
