# Arquitectura del Backend

## Resumen

La aplicación sigue una arquitectura simple por capas:

- `app/main.py` ensambla la aplicación FastAPI, CORS y routers.
- `app/core/` concentra configuración, base de datos, seguridad y rate limiting (`rate_limit.py`).
- `app/models/` define el modelo relacional con SQLAlchemy (18 modelos desde la Fase 39; ver `models.py` — User, Account, Category, Transaction, Budget, Fund, FundEntry, tokens y demás).
- `app/schemas/` define contratos de entrada y salida con Pydantic.
- `app/api/` implementa los endpoints por dominio funcional.

## Flujo de autenticación

1. El usuario se registra en `/api/users/`.
2. La contraseña se hashea con bcrypt.
3. El login en `/api/auth/login` verifica credenciales (rate limiting: 5 req/min).
4. Se emite un JWT con `sub = user_id` (expira en 60 min).
5. Se genera un refresh token opaco (expira en 30 días, almacenado hasheado en DB).
6. Las rutas protegidas leen el token con `OAuth2PasswordBearer` y recuperan el usuario desde la base.
7. `/api/auth/refresh` rota el refresh token y emite un nuevo JWT.
8. `/api/auth/logout` revoca el refresh token.

## Decisiones relevantes

- La autenticación se basa en JWT bearer token + refresh token rotation.
- Refresh token: `RefreshToken` model con `token_hash` (SHA-256), `user_id`, `expires_at` (30 días), `revoked_at`. Se almacena hasheado; el token opaco viaja al frontend.
- CORS configurado vía variable de entorno `ALLOWED_ORIGINS` + regex para IPs de Tailscale (100.x.x.x).
- Rate limiting en login via `slowapi` (5 req/min). Instancia `Limiter` en `app/core/rate_limit.py`, registrada en `main.py:127`.
- La base de datos es PostgreSQL en Docker (`postgres:16-alpine`), con fallback a SQLite en ausencia de `DATABASE_URL`.
- El backend hace validación y reglas de negocio en servidor, no en Frontend.
- El dashboard devuelve agregados ya calculados para evitar lógica duplicada en el cliente.
- Los montos se modelan como `Decimal` en contratos y `Numeric(14, 2)` en persistencia para evitar precisión flotante.
- Las categorías base del sistema se siembran al arrancar la aplicación.
- Cada cuenta, transacción y presupuesto almacena su moneda (`currency` column, default "COP").
- Preferencias de usuario: `preferred_currency`, `preferred_locale`, `preferred_theme`, `weekly_summary_enabled` y `timezone` (exponen en `GET/PATCH /api/users/me/preferences`).

## Zona horaria (Fase 34)

- `User.timezone` (migración `a34c0de1b7f2`) es la zona IANA del usuario; `app/core/timezones.py` es el único punto de validación (`es_zona_valida`, `zona_o_default`, `get_zoneinfo`).
- `app/core/periods.py` es el módulo único de aritmética de calendario con zona: funciones puras con `ahora` y la zona inyectados (`resolver_mes`, `rango_mes`, `limites_semana`, `rango_dias`, `dia_local`, `instante_de_dia`, `resolver_rango`). Devuelve datetimes aware en UTC con límite superior exclusivo. Lo consumen `api/dashboard.py`, `api/accounts.py`, `api/transactions.py`, `core/budget_alerts.py` y `core/weekly_summary.py`; ningún otro módulo construye `datetime(...)` naive ni resuelve "actual" desde UTC.
- `core/weekly_summary.py` calcula la semana en la zona de cada usuario (la constante `SUMMARY_TIMEZONE` se eliminó); el cron sigue siendo único (lunes 07:00 `America/Bogota`, `main.py`).
- `tzdata` está en `requirements.txt`: la imagen slim de Docker no trae los alias IANA que lista Chrome (`Asia/Calcutta`, `Europe/Kiev`…); sin él el selector de Ajustes ofrecería zonas que el backend rechaza con `422`. Tras traer este cambio hay que reconstruir la imagen y reinstalar requirements en los venvs locales.
- La migración de datos `c7d3e9a4b1f6` (separada de la del esquema) mueve las fechas históricas `00:00Z` a `17:00Z`; corre sola en el `CMD` de Docker con `alembic upgrade head`. `scripts/fase34_reporte_x1.py` genera el reporte de totales antes/después sobre una copia.

