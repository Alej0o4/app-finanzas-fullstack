#!/usr/bin/env python3
"""Reporte antes/después de la migración de datos de la Fase 34 (X1/X3, T8).

Aplica `alembic upgrade head` sobre una COPIA de la base (nunca producción) y compara, por
usuario, cuenta y mes (en la zona de cada usuario), los totales de ingresos y gastos antes y
después, más la lista de filas que cruzan de mes y la comprobación de que los saldos de cuenta
no cambian. El dueño revisa esto antes de que la migración corra en producción.

Uso (desde la raíz, con el venv del backend):

    backend/venv/bin/python scripts/fase34_reporte_x1.py --url postgresql://u:p@127.0.0.1:5433/copia \
        --confirmo-copia

Receta de copia desechable: ver "Override del operador" en AGENTS.md (Postgres tmpfs en :5433),
o restaurar un `pg_dump` en una base nueva. NO apuntar al stack compose por defecto, que es
producción. Si la base ya está en `head`, el script lo dice y no compara nada (ya no hay "antes").
"""

import argparse
import os
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1] / "backend"
REV_COLUMNA = "a34c0de1b7f2"  # esquema con users.timezone, sin la migración de datos


def _aware(valor) -> datetime:
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor)
    return valor.replace(tzinfo=UTC) if valor.tzinfo is None else valor.astimezone(UTC)


def _snapshot(engine) -> dict:
    with engine.connect() as conn:
        zonas = {r.id: r.timezone for r in conn.execute(text("SELECT id, timezone FROM users"))}
        saldos = {r.id: Decimal(str(r.balance)) for r in conn.execute(text("SELECT id, balance FROM accounts"))}
        filas = conn.execute(
            text(
                "SELECT id, user_id, account_id, type, amount, currency, date FROM transactions WHERE date IS NOT NULL"
            )
        ).all()
    totales: dict = defaultdict(lambda: Decimal(0))
    mes_de: dict[int, str] = {}
    for r in filas:
        local = _aware(r.date).astimezone(ZoneInfo(zonas.get(r.user_id) or "America/Bogota"))
        mes = f"{local.year:04d}-{local.month:02d}"
        mes_de[r.id] = mes
        totales[(r.user_id, r.account_id, mes, r.currency, r.type)] += Decimal(str(r.amount))
    return {"totales": dict(totales), "mes_de": mes_de, "saldos": saldos, "n": len(filas)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="URL SQLAlchemy de la COPIA")
    ap.add_argument("--confirmo-copia", action="store_true", help="confirmo que --url NO es producción")
    args = ap.parse_args()
    if not args.confirmo_copia:
        print("Falta --confirmo-copia: este script MODIFICA la base de --url (aplica la migración).", file=sys.stderr)
        return 2

    engine = create_engine(args.url)
    with engine.connect() as conn:
        actual = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    print(f"Base: {engine.url.render_as_string(hide_password=True)} — revisión actual: {actual}")
    if actual != REV_COLUMNA:
        print(
            f"La copia debe estar en {REV_COLUMNA} (antes de X1); si ya está en head no hay 'antes'.", file=sys.stderr
        )
        return 1

    antes = _snapshot(engine)
    env = {**os.environ, "DATABASE_URL": args.url}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True)
    despues = _snapshot(engine)

    print(f"\nFilas con fecha: {antes['n']} antes / {despues['n']} después")
    print(f"Saldos de cuenta: {'SIN CAMBIOS' if antes['saldos'] == despues['saldos'] else 'CAMBIARON (revisar!)'}")

    cambios = []
    for clave in sorted(set(antes["totales"]) | set(despues["totales"])):
        a, d = antes["totales"].get(clave, Decimal(0)), despues["totales"].get(clave, Decimal(0))
        if a != d:
            cambios.append((clave, a, d))
    print(f"\nTotales por (usuario, cuenta, mes, moneda, tipo) que cambian: {len(cambios)}")
    for (user, cuenta, mes, moneda, tipo), a, d in cambios:
        print(f"  user={user} cuenta={cuenta} {mes} {moneda} {tipo}: {a} -> {d}")

    cruzan = [i for i, m in antes["mes_de"].items() if despues["mes_de"].get(i) != m]
    print(f"\nFilas que cruzan de mes: {len(cruzan)}")
    for i in cruzan:
        print(f"  transacción {i}: {antes['mes_de'][i]} -> {despues['mes_de'][i]}")
    print("\nPara deshacer: alembic downgrade " + REV_COLUMNA + " (con DATABASE_URL de la misma copia).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
