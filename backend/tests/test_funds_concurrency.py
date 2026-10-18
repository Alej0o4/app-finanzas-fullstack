"""Concurrencia real de sobres contra Postgres (Fase 35 T6, B6).

Mismo seam que `test_concurrency.py`: sesión real por request, commits reales, hilos con
`threading.Barrier`. El `FOR UPDATE` sobre la fila del sobre es lo que impide que dos retiros
vean el mismo saldo y lo dejen en negativo.
"""

import threading
from decimal import Decimal

import pytest

from app.models import models

pytestmark = pytest.mark.concurrencia

URL = "/api/v1/funds/"


def _preparar(real_client, real_register_and_login, real_make_account, email: str, saldo_inicial: str):
    usuario = real_register_and_login(email=email)
    cuenta = real_make_account(usuario["headers"], balance="1000.00")
    resp = real_client.post(
        URL,
        json={"name": "Seguro", "kind": "goal", "account_id": cuenta["id"], "target_amount": "1000.00"},
        headers=usuario["headers"],
    )
    assert resp.status_code == 200, resp.text
    fondo = resp.json()
    resp = real_client.post(
        f"{URL}{fondo['id']}/contributions", json={"amount": saldo_inicial}, headers=usuario["headers"]
    )
    assert resp.status_code == 200, resp.text
    return usuario, fondo


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


class TestRetirosParalelos:
    def test_ocho_retiros_de_40_sobre_un_saldo_de_100_exactamente_dos_pasan(
        self, real_client, real_register_and_login, real_make_account
    ):
        usuario, fondo = _preparar(
            real_client, real_register_and_login, real_make_account, "fondos-ret@example.com", "100.00"
        )

        def _retirar(_i: int) -> int:
            return real_client.post(
                f"{URL}{fondo['id']}/withdrawals", json={"amount": "40.00"}, headers=usuario["headers"]
            ).status_code

        resultados = _disparar(8, _retirar)

        assert resultados.count(200) == 2, resultados
        assert resultados.count(422) == 6, resultados
        assert 500 not in resultados, resultados
        detalle = real_client.get(f"{URL}{fondo['id']}", headers=usuario["headers"]).json()
        assert Decimal(str(detalle["balance"])) == Decimal("20.00")


class TestAportesParalelos:
    def test_ocho_aportes_paralelos_suman_exacto(self, real_client, real_register_and_login, real_make_account):
        usuario, fondo = _preparar(
            real_client, real_register_and_login, real_make_account, "fondos-apo@example.com", "10.00"
        )

        def _aportar(i: int) -> int:
            return real_client.post(
                f"{URL}{fondo['id']}/contributions", json={"amount": f"{i + 1}.00"}, headers=usuario["headers"]
            ).status_code

        resultados = _disparar(8, _aportar)

        assert resultados == [200] * 8, resultados
        detalle = real_client.get(f"{URL}{fondo['id']}", headers=usuario["headers"]).json()
        assert Decimal(str(detalle["balance"])) == Decimal("46.00")  # 10 + (1+2+...+8)
        assert len(detalle["entries"]) == 9


class TestRetiroYArchivoParalelos:
    def test_archivar_mientras_se_retira_nunca_deja_saldo_en_un_archivado(
        self, real_client, real_register_and_login, real_make_account
    ):
        usuario, fondo = _preparar(
            real_client, real_register_and_login, real_make_account, "fondos-arc@example.com", "100.00"
        )

        def _accion(i: int) -> int:
            if i % 2 == 0:
                return real_client.post(
                    f"{URL}{fondo['id']}/withdrawals", json={"amount": "100.00"}, headers=usuario["headers"]
                ).status_code
            return real_client.post(f"{URL}{fondo['id']}/archive", headers=usuario["headers"]).status_code

        resultados = _disparar(8, _accion)

        assert 500 not in resultados, resultados
        detalle = real_client.get(f"{URL}{fondo['id']}", headers=usuario["headers"]).json()
        # Invariante: un sobre archivado siempre tiene saldo 0.
        if detalle["status"] == "archived":
            assert Decimal(str(detalle["balance"])) == Decimal("0.00")


class TestBorrarVsAportar:
    def test_borrar_y_aportar_en_paralelo_no_dejan_entradas_huerfanas(
        self, real_client, real_register_and_login, real_make_account, real_session
    ):
        usuario, fondo = _preparar(
            real_client, real_register_and_login, real_make_account, "fondos-del@example.com", "100.00"
        )

        def _trabajo(i: int) -> int:
            if i == 0:
                return real_client.delete(f"{URL}{fondo['id']}", headers=usuario["headers"]).status_code
            return real_client.post(
                f"{URL}{fondo['id']}/contributions", json={"amount": "10.00"}, headers=usuario["headers"]
            ).status_code

        resultados = _disparar(6, _trabajo)

        assert resultados[0] == 204, resultados
        assert 500 not in resultados, resultados
        assert all(r in (200, 404) for r in resultados[1:]), resultados
        assert real_client.get(f"{URL}{fondo['id']}", headers=usuario["headers"]).status_code == 404
        huerfanas = real_session.query(models.FundEntry).filter(models.FundEntry.fund_id == fondo["id"]).count()
        assert huerfanas == 0
