"""Concurrencia real de CDT contra Postgres (Fase 38 T6, D4).

Mismo seam que `test_recurring_concurrency.py`: sesión real por request, commits reales, hilos con
`threading.Barrier`. El `FOR UPDATE` sobre la fila es lo que hace que de dos `redeem` simultáneos
uno gane (200) y el resto vea `redeemed` (409).
"""

import threading
from datetime import UTC, datetime, timedelta

import pytest

from app.core.periods import dia_local
from app.core.timezones import get_zoneinfo
from app.models import models

pytestmark = pytest.mark.concurrencia

URL = "/api/v1/cdts/"


def _crear(real_client, headers) -> dict:
    hoy = dia_local(datetime.now(UTC), get_zoneinfo("America/Bogota"))
    resp = real_client.post(
        URL,
        json={
            "name": "CDT",
            "principal": "1000.00",
            "rate_ea": "10",
            "opened_on": (hoy - timedelta(days=100)).isoformat(),
            # Ya vencido: redimir antes del vencimiento es 422 (92f7e01).
            "maturity_on": (hoy - timedelta(days=1)).isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


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


def test_dos_redenciones_simultaneas_un_200_y_un_409(real_client, real_register_and_login, real_session):
    usuario = real_register_and_login(email="cdt-redeem@example.com")
    cdt = _crear(real_client, usuario["headers"])

    resultados = _disparar(
        2, lambda _i: real_client.post(f"{URL}{cdt['id']}/redeem", json={}, headers=usuario["headers"]).status_code
    )

    assert sorted(resultados) == [200, 409], resultados
    real_session.expire_all()
    fila = real_session.query(models.Cdt).filter(models.Cdt.id == cdt["id"]).one()
    assert fila.status == "redeemed"
    assert real_session.query(models.Transaction).filter(models.Transaction.user_id == usuario["id"]).count() == 0


def test_redimir_y_editar_en_paralelo_no_dejan_estado_incoherente(real_client, real_register_and_login, real_session):
    usuario = real_register_and_login(email="cdt-edit@example.com")
    cdt = _crear(real_client, usuario["headers"])

    def _trabajo(i: int) -> int:
        if i == 0:
            return real_client.post(f"{URL}{cdt['id']}/redeem", json={}, headers=usuario["headers"]).status_code
        return real_client.put(f"{URL}{cdt['id']}", json={"name": f"Edit {i}"}, headers=usuario["headers"]).status_code

    resultados = _disparar(4, _trabajo)

    assert resultados[0] == 200, resultados
    assert 500 not in resultados, resultados
    assert all(r in (200, 409) for r in resultados[1:]), resultados
    real_session.expire_all()
    fila = real_session.query(models.Cdt).filter(models.Cdt.id == cdt["id"]).one()
    assert fila.status == "redeemed"
    assert fila.final_amount is not None
    assert fila.redeemed_on is not None
