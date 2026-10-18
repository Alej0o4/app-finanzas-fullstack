"""Concurrencia real de recurrentes contra Postgres (Fase 37 T9, D9, D20).

Mismo seam que `test_funds_concurrency.py`: sesión real por request, commits reales, hilos con
`threading.Barrier`. El `FOR UPDATE` sobre la regla es lo que impide que dos confirmaciones de la
misma ocurrencia creen dos transacciones, y que `confirm` vs `DELETE` deje una transacción a medias.
"""

import threading
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.core.periods import dia_local
from app.core.timezones import get_zoneinfo
from app.models import models

pytestmark = pytest.mark.concurrencia

URL = "/api/v1/recurring/"


def _hoy() -> str:
    # Zona por defecto de un usuario nuevo (America/Bogota).
    return dia_local(datetime.now(UTC), get_zoneinfo("America/Bogota")).isoformat()


def _preparar(real_client, real_register_and_login, real_make_account, real_make_category, email: str):
    usuario = real_register_and_login(email=email)
    cuenta = real_make_account(usuario["headers"], balance="1000.00")
    categoria = real_make_category(usuario["headers"])
    resp = real_client.post(
        URL,
        json={
            "name": "Arriendo",
            "type": "expense",
            "amount": "100.00",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
            "frequency": "monthly",
            "start_date": _hoy(),
        },
        headers=usuario["headers"],
    )
    assert resp.status_code == 200, resp.text
    return usuario, cuenta, resp.json()


def _disparar(n: int, trabajo) -> list[int | None]:
    barrera = threading.Barrier(n)
    resultados: list[int | None] = [None] * n

    def _correr(i: int) -> None:
        barrera.wait()
        resultados[i] = trabajo(i)

    hilos = [threading.Thread(target=_correr, args=(i,)) for i in range(n)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    return resultados


class TestConfirmarParalelo:
    def test_ocho_confirmaciones_de_la_misma_ocurrencia_crean_una_sola_transaccion(
        self, real_client, real_register_and_login, real_make_account, real_make_category, real_session
    ):
        usuario, cuenta, regla = _preparar(
            real_client, real_register_and_login, real_make_account, real_make_category, "rec-conf@example.com"
        )

        def _confirmar(_i: int) -> int:
            return real_client.post(
                f"{URL}{regla['id']}/confirm", json={"occurrence_date": regla["next_date"]}, headers=usuario["headers"]
            ).status_code

        resultados = _disparar(8, _confirmar)

        assert resultados.count(200) == 1, resultados
        assert resultados.count(409) == 7, resultados
        assert real_session.query(models.Transaction).filter(models.Transaction.user_id == usuario["id"]).count() == 1
        saldo = real_client.get(f"/api/v1/accounts/{cuenta['id']}", headers=usuario["headers"]).json()["balance"]
        assert Decimal(str(saldo)) == Decimal("900.00")

    def test_confirmar_y_saltar_en_paralelo_resuelven_la_ocurrencia_una_sola_vez(
        self, real_client, real_register_and_login, real_make_account, real_make_category, real_session
    ):
        usuario, cuenta, regla = _preparar(
            real_client, real_register_and_login, real_make_account, real_make_category, "rec-skip@example.com"
        )

        def _accion(i: int) -> int:
            accion = "confirm" if i % 2 == 0 else "skip"
            return real_client.post(
                f"{URL}{regla['id']}/{accion}", json={"occurrence_date": regla["next_date"]}, headers=usuario["headers"]
            ).status_code

        resultados = _disparar(6, _accion)

        assert resultados.count(200) == 1, resultados
        assert resultados.count(409) == 5, resultados
        transacciones = (
            real_session.query(models.Transaction).filter(models.Transaction.user_id == usuario["id"]).count()
        )
        saldo = Decimal(
            str(real_client.get(f"/api/v1/accounts/{cuenta['id']}", headers=usuario["headers"]).json()["balance"])
        )
        # O se confirmó (1 transacción, saldo 900) o se saltó (0 transacciones, saldo 1000): nunca a medias.
        assert (transacciones, saldo) in {(1, Decimal("900.00")), (0, Decimal("1000.00"))}


class TestConfirmarVsBorrar:
    def test_confirmar_y_borrar_en_paralelo_no_dejan_transaccion_a_medias(
        self, real_client, real_register_and_login, real_make_account, real_make_category, real_session
    ):
        usuario, cuenta, regla = _preparar(
            real_client, real_register_and_login, real_make_account, real_make_category, "rec-del@example.com"
        )

        def _trabajo(i: int) -> int:
            if i == 0:
                return real_client.delete(f"{URL}{regla['id']}", headers=usuario["headers"]).status_code
            return real_client.post(
                f"{URL}{regla['id']}/confirm", json={"occurrence_date": regla["next_date"]}, headers=usuario["headers"]
            ).status_code

        resultados = _disparar(5, _trabajo)

        assert resultados[0] == 204, resultados
        assert 500 not in resultados, resultados
        assert all(r in (200, 404, 409) for r in resultados[1:]), resultados
        assert resultados[1:].count(200) <= 1, resultados
        confirmadas = resultados[1:].count(200)
        transacciones = (
            real_session.query(models.Transaction).filter(models.Transaction.user_id == usuario["id"]).count()
        )
        assert transacciones == confirmadas
        saldo = Decimal(
            str(real_client.get(f"/api/v1/accounts/{cuenta['id']}", headers=usuario["headers"]).json()["balance"])
        )
        assert saldo == Decimal("1000.00") - Decimal("100.00") * confirmadas
        assert real_session.query(models.RecurringRule).filter(models.RecurringRule.id == regla["id"]).count() == 0
