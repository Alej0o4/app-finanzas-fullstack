# Spec — Fase 35: sobres virtuales + disponible real

> Primera fase del enfoque "finanzas responsables" (`docs/VISION_FINANZAS_RESPONSABLES.md` §2.1 y
> §2.2, 2026-10-17). Sintetiza un **self-grilling** (sin dueño disponible): las decisiones de
> producto que la visión ya fijaba se citan tal cual; las que estaban abiertas las tomó el agente
> leyendo el código y quedan en "Decisiones tomadas por el agente (pendientes de revisión del
> dueño)". Las marcadas **[REVISAR]** cambian el modelo de datos de forma incómoda de revertir.

**Estado:** **implementada y cerrada el 2026-10-17** (575 tests en Postgres 16; ver "Desvíos y
hallazgos del cierre"). Sin marcadores `[NEEDS CLARIFICATION]`. `/analyze-spec` previo sin
CRÍTICO/ALTO.

---

## Problem Statement

Oikos responde *¿cuánto tengo?* (stock) y *¿cuánto gasté este mes?* (flujo), pero no *¿cuánto de lo
que tengo ya tiene dueño?*. El dinero para el seguro de diciembre, los regalos o el colchón de
emergencia está en una cuenta y la app lo muestra como disponible; el golpe llega cuando vence.

## Solution

Una capa de asignación llamada **sobre** (*fund*) encima de las cuentas, y una cifra derivada:

> **disponible real = saldo de las cuentas − Σ saldos de sobres** (por moneda)

- Un solo concepto con `kind`: `annual_expense` (provisión), `emergency`, `goal`.
- El dinero apartado **no se mueve**: aportar a un sobre no crea transacción ni toca
  `Account.balance`. La fase es **aditiva** (tablas nuevas; no se toca `Transaction`, `ledger.py`
  ni `Account.balance`).
- El saldo de un sobre es `SUM(fund_entries.amount)` de un libro append-only.
- El servidor calcula aporte requerido, estado de ritmo, meta del fondo de emergencia, runway y
  disponible real. El frontend solo presenta.
- `GET /dashboard/summary` suma `committed`, `free_to_spend` y `accounts_total`. El flujo mensual
  **sigue siendo la cifra principal**; el disponible real va como cifra secundaria con desglose.

## User Stories

1. Como dueño quiero crear un sobre "Seguro del carro" con meta $1.800.000 para diciembre, para que
   la app me diga cuánto aportar cada mes.
2. Quiero aportar al sobre con el monto sugerido pre-llenado, sin que se cree un gasto.
3. Quiero ver si voy **al día**, **atrasado** o si ya **cumplí** la meta.
4. Quiero un fondo de emergencia cuya meta sea "3 meses de mi gasto promedio", con progreso y
   runway.
5. Quiero ver en el dashboard cuánto de mi saldo ya está apartado y cuánto es realmente libre.
6. Si el disponible real es negativo, quiero un aviso claro (no un bloqueo).
7. Quiero retirar dinero de un sobre (libera el monto al disponible) y archivar un sobre vacío.
8. Quiero que un sobre no pueda cambiarse de moneda ni quedar apuntando a una cuenta ajena.
9. Quiero saber si una cuenta tiene menos saldo que lo apartado en sus sobres ("sin respaldo").

## Implementation Decisions

Convención de IDs: **B** backend, **F** frontend, **D** decisión de diseño tomada por el agente,
**T** testing, **X** docs.

### Modelo de datos (B1–B3)

**B1. `funds`** (modelo `Fund`; sin `SoftDeleteMixin` — "archivar" es el borrado):

| Columna | Tipo | Notas |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | FK users, NOT NULL, index | |
| `account_id` | FK accounts, NOT NULL, index | cuenta que respalda el sobre |
| `name` | String(100) NOT NULL | recortado, no vacío |
| `kind` | String(20) NOT NULL | CHECK IN (`annual_expense`,`emergency`,`goal`) |
| `currency` | String(3) NOT NULL | = moneda de la cuenta, validado en servicio |
| `target_amount` | Numeric(14,2) NULL | CHECK `> 0` |
| `target_months` | Integer NULL | CHECK `BETWEEN 1 AND 60`; solo `emergency` |
| `target_date` | DateTime(tz) NULL | 12:00 locales del día elegido, UTC |
| `status` | String(10) NOT NULL default `active` | CHECK IN (`active`,`archived`) |
| `created_at`, `updated_at` | DateTime(tz) | mismo patrón que el resto |

CHECK de tabla: `(target_amount IS NOT NULL) <> (target_months IS NOT NULL)` — exactamente uno.
Índice `ix_funds_user_id_status (user_id, status)`.

**B2. `fund_entries`** (modelo `FundEntry`; append-only: la API nunca actualiza ni borra filas):

`id`, `fund_id` (FK, NOT NULL, index), `user_id` (FK, NOT NULL), `amount` Numeric(14,2) con signo
(CHECK `<> 0`), `type` (CHECK IN `contribution`,`withdrawal`,`adjustment`), `occurred_at`
DateTime(tz) default `now()`, `period` String(7) (`YYYY-MM` en la zona del usuario, con
`core/periods.dia_local`), `transaction_id` FK transactions NULL (**siempre NULL en esta fase**;
lo usa la Fase 36), `note` String(200) NULL. CHECK de signo: `contribution` ⇒ `amount > 0`,
`withdrawal` ⇒ `amount < 0`. **Sin** `UNIQUE (fund_id, period)` (permite aportes extra o
quincenales). Índice `ix_fund_entries_fund_id_occurred_at`.

**B3. Migración Alembic** aditiva (`alembic-migration`), `down_revision = "c7d3e9a4b1f6"`, con
`downgrade` que borra `fund_entries` y luego `funds`. Revisada a mano; `alembic check` verde.

### Servicio y errores (B4–B8)

**B4. `app/services/funds.py`** — toda la lógica; el router es delgado:

- Funciones **puras** (con `ahora` y `tz` inyectados; sin `datetime(...)` naive; sin leer el reloj):
  `meses_restantes`, `aporte_requerido`, `ritmo`, `progreso`, `promedio_gasto_mensual_rango`.
- Con DB: `crear`, `actualizar`, `listar`, `detalle`, `aportar`, `retirar`, `archivar`,
  `desarchivar`, `saldos_por_sobre`, `disponibilidad(db, user_id)`.

**B5. Saldo del sobre = `SUM(fund_entries.amount)`**; no hay columna `balance`.

**B6. Aportar y retirar** toman `SELECT ... FOR UPDATE` sobre la fila del sobre (filtrada por
`user_id` y `status`) como **primera** consulta; después calculan el saldo y escriben la entrada en
la misma transacción (patrón de la Fase 31). Retiro > saldo ⇒ `ValidationError` (422) — D5.
Aportar/retirar en un sobre `archived` ⇒ `ConflictError` (409). Un sobre ajeno o inexistente ⇒
`NotFoundError` (404, mismo mensaje: "El sobre no existe o no tienes permisos.").

**B7. Errores solo con `DomainError`** (`NotFoundError`, `ValidationError`, `ConflictError`,
`BadRequestError`); nunca `HTTPException`.

**B8. Schemas** en `app/schemas/funds.py` (re-exportados en el shim `schemas.py`). Validaciones —
D6: nombre 1–100 recortado (`nombre_sin_espacios`); montos `Decimal` `gt=0`, 2 decimales,
`max_digits=MAX_DIGITS_MONEY`; `target_months` 1–60; `note` ≤ 200; `kind` y `status` como `Enum`.

### API (B9–B12) — router `/api/v1/funds`

**B9.** `GET /funds/?include_archived=false` → `list[FundResponse]`; `POST /funds/` → `FundResponse`;
`GET /funds/{id}` → `FundDetailResponse` (= `FundResponse` + `entries`: las 50 más recientes);
`PUT /funds/{id}` (actualización parcial por `model_fields_set`: `name`, `target_amount`,
`target_months`, `target_date`, `account_id`; **no** cambia `kind` ni la moneda).
`POST /funds/{id}/contributions` y `/withdrawals` con body `{ amount, note? }` → `FundEntryResponse`.
`POST /funds/{id}/archive` (exige saldo 0, si no 409) y `/unarchive`. No hay `DELETE`.
Rutas fijas declaradas antes de `/{id}` (convención de `accounts.py`).

**B10. `FundResponse`:** `id, name, kind, status, account_id, currency, balance, target_amount`
(efectivo: para `target_months` es `months × promedio`, `null` si no hay historial), `target_months`,
`target_date` (`YYYY-MM-DD` en la zona del usuario o `null`), `progress_pct` (0–100 capado, `null`
sin meta), `remaining` (`max(meta − saldo, 0)`), `months_remaining`, `required_contribution`,
`pace` (`completed`/`on_track`/`behind`/`null`), `monthly_expense_avg` y `runway_months` (solo
`emergency`), `backing_shortfall` (D4), `created_at`.

**B11. Dashboard.** `DashboardSummary` suma tres listas `list[BalanceByCurrency]`, ordenadas con la
moneda preferida primero: `accounts_total` (Σ saldo de **todas** las cuentas — D1), `committed`
(Σ saldo de sobres activos) y `free_to_spend` (= `accounts_total − committed`, por moneda; incluye
monedas que solo aparecen en un lado). Sin parámetros nuevos: es una foto de hoy, no del mes
consultado. `balances` (cuentas destacadas) **no cambia**.

**B12. Cascadas.** `user_deletion.delete_user_cascade` borra `fund_entries` y luego `funds` antes
que `Account`/`Transaction`. `DELETE /accounts/{id}` devuelve `BadRequestError` si la cuenta tiene
sobres **activos** (D4). `main.py` monta el router. `seed.py` no cambia.

### Frontend (F1–F6)

**F1.** `types/api.ts`: `Fund`, `FundDetail`, `FundEntry` y los campos nuevos de `DashboardSummary`.
**F2.** `lib/queryKeys.ts` + `lib/hooks/useFunds.ts` (`useFunds`, `useFund`), siguiendo
`useAccounts`.
**F3.** `/funds` (lista: tarjetas con barra de progreso, estado, aporte requerido, "sobre sin
respaldo", estado vacío, `QueryErrorState`) y `/funds/[id]` (detalle: métricas + movimientos).
**F4.** Modales (`ModalShell`): crear/editar sobre, aportar (monto sugerido pre-llenado), retirar;
archivar con `ConfirmDialog`. El botón de envío se deshabilita mientras la mutación está pendiente.
**F5.** Dashboard: tarjeta secundaria "Disponible real" junto al flujo, con desglose (saldo en
cuentas − apartado) en la moneda preferida; si es negativa, mensaje explicativo (no bloquea).
**F6.** `Sidebar`: ítem "Sobres" (bloque primario). Invalidaciones: toda mutación de sobre
invalida `funds`, `dashboardSummary`; mutaciones de cuentas/transacciones ya invalidan
`dashboardSummary`. Textos en tuteo.

### Decisiones tomadas por el agente (pendientes de revisión del dueño)

**D1. Qué saldos entran al "saldo de las cuentas".** *Todas* las cuentas activas del usuario, por
moneda (Σ `Account.balance`), **no** solo las destacadas. Razón: los sobres cuelgan de cualquier
cuenta; restar de las destacadas a sobres de no destacadas daría un disponible falso. Descartado:
filtrar por destacadas como `balances` (inconsistente con el universo de `committed`). Las cuentas de
tipo `credit` cuentan igual que en `GET /accounts/summary` (**[REVISAR]**: si el dueño usa crédito con
saldo de deuda, hay que decidir si restan). **Selector de moneda (Fase 29):** el endpoint devuelve
todas las monedas; el dashboard muestra la preferida primero y las demás como filas secundarias. No
se convierte entre monedas (regla del repo).

**D2. Ritmo (`al día`/`atrasado`/`cumplido`).** `pace = completed` si `saldo ≥ meta`. Si no hay
`target_date` o no hay meta ⇒ `pace = null` y `required_contribution = null` (no hay ritmo sin
fecha). Si hay fecha: ritmo **lineal por días** desde el día de creación (en la zona del usuario)
hasta `target_date`: `esperado = meta × clamp((hoy − creación) / (fecha − creación), 0, 1)` (si
fecha ≤ creación, `esperado = meta`); `behind` si `saldo < esperado` truncado a centavo, si no
`on_track`. `target_date` pasada y sin cumplir ⇒ `behind`. **Meses restantes** = diferencia de
meses calendario entre el mes actual y el mes de `target_date` (zona del usuario), mínimo 1 si la
fecha no ha pasado; 0 si ya pasó. **Aporte requerido** = `remaining / max(meses_restantes, 1)`
redondeado hacia arriba al centavo (`ROUND_CEILING`); `null` si no hay fecha o `remaining = 0`.
Descartado: estado basado en "aportaste este mes" (castiga al que aporta quincenal y exige un cron).

**D3. Meta del fondo de emergencia en meses.** `target_months` (1–60) en `emergency`; meta efectiva
= `target_months × monthly_expense_avg`. `monthly_expense_avg` = gasto total (`type = expense`, moneda
del sobre, todas las cuentas) de los **hasta 3 meses completos anteriores** al actual (zona del
usuario) ÷ N, con N = cantidad de esos meses que caen en o después del mes de la primera
transacción del usuario. N = 0 (cuenta nueva) o gasto 0 ⇒ `monthly_expense_avg = null`,
`target_amount = null`, `pace = null`, `runway_months = null` y la UI explica "Aún no hay historial
completo de gastos". `runway_months = saldo / monthly_expense_avg` (1 decimal). "Gasto esencial"
(excluir lo no esencial) queda como deuda en `docs/TODO.md`: Oikos no tiene clasificación
necesidad/deseo. Un `emergency` también puede usar `target_amount` fijo. Sin tope de un fondo de
emergencia por usuario.

**D4. Archivar, borrar y "sin respaldo".** Archivar exige **saldo 0** (si no, 409 "Retira el saldo
antes de archivar"): retirar es lo que libera el dinero al disponible; así nunca hay saldo
"huérfano". Un archivado se puede desarchivar. No hay borrado de sobres (el libro es histórico).
No se puede borrar una cuenta con sobres activos (400). Aparte, el saldo de una cuenta puede bajar de
lo apartado en sus sobres (gastaste de ella): `backing_shortfall` = `max(Σ sobres activos de esa
cuenta − saldo de la cuenta, 0)`, que la UI muestra como alerta "sobre sin respaldo". Descartado:
bloquear gastos que dejen sobres sin respaldo (ver "disponible negativo no bloquea nada").

**D5. Retiro mayor al saldo.** `ValidationError` (422): "El sobre solo tiene $X apartado." Un retiro
nunca deja el saldo negativo. Un aporte sí puede superar la meta o el saldo libre de la cuenta (no
bloquea nada).

**D6. Validaciones.** Ver B8. `kind ≠ emergency` exige `target_amount` y rechaza `target_months`
(422). `target_amount` XOR `target_months` también en CHECK de DB. `target_date` nueva debe ser hoy
o posterior (zona del usuario) — solo se valida cuando se envía el campo, así editar un sobre vencido
no falla. Moneda del sobre = la de su cuenta; `PUT` con otra cuenta exige misma moneda (422).
Aportes con moneda: no se envía, se hereda. Cuenta ajena ⇒ `AccountNotFoundError`.

**D7. Sin idempotencia por request.** `IdempotencyKey` tiene `transaction_id NOT NULL` (es de
transacciones), así que reutilizarla exige cambiar esa tabla. Un aporte duplicado por doble clic se
previene en el frontend (botón deshabilitado) y se corrige con un retiro. Descartado: header
`Idempotency-Key` en sobres (fase futura si hace falta).

**D8. `status` solo `active`/`archived`.** La visión listaba `completed`; se **deriva** (`pace =
completed`) porque un estado guardado se desincroniza con cada retiro. **[REVISAR]** (cambia el
vocabulario de la visión, no el esquema difícil de revertir).

**D9. `target_date` guardada como instante** (12:00 locales del día elegido, igual que una
transacción de otro día en la Fase 34), expuesta como día `YYYY-MM-DD` en la zona del usuario.
`occurred_at` = ahora; sin fecha elegida en aportes/retiros.

**D10. Tipo `adjustment`.** Existe en el CHECK pero la API no lo expone en esta fase (reservado para
reconciliación); sin endpoint.

### Docs (X1–X3)

**X1.** `backend/docs/API_REFERENCE.md` **y** `frontend/docs/API_CONTRACT.md`: `/funds/*` y los tres
campos del summary. **X2.** `backend/docs/BUSINESS_RULES.md`: invariantes de sobres/disponible.
`ARCHITECTURE.md` de backend y frontend, `STATE_AND_FETCHING.md` (keys e invalidaciones).
**X3.** `CHANGELOG`, `ROADMAP`, `TODO`, `AGENTS.md`, `VISION_FINANZAS_RESPONSABLES.md`.

## Testing Decisions

- **T1. Funciones puras** (TDD, sin DB, `ahora` fijo): `meses_restantes` (mismo mes, mes siguiente,
  cruce de año, fecha pasada, zonas distintas), `aporte_requerido` (redondeo hacia arriba, sin
  fecha, meta cumplida), `ritmo` (on_track/behind/completed, fecha ≤ creación, sin fecha).
- **T2. API:** crear/listar/editar; validaciones (kind/target xor, monto ≤ 0, nombre vacío, moneda
  distinta en `PUT`, cuenta ajena); aporte y retiro; retiro > saldo ⇒ 422; archivar con saldo ⇒ 409;
  aportar a archivado ⇒ 409; saldo = suma de entradas; `Account.balance` intacto tras aportar/
  retirar; no se crea transacción.
- **T3. Disponible real:** `committed`/`free_to_spend`/`accounts_total` por moneda; negativo; sobre
  en moneda distinta a la preferida; no cambia con `?month=`; `balances` sigue filtrando por
  destacadas.
- **T4. Aislamiento:** un usuario no ve, edita, aporta, retira ni archiva sobres ajenos (404); no
  puede usar una cuenta ajena.
- **T5. Fondo de emergencia:** promedio de 3 meses completos con transacciones sembradas, historial
  menor a 3 meses, sin historial (`null`), zona del usuario en la frontera de mes.
- **T6. `@pytest.mark.concurrencia`:** 8 retiros paralelos de un sobre con saldo para 2 ⇒ exactamente
  2 éxitos y saldo final correcto; aportes paralelos suman exacto.
- **T7. Cascadas:** `delete_user_cascade` con sobres; borrar cuenta con sobre activo ⇒ 400; con
  sobre archivado ⇒ ok.
- **T8. Migración:** `alembic check` (ya en `test_migrations.py`) más upgrade/downgrade manual.
- **T9. Frontend:** `pnpm lint`/`prettier`; verificación manual en navegador (ver Orden, paso 12).

## Out of Scope

Gasto contra sobre / enlazar transacciones (Fase 36), recurrentes, CDT, "págate primero", cierre de
mes, cron o aporte automático, clasificación necesidad/deseo, idempotencia por header, conversión
entre monedas, endpoint de ajustes, seguridad/auth.

## Further Notes

- Mutaciones de cuentas/transacciones no tocan sobres; el disponible se recalcula al leer.
- Despliegue: la migración corre sola en el `CMD` de Docker; pedir `pg_dump` previo.

## Desvíos y hallazgos del cierre (2026-10-17)

`/analyze-spec 35 cierre`: sin decisiones faltantes ni parciales; los desvíos de abajo son
refinamientos hallados en la verificación en navegador y en `/code-review`, todos corregidos y con test.

- **D4 refinada:** `backing_shortfall` nunca excede lo apartado en la cuenta (una cuenta con saldo
  negativo sin nada apartado no está "sin respaldo") y vale `0` en sobres archivados.
- **Guards agregados a B12:** no se cambia la moneda de una cuenta con sobres (`PUT /accounts` y
  `apply_to_default_account` de preferencias); un sobre archivado no se edita (409) y `unarchive`
  revalida que la moneda de la cuenta coincida; `crear`/mover un sobre y `DELETE /accounts/{id}` toman
  `FOR UPDATE` de la cuenta para no dejar un sobre activo sobre una cuenta borrada.
- **Frontend:** la key `funds.byId` normaliza el id a string (la página lo lee de la URL y las
  mutaciones lo traen numérico: la invalidación no matcheaba y el detalle quedaba viejo); las queries
  de sobres usan `staleTime: 0` (el respaldo depende de cuentas/transacciones, que no las invalidan);
  `AvailableCard` decide "tiene sobres" con `useFunds()` (un sobre recién creado tiene `committed = 0`).
- **D2 refinada (segunda revisión):** `required_contribution` es la cuota de **este mes**: se calcula
  con el saldo de inicio de mes y se le resta lo ya aportado (neto de aportes y retiros del período
  `YYYY-MM` en la zona del usuario); llega a `null` al cumplir la cuota. Frontend: Editar no se ofrece en
  archivados, el cambio de zona invalida las queries de sobres, y el estado vacío de la tarjeta solo se
  muestra con la lista cargada y vacía.
- **Hallazgos aceptados por escrito:** (a) un sobre archivado bloquea el cambio de moneda de su cuenta
  y, si la cuenta se borra teniendo solo archivados, quedan sin reactivar — coherente con la limitación
  ya existente de cuentas con transacciones; (b) `_construir` hace 4-6 queries por llamada —
  irrelevante a esta escala.
- **`core/periods.mediodia_local`** se agregó como helper (D9); `instante_de_dia` lo reutiliza.
- **Verificación T9:** el MCP de Playwright no conectó; se usó Playwright por node (fuera del repo)
  contra un stack dev aislado (`-p oikos-dev-f35`, ambos `-f`), en escritorio y 390 px, oscuro/claro.
- **Migración (T8):** upgrade → downgrade → upgrade → `alembic check` sobre un Postgres desechable.

## Orden de ejecución

1. [backend] `models.py` (`Fund`, `FundEntry`) + migración Alembic — B1, B2, B3.
   Depende de: —
2. [backend] `app/services/funds.py` funciones puras (TDD) — B4, D2, D3.
   Depende de: —  (se puede escribir antes que el modelo)
3. [backend] `schemas/funds.py` + shim — B8, B10, D6.
   Depende de: 1
4. [backend] servicio con DB (`crear`…`disponibilidad`, locks) — B4, B5, B6, B7, D4, D5, D7, D10.
   Depende de: 1, 2, 3
5. [backend] `api/funds.py` + `main.py` — B9, D8, D9.
   Depende de: 4
6. [backend] dashboard summary + `user_deletion` + guard en `accounts.py` — B11, B12, D1.
   Depende de: 4
7. [backend] tests T1–T8.
   Depende de: 5, 6
8. [frontend] tipos, keys, hooks — F1, F2.
   Depende de: 5  (contrato)
9. [frontend] [P] páginas `/funds` y `/funds/[id]` + modales — F3, F4, F6.
   Depende de: 8
10. [frontend] [P] tarjeta de disponible real en dashboard — F5.
    Depende de: 8, 6
11. [docs] contratos y docs de arquitectura — X1, X2.
    Depende de: 5, 6
12. [verif] `/run-tests`, navegador (crear → aportar → disponible baja → retirar → archivar; vacío,
    error, 390 px, oscuro), `/code-review`, `/analyze-spec 35 cierre` — T9.
    Depende de: 7, 9, 10, 11
13. [docs] cierre (CHANGELOG, ROADMAP, TODO, AGENTS, VISION), `graphify update .`, PR — X3.
    Depende de: 12
