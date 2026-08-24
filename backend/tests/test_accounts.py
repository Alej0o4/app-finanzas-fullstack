"""Tests de cuentas (Fase 11 §11.5): el nuevo endpoint GET /api/v1/accounts/summary.

Hasta Fase 11 no existían tests dedicados de app/api/accounts.py (mismo hallazgo de
falta de cobertura que §11.1 señala para dashboard.py).
"""

from decimal import Decimal


class TestAccountsSummary:
    def test_sums_all_accounts_including_non_highlighted(self, client, auth_headers, make_account):
        """Decisión 11.5.1: /accounts/summary suma TODAS las cuentas — a diferencia de
        /dashboard/summary, que filtra por destacadas cuando existe al menos una."""
        make_account(auth_headers, name="Destacada", currency="COP", balance="1000.00", highlighted=True)
        make_account(auth_headers, name="No destacada", currency="COP", balance="500.00", highlighted=False)

        resumen_resp = client.get("/api/v1/accounts/summary", headers=auth_headers)
        assert resumen_resp.status_code == 200, resumen_resp.text
        resumen = resumen_resp.json()
        assert len(resumen) == 1  # una sola moneda → una sola fila
        assert resumen[0]["currency"] == "COP"
        # Incluye la cuenta no destacada (y la cuenta por defecto del registro, saldo 0)
        assert Decimal(str(resumen[0]["total"])) == Decimal("1500.00")

        contraste_resp = client.get("/api/v1/dashboard/summary", headers=auth_headers)
        assert contraste_resp.status_code == 200, contraste_resp.text
        balances_dashboard = {b["currency"]: Decimal(str(b["total"])) for b in contraste_resp.json()["balances"]}
        # El dashboard solo ve las destacadas: 0 (default) + 1000
        assert balances_dashboard["COP"] == Decimal("1000.00")

    def test_groups_balances_by_currency(self, client, auth_headers, make_account):
        make_account(auth_headers, name="Ahorros COP", currency="COP", balance="2000.00")
        make_account(auth_headers, name="Efectivo COP", currency="COP", balance="1000.00", highlighted=True)
        make_account(auth_headers, name="Ahorros USD", currency="USD", balance="500.00")

        resumen_resp = client.get("/api/v1/accounts/summary", headers=auth_headers)
        assert resumen_resp.status_code == 200, resumen_resp.text

        totales = {fila["currency"]: Decimal(str(fila["total"])) for fila in resumen_resp.json()}
        assert len(totales) == 2
        assert totales["COP"] == Decimal("3000.00")
        assert totales["USD"] == Decimal("500.00")

    def test_route_summary_does_not_collide_with_account_id(self, client, auth_headers):
        """⚠️ Ruta declarada antes de GET /{account_id}: si quedara después, FastAPI
        interpretaría "summary" como account_id y respondería 422 en vez de 200."""
        response = client.get("/api/v1/accounts/summary", headers=auth_headers)
        assert response.status_code == 200, response.text

        resumen = response.json()
        assert isinstance(resumen, list)
        for fila in resumen:
            assert set(fila.keys()) == {"currency", "total"}
