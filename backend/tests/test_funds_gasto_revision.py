# ruff: noqa: F811  (las fixtures importadas de test_funds_gasto se "redefinen" como argumentos)
"""Regresiones de la revisión de código de la Fase 36: edición ajena al monto, sobre sin saldo en
`PUT` y en el replay idempotente, e intercambio concurrente de sobres."""

from decimal import Decimal

import pytest

# Las fixtures se reutilizan de test_funds_gasto (se importan por nombre, pytest las resuelve).
from tests.test_funds_gasto import (  # noqa: F401
    FUNDS,
    TX,
    _fondo,
    _gasto,
    _m,
    _put,
    categoria,
    cuenta,
    sobre,
)

D = Decimal


class TestEdicionAjenaAlMonto:
    def test_editar_solo_la_descripcion_no_vuelve_a_cobrar_al_sobre(
        self,
        client,
        auth_headers,
        cuenta,
        categoria,
        sobre,
    ):
        fondo = sobre("50.00")
        tx = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "100.00", fund_id=fondo["id"]).json()
        assert _m(tx["fund_applied_amount"]) == D("50.00")  # el sobre solo tenía 50
        client.post(f"{FUNDS}{fondo['id']}/contributions", json={"amount": "30.00"}, headers=auth_headers)

        resp = _put(client, auth_headers, tx, description="solo el texto")  # mismo monto

        assert resp.status_code == 200, resp.text
        assert _m(resp.json()["fund_applied_amount"]) == D("50.00")
        assert _m(_fondo(client, auth_headers, fondo["id"])["balance"]) == D("30.00")  # los 30 siguen ahí


class TestSobreSinSaldo:
    def test_put_con_un_sobre_en_cero_informa_aplicado_cero(
        self,
        client,
        auth_headers,
        cuenta,
        categoria,
        sobre,
    ):
        vacio = sobre("0")
        tx = _gasto(client, auth_headers, cuenta["id"], categoria["id"], "40.00").json()
        resp = _put(client, auth_headers, tx, fund_id=vacio["id"])
        assert resp.status_code == 200, resp.text
        assert resp.json()["fund_id"] is None
        assert _m(resp.json()["fund_applied_amount"]) == D("0")

    def test_replay_idempotente_con_sobre_en_cero_conserva_aplicado_cero(
        self,
        client,
        auth_headers,
        cuenta,
        categoria,
        sobre,
    ):
        vacio = sobre("0")
        cabeceras = {**auth_headers, "Idempotency-Key": "k-f36-revision"}
        cuerpo = {
            "amount": "40.00",
            "type": "expense",
            "account_id": cuenta["id"],
            "category_id": categoria["id"],
            "fund_id": vacio["id"],
        }
        primera = client.post(TX, json=cuerpo, headers=cabeceras).json()
        segunda = client.post(TX, json=cuerpo, headers=cabeceras).json()
        assert _m(primera["fund_applied_amount"]) == _m(segunda["fund_applied_amount"]) == D("0")


@pytest.mark.concurrencia
class TestIntercambioDeSobres:
    def test_dos_cambios_en_sentidos_opuestos_no_se_interbloquean(
        self, real_client, real_register_and_login, real_make_account, real_make_category
    ):
        from tests.test_funds_concurrency import _disparar

        usuario = real_register_and_login(email="swap-f36@example.com")
        h = usuario["headers"]
        cuenta_id = real_make_account(h, balance="1000.00")["id"]
        categoria_id = real_make_category(h)["id"]

        def _sobre(nombre: str) -> int:
            r = real_client.post(
                FUNDS,
                json={"name": nombre, "kind": "goal", "account_id": cuenta_id, "target_amount": "500.00"},
                headers=h,
            )
            fid = r.json()["id"]
            real_client.post(f"{FUNDS}{fid}/contributions", json={"amount": "200.00"}, headers=h)
            return fid

        a, b = _sobre("A"), _sobre("B")

        def _gasto_en(fid: int) -> dict:
            return real_client.post(
                TX,
                json={
                    "amount": "50.00",
                    "type": "expense",
                    "account_id": cuenta_id,
                    "category_id": categoria_id,
                    "fund_id": fid,
                },
                headers=h,
            ).json()

        tx_a, tx_b = _gasto_en(a), _gasto_en(b)

        def _mover(i: int) -> int:
            tx, destino = (tx_a, b) if i == 0 else (tx_b, a)
            return real_client.put(
                f"{TX}{tx['id']}",
                json={
                    "amount": "50.00",
                    "type": "expense",
                    "account_id": cuenta_id,
                    "category_id": categoria_id,
                    "fund_id": destino,
                },
                headers=h,
            ).status_code

        resultados = _disparar(2, _mover)

        assert resultados == [200, 200], resultados  # ninguno aborta por deadlock
        saldos = {fid: _m(real_client.get(f"{FUNDS}{fid}", headers=h).json()["balance"]) for fid in (a, b)}
        assert saldos == {a: D("150.00"), b: D("150.00")}
