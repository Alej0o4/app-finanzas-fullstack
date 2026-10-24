"""Script de datos de la Fase 39 (D4, T9): `scripts/fase39_corregir_bancolombia.py`.

Se prueba `ejecutar` sobre una copia sintética del estado real (Bancolombia 8.994.000 COP con dos CDT
aislados), igual que el resto de la suite: sesión de test, sin tocar ninguna base real."""

import importlib.util
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.models import models

D = Decimal
RUTA = Path(__file__).resolve().parents[2] / "scripts" / "fase39_corregir_bancolombia.py"
AHORA = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)
CDTS = "/api/v1/cdts/"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("fase39_corregir_bancolombia", RUTA)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def estado(client, auth_headers, make_account, make_category):
    """Bancolombia con saldo inicial 0 y 8.994.000 de movimientos; dos CDT reales sin vínculo."""
    cuenta = make_account(auth_headers, name="Bancolombia", type="debit", balance="0.00")
    cat = make_category(auth_headers, name="Sueldo", type="income")
    r = client.post(
        "/api/v1/transactions/",
        json={"amount": "8994000.00", "type": "income", "account_id": cuenta["id"], "category_id": cat["id"]},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    for principal, abierto in (("22000000.00", "2026-09-22"), ("10000000.00", "2026-10-17")):
        r = client.post(
            CDTS,
            json={
                "name": f"CDT {principal}",
                "currency": "COP",
                "principal": principal,
                "rate_ea": "10",
                "opened_on": abierto,
                "maturity_on": "2027-04-17",
            },
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
    return cuenta


def _cuenta(db_session, cuenta_id):
    db_session.expire_all()
    return db_session.get(models.Account, cuenta_id)


def test_deja_bancolombia_en_2614000_con_las_dos_transferencias(
    script, db_session, estado, test_user, client, auth_headers
):
    salida = []
    codigo = script.ejecutar(db_session, test_user["email"], "Bancolombia", AHORA, True, salida.append)

    assert codigo == script.EXIT_OK, salida
    cuenta = _cuenta(db_session, estado["id"])
    assert cuenta.balance == D("2614000.00")
    assert cuenta.opening_balance == D("25620000.00")
    transferencias = db_session.query(models.Transfer).order_by(models.Transfer.amount_out.desc()).all()
    assert [(t.amount_out, t.from_account_id, t.to_account_id) for t in transferencias] == [
        (D("22000000.00"), estado["id"], None),
        (D("10000000.00"), estado["id"], None),
    ]
    assert [t.date.date().isoformat() for t in transferencias] == ["2026-09-22", "2026-10-17"]
    assert all(t.cdt_id is not None for t in transferencias)
    # La reconciliación cuadra y el patrimonio ya no cuenta los 32 millones dos veces.
    r = client.post(f"/api/v1/accounts/{estado['id']}/reconcile", headers=auth_headers).json()
    assert D(str(r["discrepancy"])) == D("0.00")
    items = {i["principal"]: i for i in client.get(CDTS, headers=auth_headers).json()["items"]}
    assert all(i["source_account_id"] == estado["id"] for i in items.values())


def test_segunda_corrida_sale_con_exito_sin_cambiar_nada(script, db_session, estado, test_user):
    script.ejecutar(db_session, test_user["email"], "Bancolombia", AHORA, True, lambda _m: None)
    salida = []
    codigo = script.ejecutar(db_session, test_user["email"], "Bancolombia", AHORA, True, salida.append)

    assert codigo == script.EXIT_OK and "Ya migrado" in salida[0]
    cuenta = _cuenta(db_session, estado["id"])
    assert (cuenta.balance, cuenta.opening_balance) == (D("2614000.00"), D("25620000.00"))
    assert db_session.query(models.Transfer).count() == 2


def test_aborta_si_el_saldo_de_partida_no_coincide(script, db_session, estado, test_user):
    cuenta = _cuenta(db_session, estado["id"])
    cuenta.balance = D("8000000.00")
    db_session.commit()
    salida = []
    codigo = script.ejecutar(db_session, test_user["email"], "Bancolombia", AHORA, True, salida.append)

    assert codigo == script.EXIT_ABORTADO and "ABORTADO" in salida[-1]
    cuenta = _cuenta(db_session, estado["id"])
    assert (cuenta.balance, cuenta.opening_balance) == (D("8000000.00"), D("0.00"))
    assert db_session.query(models.Transfer).count() == 0


def test_aborta_si_falta_un_cdt_o_la_cuenta_o_el_usuario(script, db_session, estado, test_user, client, auth_headers):
    quedan = [i for i in client.get(CDTS, headers=auth_headers).json()["items"] if i["principal"] == "10000000.00"]
    client.delete(f"{CDTS}{quedan[0]['id']}", headers=auth_headers)
    assert script.ejecutar(db_session, test_user["email"], "Bancolombia", AHORA, True, lambda _m: None) == 1
    assert script.ejecutar(db_session, test_user["email"], "Otra", AHORA, True, lambda _m: None) == 1
    assert script.ejecutar(db_session, "nadie@example.com", "Bancolombia", AHORA, True, lambda _m: None) == 1
    assert _cuenta(db_session, estado["id"]).balance == D("8994000.00")
    assert db_session.query(models.Transfer).count() == 0


def test_aborta_con_estado_parcial_o_inconsistente(script, db_session, estado, test_user, client, auth_headers):
    # Un CDT ya vinculado a mano, el otro no: no es el estado migrado ni el de partida.
    uno = client.get(CDTS, headers=auth_headers).json()["items"][0]
    r = client.put(f"{CDTS}{uno['id']}", json={"source_account_id": estado["id"]}, headers=auth_headers)
    assert r.status_code == 200, r.text
    saldo_parcial = _cuenta(db_session, estado["id"]).balance
    assert script.ejecutar(db_session, test_user["email"], "Bancolombia", AHORA, True, lambda _m: None) == 1
    assert _cuenta(db_session, estado["id"]).balance == saldo_parcial


def test_sin_confirmacion_solo_imprime_el_plan(script, db_session, estado, test_user):
    salida = []
    codigo = script.ejecutar(db_session, test_user["email"], "Bancolombia", AHORA, False, salida.append)

    assert codigo == script.EXIT_SIN_CONFIRMACION
    assert any("25,620,000.00" in linea or "28,614,000.00" in linea or "2,614,000.00" in linea for linea in salida)
    assert _cuenta(db_session, estado["id"]).balance == D("8994000.00")
    assert db_session.query(models.Transfer).count() == 0


def test_main_cli_sin_y_con_confirmo_copia(script, tmp_path, capsys):
    """Cableado del CLI contra una base SQLite desechable (no la de la suite)."""
    from datetime import date

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.database import Base

    url = f"sqlite:///{tmp_path / 'copia.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        user = models.User(email="dueno@example.com", password_hash="x", full_name="Dueño")
        db.add(user)
        db.flush()
        db.add(
            models.Account(
                user_id=user.id,
                name="Bancolombia",
                type="debit",
                currency="COP",
                balance=D("8994000"),
                opening_balance=0,
            )
        )
        for principal in ("22000000", "10000000"):
            db.add(
                models.Cdt(
                    user_id=user.id,
                    name=f"CDT {principal}",
                    currency="COP",
                    principal=D(principal),
                    rate_ea=D("10"),
                    opened_on=date(2026, 9, 1),
                    maturity_on=date(2027, 9, 1),
                )
            )
        db.commit()

    base = ["--url", url, "--email", "dueno@example.com"]
    assert script.main(base) == script.EXIT_SIN_CONFIRMACION
    with sessionmaker(bind=engine)() as db:
        assert db.query(models.Transfer).count() == 0
        assert db.query(models.Account).one().balance == D("8994000")

    assert script.main([*base, "--confirmo-copia"]) == script.EXIT_OK
    with sessionmaker(bind=engine)() as db:
        assert db.query(models.Transfer).count() == 2
        assert db.query(models.Account).one().balance == D("2614000")
    engine.dispose()
