"""Concurrencia real contra Postgres (Fase 31, T2 + B2 + caso Postgres de T7; renombrado en
la Fase 32, B5).

Único archivo que usa el seam de `real_client`/`real_register_and_login`/`real_make_account`/
`real_make_category` (`conftest.py`) — sesión real por request, commits reales, requests
lanzadas desde hilos con `threading.Barrier`. Marcado `concurrencia` a nivel de módulo: el
marker describe el AISLAMIENT que necesita el test, no el motor (B4, Q6), así que se salta
automáticamente en el único modo sin sesiones reales por request, el opt-in SQLite
(`TEST_DATABASE_URL=sqlite://`). Con Postgres como default (I1) este archivo corre siempre que
`pytest` no lleve esa variable.

`reconcile.discrepancy` es el invariante que se verifica en todos los escenarios: "el
saldo guardado es el saldo de apertura más las transacciones vivas" — el mismo criterio
que usa `docs/specs/fase_31_spec.md` §Testing Decisions.
"""

import threading
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.concurrencia


def _crear_transaccion(real_client, headers, *, account_id, category_id, amount, type_, description="tx concurrencia"):
    response = real_client.post(
        "/api/v1/transactions/",
        json={
            "amount": amount,
            "type": type_,
            "description": description,
            "account_id": account_id,
            "category_id": category_id,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _reconcile(real_client, headers, account_id) -> Decimal:
    response = real_client.post(f"/api/v1/accounts/{account_id}/reconcile", headers=headers)
    assert response.status_code == 200, response.text
    return Decimal(str(response.json()["discrepancy"]))


class TestConcurrentDeleteSameTransaction:
    """T2 — QA-003 (B1): 8 `DELETE` paralelos sobre la MISMA transacción."""

    def test_eight_parallel_deletes_exactly_one_succeeds_and_reconciles(
        self, real_client, real_register_and_login, real_make_account, real_make_category
    ):
        user = real_register_and_login(email="concurrencia-delete@example.com")
        cuenta = real_make_account(user["headers"], balance="1000.00")
        categoria = real_make_category(user["headers"], name="Comida", type="expense")
        creada = _crear_transaccion(
            real_client,
            user["headers"],
            account_id=cuenta["id"],
            category_id=categoria["id"],
            amount="50.00",
            type_="expense",
        )

        n = 8
        barrera = threading.Barrier(n)
        resultados: list[int | None] = [None] * n

        def _delete(i: int) -> None:
            barrera.wait()
            resp = real_client.delete(f"/api/v1/transactions/{creada['id']}", headers=user["headers"])
            resultados[i] = resp.status_code

        hilos = [threading.Thread(target=_delete, args=(i,)) for i in range(n)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()

        assert resultados.count(200) == 1, resultados
        assert resultados.count(404) == n - 1, resultados
        assert 500 not in resultados, resultados

        assert _reconcile(real_client, user["headers"], cuenta["id"]) == Decimal("0.00")


class TestConcurrentUpdateSameTransaction:
    """T2 — QA-003 (B1): 8 `PUT` paralelos con montos distintos sobre la MISMA
    transacción — todos deben responder 200 y el saldo final debe cuadrar sea cual sea
    el orden real en que Postgres serializó las escrituras (el invariante es
    `reconcile`, no un monto final específico)."""

    def test_eight_parallel_updates_all_succeed_and_reconcile(
        self, real_client, real_register_and_login, real_make_account, real_make_category
    ):
        user = real_register_and_login(email="concurrencia-update@example.com")
        cuenta = real_make_account(user["headers"], balance="1000.00")
        categoria = real_make_category(user["headers"], name="Comida", type="expense")
        creada = _crear_transaccion(
            real_client,
            user["headers"],
            account_id=cuenta["id"],
            category_id=categoria["id"],
            amount="50.00",
            type_="expense",
        )

        n = 8
        barrera = threading.Barrier(n)
        resultados: list[int | None] = [None] * n

        def _put(i: int) -> None:
            barrera.wait()
            payload = {
                "amount": f"{10 + i}.00",
                "currency": "COP",
                "type": "expense",
                "description": f"edición concurrente {i}",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            }
            resp = real_client.put(f"/api/v1/transactions/{creada['id']}", json=payload, headers=user["headers"])
            resultados[i] = resp.status_code

        hilos = [threading.Thread(target=_put, args=(i,)) for i in range(n)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()

        assert resultados == [200] * n, resultados
        assert _reconcile(real_client, user["headers"], cuenta["id"]) == Decimal("0.00")


class TestConcurrentUpdateAndDeleteSameTransaction:
    """T2 — QA-003 (B1): 4 `PUT` + 4 `DELETE` simultáneos sobre la MISMA transacción —
    sea cual sea el orden real, la transacción termina borrada y la cuenta concilia."""

    def test_four_updates_and_four_deletes_end_deleted_and_reconciled(
        self, real_client, real_register_and_login, real_make_account, real_make_category
    ):
        user = real_register_and_login(email="concurrencia-mixta@example.com")
        cuenta = real_make_account(user["headers"], balance="1000.00")
        categoria = real_make_category(user["headers"], name="Comida", type="expense")
        creada = _crear_transaccion(
            real_client,
            user["headers"],
            account_id=cuenta["id"],
            category_id=categoria["id"],
            amount="50.00",
            type_="expense",
        )

        n = 8
        barrera = threading.Barrier(n)
        resultados: list[int | None] = [None] * n

        def _worker(i: int) -> None:
            barrera.wait()
            if i % 2 == 0:
                payload = {
                    "amount": f"{20 + i}.00",
                    "currency": "COP",
                    "type": "expense",
                    "description": f"edición mixta {i}",
                    "account_id": cuenta["id"],
                    "category_id": categoria["id"],
                }
                resp = real_client.put(f"/api/v1/transactions/{creada['id']}", json=payload, headers=user["headers"])
            else:
                resp = real_client.delete(f"/api/v1/transactions/{creada['id']}", headers=user["headers"])
            resultados[i] = resp.status_code

        hilos = [threading.Thread(target=_worker, args=(i,)) for i in range(n)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()

        assert 500 not in resultados, resultados
        assert all(r in (200, 404) for r in resultados), resultados

        listado = real_client.get("/api/v1/transactions/", headers=user["headers"])
        assert listado.status_code == 200, listado.text
        assert all(t["id"] != creada["id"] for t in listado.json()["items"])

        assert _reconcile(real_client, user["headers"], cuenta["id"]) == Decimal("0.00")


class TestConcurrentOppositeDirectionUpdatesNoDeadlock:
    """B2 (H12) — única verificación obligatoria de B2 (spec, T2): dos `PUT`
    concurrentes que mueven transacciones DISTINTAS en sentidos opuestos entre dos
    cuentas (A→B y B→A) nunca responden 500 (el `DeadlockDetected` de Postgres cuando
    los dos `UPDATE` de `Account.balance` toman los locks en orden inverso), repetido
    varias veces, y las dos cuentas concilian al final."""

    def test_opposite_direction_updates_never_deadlock_and_both_accounts_reconcile(
        self, real_client, real_register_and_login, real_make_account, real_make_category
    ):
        user = real_register_and_login(email="concurrencia-deadlock@example.com")
        cuenta_a = real_make_account(user["headers"], name="Cuenta A", balance="1000.00")
        cuenta_b = real_make_account(user["headers"], name="Cuenta B", balance="1000.00")
        categoria = real_make_category(user["headers"], name="Comida", type="expense")

        tx_en_a = _crear_transaccion(
            real_client,
            user["headers"],
            account_id=cuenta_a["id"],
            category_id=categoria["id"],
            amount="50.00",
            type_="expense",
        )
        tx_en_b = _crear_transaccion(
            real_client,
            user["headers"],
            account_id=cuenta_b["id"],
            category_id=categoria["id"],
            amount="30.00",
            type_="expense",
        )

        repeticiones = 15
        fallas_500 = []

        for _ in range(repeticiones):
            barrera = threading.Barrier(2)
            resultados: dict[str, object] = {}

            def _mover(
                nombre: str, tx: dict, cuenta_destino_id: int, *, _barrera=barrera, _resultados=resultados
            ) -> None:
                # `_barrera`/`_resultados` como default arg: los liga al valor de ESTA
                # vuelta del loop en el momento de la definición, no al nombre de la
                # variable (que la siguiente vuelta reasigna) — B023 de flake8-bugbear.
                _barrera.wait()
                payload = {
                    "amount": tx["amount"],
                    "currency": "COP",
                    "type": "expense",
                    "description": "movida cruzada",
                    "account_id": cuenta_destino_id,
                    "category_id": categoria["id"],
                }
                resp = real_client.put(f"/api/v1/transactions/{tx['id']}", json=payload, headers=user["headers"])
                _resultados[nombre] = resp

            h1 = threading.Thread(target=_mover, args=("a_to_b", tx_en_a, cuenta_b["id"]))
            h2 = threading.Thread(target=_mover, args=("b_to_a", tx_en_b, cuenta_a["id"]))
            h1.start()
            h2.start()
            h1.join()
            h2.join()

            for nombre, resp in resultados.items():
                if resp.status_code == 500:
                    fallas_500.append((nombre, resp.status_code, resp.text))

            assert resultados["a_to_b"].status_code == 200, resultados["a_to_b"].text
            assert resultados["b_to_a"].status_code == 200, resultados["b_to_a"].text

            # Swap: para la próxima vuelta, cada transacción vive ahora en la cuenta
            # contraria — se repite el cruce en la dirección inversa.
            tx_en_a = resultados["b_to_a"].json()
            tx_en_b = resultados["a_to_b"].json()

        assert fallas_500 == []
        assert _reconcile(real_client, user["headers"], cuenta_a["id"]) == Decimal("0.00")
        assert _reconcile(real_client, user["headers"], cuenta_b["id"]) == Decimal("0.00")


class TestSessionTimezoneIsAlwaysUtc:
    """T7 (B8, QA-022) — caso Postgres: la sesión de la app queda en UTC pase lo que
    pase con el timezone por defecto configurado en el servidor/base de datos.

    Estos dos son los únicos que hablan de la base sin pasar por HTTP, y para eso usan
    `admin_engine` (B5): el `engine` de la suite no sirve —una conexión suya se abrió antes
    del `ALTER DATABASE`, así que no ve el default nuevo de la base y el `SHOW timezone` de
    control no probaría nada—, y el nombre de la base sale de `test_db_url` en vez de leerse
    de `os.environ`."""

    def test_session_is_utc_even_if_database_default_changes(self, test_db_url, admin_engine):
        db_name = test_db_url.rsplit("/", 1)[-1]
        try:
            with admin_engine.connect() as conn:
                conn.execute(text(f"ALTER DATABASE \"{db_name}\" SET timezone TO 'America/Bogota'"))

            # Conexión NUEVA (para que recoja el ALTER DATABASE de arriba) armada con
            # los mismos kwargs que usa la app real — `options: -c timezone=UTC` (B8)
            # debe ganarle al default de la base. Que sea nueva de verdad lo garantiza
            # el `NullPool` de `admin_engine`.
            with admin_engine.connect() as conn:
                assert conn.execute(text("SHOW timezone")).scalar() == "UTC"
        finally:
            with admin_engine.connect() as conn:
                conn.execute(text(f'ALTER DATABASE "{db_name}" SET timezone TO DEFAULT'))

    def test_cashflow_series_bucket_does_not_shift_with_database_default_timezone(
        self, real_client, real_register_and_login, real_make_account, real_make_category, test_db_url, admin_engine
    ):
        """Con el default de la base en `America/Bogota` (UTC-5), un ingreso a las
        `2026-03-01T02:00:00Z` debe seguir cayendo en el bucket `2026-03-01` de
        `cashflow-series` — sin B8, `to_char()` convertiría la fecha a la zona de la
        SESIÓN antes de agruparla y el bucket se correría a `2026-02-28`."""
        db_name = test_db_url.rsplit("/", 1)[-1]
        try:
            with admin_engine.connect() as conn:
                conn.execute(text(f"ALTER DATABASE \"{db_name}\" SET timezone TO 'America/Bogota'"))

            user = real_register_and_login(email="concurrencia-tz@example.com")
            # Fase 34: el bucket se agrupa en la zona del usuario; con UTC explícito el caso
            # sigue probando que la zona de la SESIÓN de la base no corre el bucket.
            ajuste = real_client.patch(
                "/api/v1/users/me/preferences", json={"timezone": "UTC"}, headers=user["headers"]
            )
            assert ajuste.status_code == 200, ajuste.text
            cuenta = real_make_account(user["headers"], currency="COP", balance="1000.00")
            categoria = real_make_category(user["headers"], name="Salario", type="income")
            _crear_transaccion(
                real_client,
                user["headers"],
                account_id=cuenta["id"],
                category_id=categoria["id"],
                amount="500.00",
                type_="income",
                description="ingreso de borde de zona horaria",
            )
            # `date` no viaja en el payload de arriba (usa `datetime.now(UTC)` del
            # servidor) — se fija a mano por SQL directo para controlar el instante
            # exacto del caso borde.
            with admin_engine.connect() as conn:
                conn.execute(
                    text("UPDATE transactions SET date = :fecha WHERE account_id = :cuenta_id"),
                    {"fecha": datetime(2026, 3, 1, 2, 0, 0, tzinfo=UTC), "cuenta_id": cuenta["id"]},
                )

            response = real_client.get(
                "/api/v1/dashboard/cashflow-series",
                params={
                    "start_date": "2026-02-01T00:00:00Z",
                    "end_date": "2026-03-31T00:00:00Z",
                    "period": "day",
                    "currency": "COP",
                },
                headers=user["headers"],
            )
            assert response.status_code == 200, response.text
            buckets = {b["date_label"]: b for b in response.json()["buckets"]}
            assert "2026-03-01" in buckets, buckets
            assert Decimal(str(buckets["2026-03-01"]["income"])) == Decimal("500.00")
            assert "2026-02-28" not in buckets, buckets
        finally:
            with admin_engine.connect() as conn:
                conn.execute(text(f'ALTER DATABASE "{db_name}" SET timezone TO DEFAULT'))
