"""Concurrencia real de transferencias (Fase 39 T8), contra Postgres.

Mismo seam que `test_funds_gasto_concurrency.py`. Las cuentas se bloquean y se actualizan en orden
ascendente de id (D7): dos transferencias cruzadas A->B y B->A simultáneas no se bloquean entre sí.
"""

from decimal import Decimal

import pytest

from tests.test_funds_concurrency import _disparar

pytestmark = pytest.mark.concurrencia

URL = "/api/v1/transfers/"


def _preparar(real_client, real_register_and_login, real_make_account, email: str):
    usuario = real_register_and_login(email=email)
    a = real_make_account(usuario["headers"], name="A", balance="10000.00")
    b = real_make_account(usuario["headers"], name="B", balance="10000.00")
    return usuario, a, b


def _saldo(real_client, usuario, cuenta_id) -> Decimal:
    resp = real_client.get(f"/api/v1/accounts/{cuenta_id}", headers=usuario["headers"])
    return Decimal(str(resp.json()["balance"]))


class TestTransferenciasCruzadas:
    def test_a_a_b_y_b_a_a_simultaneas_no_hacen_deadlock(self, real_client, real_register_and_login, real_make_account):
        usuario, a, b = _preparar(real_client, real_register_and_login, real_make_account, "tr-cruzadas@example.com")

        def _transferir(i: int) -> int:
            origen, destino = (a, b) if i % 2 == 0 else (b, a)
            monto = "100.00" if i % 2 == 0 else "30.00"
            return real_client.post(
                URL,
                json={"from_account_id": origen["id"], "to_account_id": destino["id"], "amount_out": monto},
                headers=usuario["headers"],
            ).status_code

        resultados = _disparar(16, _transferir)

        assert resultados == [200] * 16, resultados
        # 8 de A->B por 100 y 8 de B->A por 30: A pierde 800 y gana 240.
        assert _saldo(real_client, usuario, a["id"]) == Decimal("9440.00")
        assert _saldo(real_client, usuario, b["id"]) == Decimal("10560.00")

    def test_editar_y_borrar_cruzados_tampoco_se_bloquean(
        self, real_client, real_register_and_login, real_make_account
    ):
        usuario, a, b = _preparar(real_client, real_register_and_login, real_make_account, "tr-edit@example.com")
        creadas = []
        for origen, destino in ((a, b), (b, a), (a, b), (b, a)):
            r = real_client.post(
                URL,
                json={"from_account_id": origen["id"], "to_account_id": destino["id"], "amount_out": "50.00"},
                headers=usuario["headers"],
            )
            assert r.status_code == 200, r.text
            creadas.append((r.json()["id"], origen, destino))

        def _accion(i: int) -> int:
            tid, origen, destino = creadas[i]
            if i % 2 == 0:
                return real_client.delete(f"{URL}{tid}", headers=usuario["headers"]).status_code
            body = {"from_account_id": destino["id"], "to_account_id": origen["id"], "amount_out": "70.00"}
            return real_client.put(f"{URL}{tid}", json=body, headers=usuario["headers"]).status_code

        resultados = _disparar(4, _accion)

        assert 500 not in resultados and set(resultados) <= {200, 204}, resultados
        # Ver que el saldo quedó consistente con lo que sobrevive: se reconcilia sin discrepancia.
        for cuenta in (a, b):
            r = real_client.post(f"/api/v1/accounts/{cuenta['id']}/reconcile", headers=usuario["headers"])
            assert Decimal(str(r.json()["discrepancy"])) == Decimal("0.00")

    def test_borrados_repetidos_de_la_misma_transferencia_revierten_una_sola_vez(
        self, real_client, real_register_and_login, real_make_account
    ):
        usuario, a, b = _preparar(real_client, real_register_and_login, real_make_account, "tr-doble@example.com")
        t = real_client.post(
            URL,
            json={"from_account_id": a["id"], "to_account_id": b["id"], "amount_out": "500.00"},
            headers=usuario["headers"],
        ).json()

        resultados = _disparar(
            6, lambda _i: real_client.delete(f"{URL}{t['id']}", headers=usuario["headers"]).status_code
        )

        assert resultados.count(204) == 1 and resultados.count(404) == 5, resultados
        assert _saldo(real_client, usuario, a["id"]) == Decimal("10000.00")
        assert _saldo(real_client, usuario, b["id"]) == Decimal("10000.00")
