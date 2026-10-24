#!/usr/bin/env python3
"""Corrección única de datos de la Fase 39 (D4, docs/specs/fase_39_spec.md): deja Bancolombia en la verdad.

Hace, en UNA transacción:

1. Suma 25.620.000 COP al saldo inicial (`opening_balance`) y al saldo (`balance`) de la cuenta: dinero
   que ya estaba en el banco cuando se creó la cuenta con saldo inicial 0.
2. Crea las dos transferencias de constitución (cuenta -> CDT) de los CDT reales:
   22.000.000 COP el 2026-09-22 y 10.000.000 COP el 2026-10-17, y descuenta su capital del saldo.

Saldo esperado antes: 8.994.000 COP. Saldo esperado después: 2.614.000 COP (bolsillo incluido).
**25.620.000 no está verificado contra el extracto del banco**: es el valor que cuadra la cuenta; si
aparece otro movimiento sin registrar, ajustar `AJUSTE_SALDO_INICIAL` antes de correrlo.

Idempotente: si las dos transferencias ya existen y el saldo es 2.614.000, sale con éxito sin cambiar nada.
Aborta (sin escribir) si el saldo de la cuenta no es 8.994.000 y no está ya migrado, para no ejecutarse
contra una base distinta. Los dos CDT se buscan por capital (COP, vigentes) entre los del usuario.

Uso (después de `alembic upgrade head`, desde la raíz, con el venv del backend):

    backend/venv/bin/python scripts/fase39_corregir_bancolombia.py \\
        --url postgresql://usuario:clave@host:5432/oikos --email dueno@example.com --confirmo-copia

Sin `--confirmo-copia` solo imprime el plan y no escribe nada. `--confirmo-copia` significa: "ya hice un
`pg_dump` de esta base" (en producción) o "esto es una copia desechable". Probar primero contra una copia
restaurada; ver "Override del operador" en AGENTS.md para una base desechable.
"""

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

SALDO_ANTES = Decimal("8994000.00")
AJUSTE_SALDO_INICIAL = Decimal("25620000.00")
SALDO_DESPUES = Decimal("2614000.00")
# (capital, fecha de la constitución)
CDT_REALES = [
    (Decimal("22000000.00"), date(2026, 9, 22)),
    (Decimal("10000000.00"), date(2026, 10, 17)),
]
MONEDA = "COP"

EXIT_OK = 0
EXIT_ABORTADO = 1
EXIT_SIN_CONFIRMACION = 2


@dataclass
class Abortar(Exception):
    motivo: str


def _fmt(valor: Decimal) -> str:
    return f"{valor:,.2f}"


def ejecutar(db, email: str, nombre_cuenta: str, ahora: datetime, aplicar: bool, salida=print) -> int:
    """Lógica del script sobre una sesión ya abierta (testeable). Devuelve el código de salida."""
    try:
        return _ejecutar(db, email, nombre_cuenta, ahora, aplicar, salida)
    except Abortar as exc:
        db.rollback()
        salida(f"ABORTADO: {exc.motivo}")
        return EXIT_ABORTADO