## Sobres y disponible real (Fase 35)

- Tercera capa del producto ("compromiso"): `Fund` y `FundEntry` (migración `d5f2a8c1e703`, aditiva) en `models.py`, que pasa a 15 modelos. No tocan `Transaction`, `Account.balance` ni `services/ledger.py`.
- `app/services/funds.py` concentra toda la lógica en dos mitades: funciones **puras** (`meses_restantes`, `aporte_requerido`, `ritmo`, `progreso`, `meta_efectiva`, `runway`; reciben fechas ya resueltas en la zona del usuario) y casos de uso con DB (`listar`, `detalle`, `crear`, `actualizar`, `registrar_movimiento`, `archivar`, `desarchivar`, `disponibilidad`, `promedio_gasto_mensual`). `api/funds.py` es un router delgado que solo pasa `ahora`.
- Aportar/retirar serializan con `SELECT … FOR UPDATE` sobre la fila del sobre (patrón de la Fase 31); verificado con `tests/test_funds_concurrency.py` (`@pytest.mark.concurrencia`).
- `GET /dashboard/summary` suma `accounts_total`, `committed` y `free_to_spend` llamando a `funds.disponibilidad`.
- **Gasto contra sobre (Fase 36).** `app/api/transactions.py` llama a `app/services/funds.py` (`bloquear_para_gasto`, `aplicar_gasto`, `reajustar_gasto`, `devolver_gasto`, `sincronizar_enlace`, `vinculos`) dentro de su propia transacción SQL; esas funciones no comitean y respetan el orden de locks transacción → sobre → cuentas. Funciones puras nuevas: `monto_a_aplicar` y `delta_reajuste`. Un gasto enlazado es un `withdrawal` con `transaction_id` en el libro (índice `ix_fund_entries_transaction_id`); `vinculos` lo resuelve en una sola consulta agrupada por `(transacción, sobre)` con `HAVING SUM < 0`. `dashboard.py` usa `funds.ids_transacciones_enlazadas` para `planned_expense`, y `promedio_gasto_mensual` excluye esas transacciones. Tests: `tests/test_funds_gasto.py` y `tests/test_funds_gasto_concurrency.py`. Spec: `docs/specs/fase_36_spec.md`.
- `core/periods.mediodia_local` guarda `Fund.target_date` a las 12:00 locales (misma convención que una transacción de otro día).

## Migraciones en runtime (sin Alembic)

En cada arranque, `main.py` ejecuta:

1. `_ensure_user_preference_columns()` — inspecciona columnas de `users` y agrega `preferred_currency`, `preferred_locale`, `preferred_theme` vía `ALTER TABLE ADD COLUMN` si no existen. Permite agregar preferencias nuevas sin romper la DB existente.
2. `seed_default_categories()` — si la tabla `categories` está vacía, inserta las categorías base del sistema (gasto e ingreso).
3. Migración de categorías legacy — renombra `"Otro (Gasto)"` → `"Otro"` y migra transacciones de `"Otro (Ingreso)"` a `"Otro"` con `type=income`.

## Limitaciones conocidas

- No hay sistema de roles o permisos avanzados.
- No hay migraciones automáticas con Alembic (`create_all()` en startup).
- No hay logging estructurado ni observabilidad avanzada.
- La sesión de navegador usa cookies `httpOnly` + CSRF double-submit desde Fase 26 (antes: JWT en `localStorage`, vulnerable a XSS). Los clientes no-browser (API keys `oikos_pat_...`) siguen autenticando por header `Authorization: Bearer` sin cookies.
- Las rutas agregadas del dashboard incluyen resumen, progreso de presupuestos, serie temporal de flujo de caja y distribución por categoría.

## CDT (Fase 38)

