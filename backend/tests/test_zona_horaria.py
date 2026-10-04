"""Tests de integración por zona horaria (Fase 34, T2-T6): entran por la frontera pública
(HTTP con `TestClient`, `run_weekly_summary_job`) con usuarios en `Asia/Tokyo` (+9, el día local
va ADELANTADO al UTC) y `America/New_York` (-4/-5, con horario de verano), no por el módulo de
límites (eso es `tests/test_periods.py`).

Las fechas de borde se eligen para que la zona del usuario y UTC discrepen en el mes: si algún
endpoint resolviera el mes en UTC, los totales de abajo no cuadrarían.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import ClassVar
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from app.core import security
from app.core.weekly_summary import run_weekly_summary_job
from app.models import models

# (zona, [(instante UTC, monto)], {mes: total esperado en esa zona}) — todos en 2026.
#
# Tokyo: 2026-02-28T15:00Z = 1-mar 00:00 JST (marzo local, febrero UTC);
#        2026-03-31T14:59:59Z = 31-mar 23:59:59 JST; 2026-03-31T16:00Z = 1-abr 01:00 JST.
# New York: 2026-03-01T04:59:59Z = 28-feb 23:59:59 EST (EST = -5, antes del DST del 8-mar);
#        2026-04-01T03:59:59Z = 31-mar 23:59:59 EDT (-4); 2026-04-01T04:00Z = 1-abr 00:00 EDT.
CASOS = {
    "Asia/Tokyo": (
        [("2026-02-28T15:00:00Z", 40), ("2026-03-31T14:59:59Z", 10), ("2026-03-31T16:00:00Z", 20)],
        {2: 0, 3: 50, 4: 20},
    ),
    "America/New_York": (
        [("2026-03-01T04:59:59Z", 40), ("2026-04-01T03:59:59Z", 10), ("2026-04-01T04:00:00Z", 20)],
        {2: 40, 3: 10, 4: 20},
    ),
}


def _usuario_en(register_and_login, client, zona: str, email: str) -> dict:
    user = register_and_login(email=email)
    response = client.patch("/api/v1/users/me/preferences", json={"timezone": zona}, headers=user["headers"])
    assert response.status_code == 200, response.text
    return user


def _rango_mes(mes: int) -> dict:
    ultimo = {2: 28, 3: 31, 4: 30}[mes]
    return {"start_date": f"2026-{mes:02d}-01", "end_date": f"2026-{mes:02d}-{ultimo}"}


def _sembrar(client, headers, make_account, make_category, items) -> dict:
    # `highlighted`: el resumen del dashboard solo cuenta las cuentas destacadas si hay alguna
    # (la cuenta por defecto del registro ya lo es).
    cuenta = make_account(headers, balance="1000.00", highlighted=True)
    categoria = make_category(headers, name="Comida", type="expense")
    for instante, monto in items:
        response = client.post(
            "/api/v1/transactions/",
            json={
                "amount": str(monto),
                "type": "expense",
                "date": instante,
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["date"].startswith(instante[:19])  # datetime con zona: tal cual
    return {"cuenta": cuenta, "categoria": categoria}


def _es_sqlite(db_session) -> bool:
    return db_session.bind.dialect.name == "sqlite"


@pytest.mark.parametrize("zona", list(CASOS))
class TestBordeDeMesPorZonaVistoPorHttp:
    """T2: el mismo gasto de borde cae en el mismo mes en TODOS los endpoints (criterio 1)."""

    def test_los_totales_del_mes_coinciden_entre_endpoints(
        self, zona, client, register_and_login, make_account, make_category
    ):
        user = _usuario_en(register_and_login, client, zona, "borde@example.com")
        h = user["headers"]
        items, esperado = CASOS[zona]
        ids = _sembrar(client, h, make_account, make_category, items)

        for mes, total in esperado.items():
            total = Decimal(total)
            lista = client.get("/api/v1/transactions/", params=_rango_mes(mes), headers=h).json()
            assert sum(Decimal(t["amount"]) for t in lista["items"]) == total, (zona, mes, "lista")

            serie = client.get(
                "/api/v1/dashboard/cashflow-series", params={**_rango_mes(mes), "period": "month"}, headers=h
            )
            assert serie.status_code == 200, serie.text
            assert Decimal(serie.json()["total_expense"]) == total, (zona, mes, "cashflow-series")
            dist = client.get("/api/v1/dashboard/category-distribution", params=_rango_mes(mes), headers=h).json()
            assert sum(Decimal(d["total"]) for d in dist) == total, (zona, mes, "category-distribution")

            resumen = client.get("/api/v1/dashboard/summary", params={"year": 2026, "month": mes}, headers=h).json()
            gasto = next(
                (Decimal(e["total"]) for e in resumen["monthly_expense_by_currency"] if e["currency"] == "COP"),
                Decimal(0),
            )
            assert gasto == total, (zona, mes, "summary")

        # budgets-progress: un presupuesto de marzo ve solo el gasto de marzo de la zona.
        client.post(
            "/api/v1/budgets/",
            json={
                "amount_limit": "1000.00",
                "currency": "COP",
                "month": 3,
                "year": 2026,
                "category_id": ids["categoria"]["id"],
            },
            headers=h,
        )
        progreso = client.get("/api/v1/dashboard/budgets-progress", params={"year": 2026, "month": 3}, headers=h).json()
        assert len(progreso) == 1
        assert Decimal(progreso[0]["spent"]) == Decimal(esperado[3])

    def test_cashflow_series_por_mes_agrupa_en_la_zona(
        self, zona, client, db_session, register_and_login, make_account, make_category
    ):
        if _es_sqlite(db_session):
            pytest.skip("el bucket mensual en la zona del usuario es solo Postgres (SQLite agrupa en UTC, Fase 34 B8c)")
        user = _usuario_en(register_and_login, client, zona, "serie-mes@example.com")
        items, esperado = CASOS[zona]
        _sembrar(client, user["headers"], make_account, make_category, items)
        # Rango de datetimes amplio: no depende de la interpretación solo-día.
        params = {"start_date": "2026-01-01T00:00:00Z", "end_date": "2026-05-01T00:00:00Z", "period": "month"}
        serie = client.get("/api/v1/dashboard/cashflow-series", params=params, headers=user["headers"])
        assert serie.status_code == 200, serie.text
        por_mes = {b["date_label"]: Decimal(b["expense"]) for b in serie.json()["buckets"]}
        assert por_mes == {f"2026-{m:02d}": Decimal(t) for m, t in esperado.items() if t}


@pytest.mark.parametrize("zona", list(CASOS))
def test_cashflow_series_por_dia_agrupa_en_el_dia_local(
    zona, client, db_session, register_and_login, make_account, make_category
):
    """T2 (Q7): el bucket por día usa `AT TIME ZONE <tz>` — solo Postgres; el opt-in SQLite
    agrupa en UTC (documentado), así que acá no hay nada que comprobar."""
    if _es_sqlite(db_session):
        pytest.skip("el bucket por día en la zona del usuario es solo Postgres (SQLite agrupa en UTC, Fase 34 B8c)")
    user = _usuario_en(register_and_login, client, zona, "serie-dia@example.com")
    items, _ = CASOS[zona]
    _sembrar(client, user["headers"], make_account, make_category, items)
    params = {"start_date": "2026-02-01", "end_date": "2026-04-30", "period": "day"}
    serie = client.get("/api/v1/dashboard/cashflow-series", params=params, headers=user["headers"])
    assert serie.status_code == 200, serie.text
    buckets = {b["date_label"]: Decimal(b["expense"]) for b in serie.json()["buckets"]}
    if zona == "Asia/Tokyo":
        assert buckets == {"2026-03-01": Decimal(40), "2026-03-31": Decimal(10), "2026-04-01": Decimal(20)}
    else:
        assert buckets == {"2026-02-28": Decimal(40), "2026-03-31": Decimal(10), "2026-04-01": Decimal(20)}


class TestResumenMensualDeCuentaEnZona:
    @freeze_time("2026-04-02T00:00:00Z")
    def test_monthly_summary_usa_el_mes_actual_de_la_zona(
        self, client, register_and_login, make_account, make_category
    ):
        # Todo bajo el mismo reloj congelado: el JWT de 15 min se emite y se valida con él.
        user = _usuario_en(register_and_login, client, "Asia/Tokyo", "mensual-tokyo@example.com")
        h = user["headers"]
        items, _ = CASOS["Asia/Tokyo"]
        ids = _sembrar(client, h, make_account, make_category, items)
        # Abril en Tokyo (ahora = 2-abr 09:00 JST) solo tiene el gasto de 20 (1-abr 01:00 JST),
        # aunque ese instante sea 31-mar en UTC.
        r = client.get(f"/api/v1/accounts/{ids['cuenta']['id']}/monthly-summary", headers=h)
        assert r.status_code == 200, r.text
        assert Decimal(r.json()["monthly_expense"]) == Decimal(20)

    @freeze_time("2026-04-01T03:59:59.500Z")
    def test_monthly_summary_en_new_york_sigue_en_marzo(self, client, register_and_login, make_account, make_category):
        # 1-abr 03:59:59.5Z = 31-mar 23:59:59.5 EDT: para el usuario todavía es marzo.
        user = _usuario_en(register_and_login, client, "America/New_York", "mensual-ny@example.com")
        h = user["headers"]
        items, _ = CASOS["America/New_York"]
        ids = _sembrar(client, h, make_account, make_category, [items[0], items[1]])
        r = client.get(f"/api/v1/accounts/{ids['cuenta']['id']}/monthly-summary", headers=h)
        assert r.status_code == 200, r.text
        assert Decimal(r.json()["monthly_expense"]) == Decimal(10)  # solo el de marzo (el de feb queda fuera)


@pytest.mark.parametrize("zona", list(CASOS))
class TestContratoDeRangoEnZona:
    """T3 (B7)."""

    def test_solo_dia_incluye_todo_el_dia_local_hasta_el_ultimo_segundo(
        self, zona, client, register_and_login, make_account, make_category
    ):
        user = _usuario_en(register_and_login, client, zona, "rango@example.com")
        h = user["headers"]
        items, _ = CASOS[zona]
        _sembrar(client, h, make_account, make_category, items)
        # El 31-mar local incluye 23:59:59 (monto 10) y excluye el 1-abr (monto 20).
        r = client.get(
            "/api/v1/transactions/", params={"start_date": "2026-03-31", "end_date": "2026-03-31"}, headers=h
        )
        assert [Decimal(t["amount"]) for t in r.json()["items"]] == [Decimal(10)]

    def test_datetime_completo_es_un_instante_con_fin_inclusivo(
        self, zona, client, register_and_login, make_account, make_category
    ):
        user = _usuario_en(register_and_login, client, zona, "rango-dt@example.com")
        h = user["headers"]
        items, _ = CASOS[zona]
        _sembrar(client, h, make_account, make_category, items)
        instante = items[1][0]
        r = client.get("/api/v1/transactions/", params={"start_date": instante, "end_date": instante}, headers=h)
        assert [Decimal(t["amount"]) for t in r.json()["items"]] == [Decimal(10)]

    def test_mezcla_de_formatos_y_inicio_mayor_que_fin(self, zona, client, register_and_login):
        user = _usuario_en(register_and_login, client, zona, "rango-mix@example.com")
        h = user["headers"]
        ok = client.get(
            "/api/v1/transactions/", params={"start_date": "2026-03-01", "end_date": "2026-03-31T23:59:59Z"}, headers=h
        )
        assert ok.status_code == 200, ok.text
        mal = client.get(
            "/api/v1/transactions/", params={"start_date": "2026-04-02", "end_date": "2026-04-01"}, headers=h
        )
        assert mal.status_code in (400, 422)


class TestFechaSoloDiaPorZona:
    """T4 (B9) en Tokyo y New York (Bogotá ya está en `test_transactions.py`)."""

    _ids: ClassVar[dict] = {}

    @pytest.fixture(autouse=True)
    def _limpiar_ids(self):
        self._ids.clear()

    def _crear(self, client, h, make_account, make_category, **extra):
        cuenta = self._ids.get(h["Authorization"]) or (
            make_account(h, balance="1000.00"),
            make_category(h, name="Comida", type="expense"),
        )
        self._ids[h["Authorization"]] = cuenta
        cuenta, categoria = cuenta
        payload = {"amount": "5.00", "type": "expense", "account_id": cuenta["id"], "category_id": categoria["id"]}
        payload.update(extra)
        return client.post("/api/v1/transactions/", json=payload, headers=h)

    @pytest.mark.parametrize(
        ("zona", "guardada"),
        [("Asia/Tokyo", "2026-03-10T03:00:00"), ("America/New_York", "2026-03-10T16:00:00")],
    )
    def test_solo_dia_pasado_es_mediodia_local_y_se_lista_ese_dia(
        self, zona, guardada, client, register_and_login, make_account, make_category
    ):
        user = _usuario_en(register_and_login, client, zona, "dia@example.com")
        h = user["headers"]
        r = self._crear(client, h, make_account, make_category, date="2026-03-10")
        assert r.status_code == 200, r.text
        assert r.json()["date"].startswith(guardada)
        lista = client.get(
            "/api/v1/transactions/", params={"start_date": "2026-03-10", "end_date": "2026-03-10"}, headers=h
        )
        assert len(lista.json()["items"]) == 1
        otro = client.get(
            "/api/v1/transactions/", params={"start_date": "2026-03-11", "end_date": "2026-03-11"}, headers=h
        )
        assert otro.json()["items"] == []

    @pytest.mark.parametrize("zona", ["Asia/Tokyo", "America/New_York"])
    def test_solo_dia_de_hoy_conserva_la_hora_real(self, zona, client, register_and_login, make_account, make_category):
        user = _usuario_en(register_and_login, client, zona, "hoy@example.com")
        hoy = datetime.now(ZoneInfo(zona)).date().isoformat()
        r = self._crear(client, user["headers"], make_account, make_category, date=hoy)
        assert r.status_code == 200, r.text
        guardada = datetime.fromisoformat(r.json()["date"]).replace(tzinfo=UTC)
        assert abs((datetime.now(UTC) - guardada).total_seconds()) < 60

    def test_solo_dia_y_datetime_naive_se_tratan_distinto(
        self, client, register_and_login, make_account, make_category
    ):
        user = _usuario_en(register_and_login, client, "Asia/Tokyo", "naive@example.com")
        h = user["headers"]
        solo_dia = self._crear(client, h, make_account, make_category, date="2026-03-10").json()["date"]
        naive = self._crear(client, h, make_account, make_category, date="2026-03-10T00:00:00").json()["date"]
        assert solo_dia.startswith("2026-03-10T03:00:00")  # 12:00 JST
        assert naive.startswith("2026-03-10T00:00:00")  # naive = UTC, sin cambios

    def test_put_sin_date_conserva_la_anterior_y_con_solo_dia_convierte(
        self, client, register_and_login, make_account, make_category
    ):
        user = _usuario_en(register_and_login, client, "America/New_York", "put@example.com")
        h = user["headers"]
        creada = self._crear(client, h, make_account, make_category, date="2026-03-10").json()
        base = {"type": "expense", "category_id": creada["category_id"], "account_id": creada["account_id"]}
        r = client.put(f"/api/v1/transactions/{creada['id']}", json={**base, "amount": "7.00"}, headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["date"] == creada["date"]
        r = client.put(
            f"/api/v1/transactions/{creada['id']}", json={**base, "amount": "7.00", "date": "2026-03-12"}, headers=h
        )
        assert r.status_code == 200, r.text
        assert r.json()["date"].startswith("2026-03-12T16:00:00")

    def test_sin_date_en_post_usa_ahora(self, client, register_and_login, make_account, make_category):
        user = _usuario_en(register_and_login, client, "Asia/Tokyo", "ahora@example.com")
        r = self._crear(client, user["headers"], make_account, make_category)
        guardada = datetime.fromisoformat(r.json()["date"]).replace(tzinfo=UTC)
        assert abs((datetime.now(UTC) - guardada).total_seconds()) < 60


class TestZonaDelUsuario:
    """T5: registro por email y Google, con `timezone`."""

    def test_registro_con_zona_valida_la_guarda(self, client):
        r = client.post(
            "/api/v1/users/",
            json={
                "email": "tz@example.com",
                "full_name": "Tz",
                "password": security_password(),
                "timezone": "Asia/Tokyo",
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["timezone"] == "Asia/Tokyo"

    @pytest.mark.parametrize("zona", ["Mars/Olympus", "", None])
    def test_registro_con_zona_invalida_o_ausente_no_falla_y_usa_el_default(self, zona, client):
        payload = {"email": "tz2@example.com", "full_name": "Tz", "password": security_password()}
        if zona is not None:
            payload["timezone"] = zona
        r = client.post("/api/v1/users/", json=payload)
        assert r.status_code == 200, r.text
        assert r.json()["timezone"] == "America/Bogota"

    def test_patch_con_zona_invalida_es_422_y_no_cambia_la_guardada(self, client, register_and_login):
        user = _usuario_en(register_and_login, client, "Asia/Tokyo", "patch@example.com")
        r = client.patch("/api/v1/users/me/preferences", json={"timezone": "Mars/Olympus"}, headers=user["headers"])
        assert r.status_code == 422
        assert isinstance(r.json()["detail"], str)
        me = client.get("/api/v1/users/me", headers=user["headers"]).json()
        assert me["timezone"] == "Asia/Tokyo"
        assert client.get("/api/v1/users/me/preferences", headers=user["headers"]).json()["timezone"] == "Asia/Tokyo"

    def test_default_de_un_usuario_sin_zona_y_get_me(self, client, register_and_login):
        user = register_and_login(email="default@example.com")
        assert client.get("/api/v1/users/me", headers=user["headers"]).json()["timezone"] == "America/Bogota"


def security_password() -> str:
    from tests.conftest import STRONG_PASSWORD

    return STRONG_PASSWORD


class TestGoogleConZona:
    def _login(self, client, monkeypatch, email: str, **extra):
        monkeypatch.setattr(security, "GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
        claims = {"email": email, "email_verified": True, "sub": f"google-sub:{email}", "name": "Persona"}
        monkeypatch.setattr("app.api.auth.google_id_token.verify_oauth2_token", lambda token, request, audience: claims)
        return client.post("/api/v1/auth/google", json={"id_token": "falso", **extra})

    def _zona_de(self, db_session, email: str) -> str:
        return db_session.query(models.User).filter(models.User.email == email).one().timezone

    def test_usuario_nuevo_toma_la_zona_enviada(self, client, monkeypatch, db_session):
        assert self._login(client, monkeypatch, "g1@example.com", timezone="Asia/Tokyo").status_code == 200
        assert self._zona_de(db_session, "g1@example.com") == "Asia/Tokyo"

    @pytest.mark.parametrize("extra", [{}, {"timezone": "Mars/Olympus"}])
    def test_usuario_nuevo_sin_zona_o_invalida_queda_en_el_default(self, extra, client, monkeypatch, db_session):
        assert self._login(client, monkeypatch, "g2@example.com", **extra).status_code == 200
        assert self._zona_de(db_session, "g2@example.com") == "America/Bogota"

    def test_login_de_cuenta_existente_ignora_la_zona(self, client, monkeypatch, db_session, register_and_login):
        user = _usuario_en(register_and_login, client, "America/New_York", "g3@example.com")
        assert self._login(client, monkeypatch, user["email"], timezone="Asia/Tokyo").status_code == 200
        db_session.expire_all()
        assert self._zona_de(db_session, user["email"]) == "America/New_York"
        # Y tampoco la de una cuenta creada por Google antes.
        self._login(client, monkeypatch, "g4@example.com", timezone="Asia/Tokyo")
        self._login(client, monkeypatch, "g4@example.com", timezone="Europe/Madrid")
        assert self._zona_de(db_session, "g4@example.com") == "Asia/Tokyo"


class TestResumenSemanalPorZona:
    """T6 (B10): mismo instante de cron, cada usuario resume la semana de SU zona."""

    @pytest.fixture(autouse=True)
    def _sin_vapid(self, monkeypatch):
        for var in ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT"):
            monkeypatch.delenv(var, raising=False)

    def _usuario_con_gasto(self, db, email, zona, instante, monto):
        user = models.User(
            email=email,
            full_name="T",
            password_hash="x",
            timezone=zona,
            preferred_currency="COP",
            weekly_summary_enabled=True,
        )
        db.add(user)
        db.flush()
        cat = models.Category(name="Mercado", type="expense", user_id=user.id)
        cuenta = models.Account(name="C", type="cash", currency="COP", user_id=user.id)
        db.add_all([cat, cuenta])
        db.flush()
        db.add(
            models.Transaction(
                amount=monto,
                currency="COP",
                type="expense",
                description="g",
                date=instante,
                user_id=user.id,
                account_id=cuenta.id,
                category_id=cat.id,
            )
        )
        db.flush()
        return user.id

    def _notif(self, db, user_id):
        return db.query(models.Notification).filter(models.Notification.user_id == user_id).all()

    @freeze_time("2026-10-05T12:00:00Z")  # lunes 07:00 Bogotá, el cron real
    def test_cada_usuario_resume_la_semana_de_su_zona(self, db_session, monkeypatch):
        monkeypatch.setattr("app.core.weekly_summary.SessionLocal", lambda: db_session)
        # Referencia del job = 28-sep 12:00Z → semana 40 (28-sep a 4-oct) en ambas zonas.
        # Gasto G1 = domingo 4-oct 20:00 Bogotá (= 5-oct 01:00Z): semana 40 en Bogotá, pero en
        # Tokyo ya es lunes 5-oct 10:00 → semana 41, fuera de lo que se resume.
        g1 = datetime(2026, 10, 5, 1, 0, tzinfo=UTC)
        # Gasto G2 = lunes 28-sep 05:00 Tokyo (= 27-sep 20:00Z): semana 40 en Tokyo, pero en
        # Bogotá es domingo 27-sep 15:00 → semana 39.
        g2 = datetime(2026, 9, 27, 20, 0, tzinfo=UTC)
        bog = self._usuario_con_gasto(db_session, "bog@test.com", "America/Bogota", g1, 100)
        self._usuario_con_gasto(db_session, "bog-g2@test.com", "America/Bogota", g2, 7)
        tok = self._usuario_con_gasto(db_session, "tok@test.com", "Asia/Tokyo", g2, 300)

        run_weekly_summary_job()

        n_bog = self._notif(db_session, bog)
        assert len(n_bog) == 1 and n_bog[0].period_key == "2026-W40"
        assert "100.00 COP" in n_bog[0].body
        n_tok = self._notif(db_session, tok)
        assert len(n_tok) == 1 and n_tok[0].period_key == "2026-W40"
        assert "300.00 COP" in n_tok[0].body

    def test_ya_no_existe_summary_timezone(self):
        import app.core.weekly_summary as ws

        assert not hasattr(ws, "SUMMARY_TIMEZONE")


class TestAlertasDePresupuestoEnZona:
    """T6 (B8b): un gasto del último día del mes a las 22:00 locales evalúa el mes de la zona."""

    def test_gasto_del_ultimo_dia_a_las_22_en_new_york_alerta_el_presupuesto_de_ese_mes(
        self, client, register_and_login, make_account, make_category
    ):
        user = _usuario_en(register_and_login, client, "America/New_York", "alerta@example.com")
        h = user["headers"]
        cuenta = make_account(h, balance="1000.00")
        categoria = make_category(h, name="Comida", type="expense")
        for mes, anio in ((3, 2026), (4, 2026)):
            r = client.post(
                "/api/v1/budgets/",
                json={
                    "amount_limit": "100.00",
                    "currency": "COP",
                    "month": mes,
                    "year": anio,
                    "category_id": categoria["id"],
                },
                headers=h,
            )
            assert r.status_code == 200, r.text
        # 31-mar 22:00 EDT = 1-abr 02:00Z: abril en UTC, marzo para el usuario.
        r = client.post(
            "/api/v1/transactions/",
            json={
                "amount": "90.00",
                "type": "expense",
                "date": "2026-04-01T02:00:00Z",
                "account_id": cuenta["id"],
                "category_id": categoria["id"],
            },
            headers=h,
        )
        assert r.status_code == 200, r.text
        items = client.get("/api/v1/notifications/", headers=h).json()["items"]
        umbrales = [i for i in items if "80" in (i.get("type") or "") or "threshold" in (i.get("type") or "")]
        assert len(umbrales) == 1
        # Y el progreso confirma que el gasto es de marzo, no de abril.
        marzo = client.get("/api/v1/dashboard/budgets-progress", params={"year": 2026, "month": 3}, headers=h).json()
        abril = client.get("/api/v1/dashboard/budgets-progress", params={"year": 2026, "month": 4}, headers=h).json()
        assert Decimal(marzo[0]["spent"]) == Decimal(90)
        assert Decimal(abril[0]["spent"]) == Decimal(0)
