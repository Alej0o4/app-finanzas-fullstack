"""Concurrencia real del gasto contra sobre (Fase 36 D17 a-d), contra Postgres.

Mismo seam que `test_funds_concurrency.py`. El `FOR UPDATE` del sobre serializa los gastos
enlazados entre sí, con retiros manuales y con el borrado del sobre; el de la transacción
serializa los `DELETE` repetidos para devolver al sobre una sola vez.
"""

from decimal import Decimal

import pytest

from app.models import models
from tests.test_funds_concurrency import URL, _disparar, _preparar

pytestmark = pytest.mark.concurrencia

TX = "/api/v1/transactions/"


def _preparar_gasto(
    real_client, real_register_and_login, real_make_account, real_make_category, email: str, saldo_inicial: str
):
    usuario, fondo = _preparar(real_client, real_register_and_login, real_make_account, email, saldo_inicial)
    categoria = real_make_category(usuario["headers"])
    return usuario, fondo, fondo["account_id"], categoria["id"]


def _gasto_enlazado(real_client, usuario, cuenta_id, categoria_id, fund_id, monto: str):
    return real_client.post(
        TX,
        json={
            "amount": monto,
            "type": "expense",
            "account_id": cuenta_id,
            "category_id": categoria_id,
            "fund_id": fund_id,
        },
        headers=usuario["headers"],
    )


def _saldo_sobre(real_client, usuario, fund_id) -> Decimal:
    return Decimal(str(real_client.get(f"{URL}{fund_id}", headers=usuario["headers"]).json()["balance"]))


class TestGastosEnlazadosParalelos:
    def test_ocho_gastos_de_40_sobre_un_saldo_de_100_nunca_lo_dejan_negativo(
        self, real_client, real_register_and_login, real_make_account, real_make_category
    ):
        usuario, fondo, cuenta_id, cat_id = _preparar_gasto(
            real_client,
            real_register_and_login,
            real_make_account,
            real_make_category,
            "gasto-par@example.com",
            "100.00",
        )
        aplicados: list[Decimal | None] = [None] * 8

        def _gastar(i: int) -> int:
            resp = _gasto_enlazado(real_client, usuario, cuenta_id, cat_id, fondo["id"], "40.00")
            if resp.status_code == 200:
                aplicados[i] = Decimal(str(resp.json()["fund_applied_amount"]))
            return resp.status_code

        resultados = _disparar(8, _gastar)

        assert resultados == [200] * 8, resultados  # D3: el exceso no se rechaza, cae como gasto normal
        assert sum((a for a in aplicados if a is not None), Decimal("0")) == Decimal("100.00"), aplicados
        assert _saldo_sobre(real_client, usuario, fondo["id"]) == Decimal("0.00")

    def test_gasto_y_retiro_manual_en_paralelo_no_dejan_negativo(
        self, real_client, real_register_and_login, real_make_account, real_make_category
    ):
        usuario, fondo, cuenta_id, cat_id = _preparar_gasto(
            real_client,
            real_register_and_login,
            real_make_account,
            real_make_category,
            "gasto-ret@example.com",
            "100.00",
        )
        aplicado: list[Decimal] = []
        retirado: list[Decimal] = []

        def _accion(i: int) -> int:
            if i % 2 == 0:
                resp = _gasto_enlazado(real_client, usuario, cuenta_id, cat_id, fondo["id"], "80.00")
                if resp.status_code == 200:
                    aplicado.append(Decimal(str(resp.json()["fund_applied_amount"])))
                return resp.status_code
            resp = real_client.post(
                f"{URL}{fondo['id']}/withdrawals", json={"amount": "60.00"}, headers=usuario["headers"]
            )
            if resp.status_code == 200:
                retirado.append(Decimal("60.00"))
            return resp.status_code

        resultados = _disparar(6, _accion)

        assert 500 not in resultados, resultados
        saldo = _saldo_sobre(real_client, usuario, fondo["id"])
        assert saldo >= 0
        assert saldo == Decimal("100.00") - sum(aplicado, Decimal("0")) - sum(retirado, Decimal("0"))


class TestBorrarSobreVsGastoEnlazado:
    def test_no_quedan_entradas_huerfanas(
        self, real_client, real_register_and_login, real_make_account, real_make_category, real_session
    ):
        usuario, fondo, cuenta_id, cat_id = _preparar_gasto(
            real_client,
            real_register_and_login,
            real_make_account,
            real_make_category,
            "gasto-del@example.com",
            "100.00",
        )

        def _trabajo(i: int) -> int:
            if i == 0:
                return real_client.delete(f"{URL}{fondo['id']}", headers=usuario["headers"]).status_code
            return _gasto_enlazado(real_client, usuario, cuenta_id, cat_id, fondo["id"], "10.00").status_code

        resultados = _disparar(6, _trabajo)

        assert resultados[0] == 204, resultados
        assert 500 not in resultados, resultados
        assert all(r in (200, 404) for r in resultados[1:]), resultados
        real_session.expire_all()
        huerfanas = real_session.query(models.FundEntry).filter(models.FundEntry.fund_id == fondo["id"]).count()
        assert huerfanas == 0


class TestDeleteDobleDeGastoEnlazado:
    def test_dos_delete_simultaneos_devuelven_al_sobre_una_sola_vez(
        self, real_client, real_register_and_login, real_make_account, real_make_category
    ):
        usuario, fondo, cuenta_id, cat_id = _preparar_gasto(
            real_client,
            real_register_and_login,
            real_make_account,
            real_make_category,
            "gasto-dd@example.com",
            "100.00",
        )
        tx = _gasto_enlazado(real_client, usuario, cuenta_id, cat_id, fondo["id"], "60.00").json()
        assert _saldo_sobre(real_client, usuario, fondo["id"]) == Decimal("40.00")

        resultados = _disparar(
            4, lambda _i: real_client.delete(f"{TX}{tx['id']}", headers=usuario["headers"]).status_code
        )

        assert resultados.count(200) == 1, resultados
        assert 500 not in resultados, resultados
        assert _saldo_sobre(real_client, usuario, fondo["id"]) == Decimal("100.00")  # devuelto una vez, no dos