def _ejecutar(db, email, nombre_cuenta, ahora, aplicar, salida) -> int:
    from sqlalchemy import case, func

    from app.core.periods import instante_de_dia
    from app.core.timezones import get_zoneinfo
    from app.models import models
    from app.services import ledger

    user = db.query(models.User).filter(models.User.email == email.lower().strip()).first()
    if user is None:
        raise Abortar(f"no existe el usuario {email!r}.")

    cuentas = [
        c
        for c in db.query(models.Account).filter(models.Account.user_id == user.id).all()
        if c.name.strip().lower() == nombre_cuenta.strip().lower()
    ]
    if len(cuentas) != 1:
        raise Abortar(f"se esperaba exactamente una cuenta {nombre_cuenta!r} y hay {len(cuentas)}.")
    cuenta = (
        db.query(models.Account).filter(models.Account.id == cuentas[0].id).with_for_update().one()
    )  # lock + estado fresco
    if cuenta.currency != MONEDA:
        raise Abortar(f"la cuenta es {cuenta.currency}, se esperaba {MONEDA}.")

    cdts = []
    for capital, fecha in CDT_REALES:
        candidatos = (
            db.query(models.Cdt)
            .filter(
                models.Cdt.user_id == user.id,
                models.Cdt.principal == capital,
                models.Cdt.currency == MONEDA,
                models.Cdt.status == "active",
            )
            .all()
        )
        if len(candidatos) != 1:
            raise Abortar(
                f"se esperaba exactamente un CDT vigente de {_fmt(capital)} {MONEDA} y hay {len(candidatos)}."
            )
        cdts.append((candidatos[0], capital, fecha))

    vinculadas = {
        cdt.id: db.query(models.Transfer).filter(models.Transfer.cdt_id == cdt.id).all() for cdt, _, _ in cdts
    }
    ya_migrado = all(any(t.from_account_id == cuenta.id for t in vinculadas[cdt.id]) for cdt, _, _ in cdts)
    if ya_migrado:
        if cuenta.balance != SALDO_DESPUES:
            raise Abortar(
                f"las transferencias ya existen pero el saldo es {_fmt(cuenta.balance)} y se esperaba "
                f"{_fmt(SALDO_DESPUES)}: estado inconsistente, revisar a mano."
            )
        salida(f"Ya migrado: {cuenta.name} = {_fmt(cuenta.balance)} {MONEDA} con las dos transferencias. Sin cambios.")
        return EXIT_OK
    if any(vinculadas[cdt.id] for cdt, _, _ in cdts):
        raise Abortar("alguno de los CDT ya tiene transferencias pero no es el estado migrado: revisar a mano.")
    if cuenta.balance != SALDO_ANTES:
        raise Abortar(
            f"el saldo de {cuenta.name} es {_fmt(cuenta.balance)} y se esperaba {_fmt(SALDO_ANTES)}: "
            "¿es la base correcta?"
        )

    salida(f"Cuenta {cuenta.name} (id {cuenta.id}) de {email}")
    salida(f"  saldo inicial: {_fmt(cuenta.opening_balance)} -> {_fmt(cuenta.opening_balance + AJUSTE_SALDO_INICIAL)}")
    salida(f"  saldo        : {_fmt(cuenta.balance)} -> {_fmt(SALDO_DESPUES)}")
    for cdt, capital, fecha in cdts:
        salida(f"  transferencia {cuenta.name} -> CDT {cdt.name!r} (id {cdt.id}): {_fmt(capital)} el {fecha}")
    if not aplicar:
        salida("Nada se escribió (falta --confirmo-copia).")
        return EXIT_SIN_CONFIRMACION

    tz = get_zoneinfo(user.timezone)
    cuenta.opening_balance = cuenta.opening_balance + AJUSTE_SALDO_INICIAL
    ledger.aplicar_delta(db, cuenta.id, AJUSTE_SALDO_INICIAL)
    for cdt, capital, fecha in cdts:
        db.add(
            models.Transfer(
                user_id=user.id,
                from_account_id=cuenta.id,
                to_account_id=None,
                cdt_id=cdt.id,
                amount_out=capital,
                currency_out=MONEDA,
                amount_in=capital,
                currency_in=MONEDA,
                date=instante_de_dia(fecha, ahora, tz),
                description=f"Constitución CDT {cdt.name}",
            )
        )
        ledger.aplicar_delta(db, cuenta.id, -capital)
    db.flush()
    db.refresh(cuenta)
    if cuenta.balance != SALDO_DESPUES:
        raise Abortar(f"el saldo final sería {_fmt(cuenta.balance)} y no {_fmt(SALDO_DESPUES)}; no se escribió nada.")

    # Informativo: la reconciliación (opening + transacciones + transferencias) debe coincidir con el saldo.
    neto_tx = (
        db.query(
            func.sum(
                case((models.Transaction.type == "income", models.Transaction.amount), else_=-models.Transaction.amount)
            )
        )
        .filter(models.Transaction.account_id == cuenta.id, models.Transaction.deleted_at.is_(None))
        .scalar()
    ) or Decimal("0")
    entradas = (
        db.query(func.sum(models.Transfer.amount_in)).filter(models.Transfer.to_account_id == cuenta.id).scalar() or 0
    )
    salidas = (
        db.query(func.sum(models.Transfer.amount_out)).filter(models.Transfer.from_account_id == cuenta.id).scalar()
        or 0
    )
    discrepancia = cuenta.opening_balance + neto_tx + entradas - salidas - cuenta.balance
    db.commit()
    salida(
        f"Listo: {cuenta.name} = {_fmt(cuenta.balance)} {MONEDA}. Discrepancia de reconciliación: {_fmt(Decimal(discrepancia))}."
    )
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="URL SQLAlchemy de la base (ya migrada a head)")
    ap.add_argument("--email", required=True, help="email del dueño de la cuenta")
    ap.add_argument("--cuenta", default="Bancolombia", help="nombre de la cuenta (por defecto Bancolombia)")
    ap.add_argument("--confirmo-copia", action="store_true", help="confirmo que hice un pg_dump / es una copia")
    args = ap.parse_args(argv)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.database import engine_kwargs_for_url

    engine = create_engine(args.url, **engine_kwargs_for_url(args.url))
    print(f"Base: {engine.url.render_as_string(hide_password=True)}")
    with sessionmaker(bind=engine, autoflush=False)() as db:
        codigo = ejecutar(db, args.email, args.cuenta, datetime.now(UTC), args.confirmo_copia)
    if codigo == EXIT_SIN_CONFIRMACION:
        print("Falta --confirmo-copia: este script MODIFICA la base de --url.", file=sys.stderr)
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
