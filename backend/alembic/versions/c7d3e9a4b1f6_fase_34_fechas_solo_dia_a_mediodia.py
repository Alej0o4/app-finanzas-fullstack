"""fase_34_fechas_solo_dia_a_mediodia

Revision ID: c7d3e9a4b1f6
Revises: a34c0de1b7f2
Create Date: 2026-10-04 00:00:00.000000

Migración de DATOS (no de esquema), separada de la columna `users.timezone` a propósito para
poder revertirse sin tocar el resto de la fase (docs/specs/fase_34_spec.md, Decisiones X1/X2).

Antes de la Fase 34 el modal mandaba `YYYY-MM-DD` y el backend lo guardaba a las `00:00 UTC`,
que en Bogotá (UTC-5) es la noche del día anterior: el gasto se veía un día corrido. Desde la
Fase 34 un día pasado se guarda a las 12:00 locales (`17:00Z` en Bogotá). Esta migración pone
las filas históricas en ese mismo criterio: toda `transactions.date` que sea EXACTAMENTE
`00:00:00.000000Z` pasa a las `17:00:00Z` DEL MISMO DÍA UTC (el día que el usuario tecleó se
conserva; es la razón de elegir esta conversión). Incluye las filas borradas lógicamente (el SQL
crudo no pasa por el filtro del ORM). Los saldos de cuenta no dependen de la hora y no cambian;
`updated_at` tampoco se toca.

Efecto conocido y aceptado (X2): un gasto del primer día de un mes cargado a medianoche UTC
contaba en el mes ANTERIOR en hora Bogotá; tras esto cuenta en su mes. Algunos totales
históricos de borde cambian a su valor correcto.

Idempotente por construcción: tras aplicarla no queda ninguna fila a `00:00:00Z` exacta, así que
volver a correr el UPDATE no toca nada. `downgrade` es simétrico (`17:00:00Z` exacta →
`00:00:00Z` del mismo día). Falso positivo aceptado del downgrade: una fila REAL registrada
exactamente a las `17:00:00.000000Z` también volvería a medianoche (prácticamente imposible con
`now()`).

Ramas por dialecto: Postgres (`timestamptz`) y SQLite (el opt-in offline guarda texto
`YYYY-MM-DD HH:MM:SS[.ffffff]` sin zona, siempre UTC) — para que `alembic check`/los tests
migren en los dos motores.

Probar SIEMPRE contra una copia o un Postgres desechable antes de producción (X3): ver
`scripts/fase34_reporte_x1.py`.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d3e9a4b1f6"
down_revision: str | None = "a34c0de1b7f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _mover(desde: str, hacia: str) -> None:
    """Mueve las filas cuya hora UTC es exactamente `desde` (`HH:MM:SS`) a `hacia` el mismo día UTC."""
    if op.get_bind().dialect.name == "postgresql":
        # `AT TIME ZONE 'UTC'` pasa el timestamptz a hora de reloj UTC sin depender de la zona
        # de la sesión; `::time` conserva los microsegundos, así que la igualdad es exacta.
        op.execute(
            f"""
            UPDATE transactions
            SET date = ((date AT TIME ZONE 'UTC')::date + TIME '{hacia}') AT TIME ZONE 'UTC'
            WHERE (date AT TIME ZONE 'UTC')::time = TIME '{desde}'
            """
        )
    else:
        op.execute(
            f"""
            UPDATE transactions
            SET date = substr(date, 1, 11) || '{hacia}.000000'
            WHERE substr(date, 12) IN ('{desde}', '{desde}.000000')
            """
        )


def upgrade() -> None:
    _mover("00:00:00", "17:00:00")


def downgrade() -> None:
    _mover("17:00:00", "00:00:00")