- `Cdt` (migración `b4e7a2d9c613`, tabla `cdts`; 17.º modelo). Aislado en la Fase 38; desde la Fase 39 puede vincularse a cuentas (`source_account_id`/`destination_account_id`, migración `c2f8a5d1e764`, 18.º modelo `Transfer`): constituir y redimir crean transferencias y mueven saldos vía `ledger.py`. Sin cuentas vinculadas sigue sin tocarlas.
- `app/services/cdt.py`: funciones **puras** (`dias_transcurridos`, `interes_causado`, `dias_para_vencer`, `alerta`) y casos de uso con DB (`listar`, `crear`, `actualizar`, `redimir`, `eliminar`, `patrimonio`); no comitean. `api/cdt.py` es un router delgado dueño del `commit`.
- `api/dashboard.py` mezcla `cdt.patrimonio(...)` (`cdt_total`, `net_worth`) en el resumen; `free_to_spend`/`committed` no cambian.

## Recurrentes y calendario (Fase 37)

- `RecurringRule` (migración `a9c3d6e1f845`, tabla nueva; 16.º modelo). No toca `Transaction`, `Account.balance` ni `services/ledger.py`: confirmar una ocurrencia crea una transacción normal con `ledger.registrar_impacto`.
- `app/services/recurring.py`: funciones **puras** (`siguiente_ocurrencia`, `primera_desde`, `ocurrencias_en`, `equivalente_mensual`, `es_candidato_anual`; fechas ya resueltas en la zona del usuario, la aritmética de meses vive en `core/periods.py`) y casos de uso con DB (`crear`, `actualizar`, `eliminar`, `pendientes`, `confirmar`, `saltar`, `calendario`, `sugerencias`). `api/recurring.py` es un router delgado dueño del `commit`.
- Las ocurrencias pendientes son **perezosas**: `next_date <= hoy` (no hay job ni tabla de ocurrencias). `confirmar`/`saltar` bloquean la regla (`SELECT … FOR UPDATE`) y exigen `occurrence_date == next_date`; verificado con `tests/test_recurring_concurrency.py` (`@pytest.mark.concurrencia`).

## Transferencias y movimientos (Fase 39)

- Tabla `transfers` (migración `c2f8a5d1e764`; modelo `Transfer`): `user_id`, `from_account_id`/`to_account_id` y `cdt_id` nulables, `amount_out`/`amount_in` con sus monedas, `date`, `description`. `CHECK`s de monto positivo y de extremos (sin CDT: dos cuentas distintas; con CDT: exactamente una) e índices únicos parciales de una constitución y una redención por CDT. Sin soft-delete: el borrado es real. No es flujo: ningún agregado de dashboard, Analítica, presupuestos ni resumen semanal la consulta.
- `app/services/transfers.py`: funciones **puras** (`calcular_monto_entrada`, `tasa_implicita`, `instante_de_fecha`) y casos de uso con DB (`listar`, `detalle`, `crear`, `actualizar`, `eliminar`, `bloquear_cuentas`, `avisos`); no comitean. `bloquear_cuentas` toma `FOR UPDATE` en orden ascendente de id. `api/transfers.py` es un router delgado dueño del `commit` (`DataError` por desborde de `Numeric` -> `422`).
- `services/ledger.py` suma `deltas_transferencia`, `aplicar_deltas` (aplica en orden de `account_id`), `sumar_deltas` e `invertir_deltas`; las ediciones aplican "revertir lo viejo + aplicar lo nuevo" en un solo juego ordenado.
- `app/services/movements.py` + `api/movements.py`: el feed `GET /movements` hace un `UNION ALL` de transacciones y transferencias ordenado y paginado en la base, y luego carga las filas completas de la página.
- `services/cdt.py` importa `bloquear_cuentas` y crea/actualiza/borra las transferencias de constitución y redención del CDT vinculado; al redimir con cuenta crea el ingreso de la categoría base "Rendimientos" con `ledger.registrar_impacto`. Orden de locks: CDT -> transferencia -> cuentas por id.
- "Rendimientos" (ingreso, `user_id = NULL`) está en `core/default_categories.py` y se siembra con el resto del catálogo; `_categoria_rendimientos` la vuelve a sembrar si falta.
- `api/accounts.py`: `reconcile` suma las transferencias, `DELETE` responde `409` y el cambio de moneda `400` si la cuenta tiene transferencias. `core/user_deletion.py` borra las transferencias antes de cuentas y CDT.
- `scripts/fase39_corregir_bancolombia.py`: script de datos de un solo uso del dueño (corrige el saldo inicial de Bancolombia y vincula los CDT reales); tests en `tests/test_fase39_script.py`. Spec: `docs/specs/fase_39_spec.md`.
