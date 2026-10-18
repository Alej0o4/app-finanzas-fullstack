# Spec — Fase 38: CDT (módulo independiente)

> Cuarta fase del enfoque "finanzas responsables" (`docs/VISION_FINANZAS_RESPONSABLES.md` §2.5).
> **Aditiva y aislada**: una tabla nueva (`cdts`), un servicio nuevo (`app/services/cdt.py`) y un
> router nuevo (`/api/v1/cdts`). **No modifica** `Transaction`, `Account.balance` ni `ledger.py`;
> no toca sobres, el fondo de emergencia ni el disponible real. Lo único que cambia en una cifra
> existente es que `GET /dashboard/summary` **suma** dos campos nuevos (`cdt_total`, `net_worth`).

**Estado:** especificada el 2026-10-18. **Sin `/grilling` con el dueño**: las decisiones D1–D16 las tomó el agente contra el código y la visión (precedente: Fases 35 y 37) y esperan su revisión. Marcadores `[NEEDS CLARIFICATION]` abiertos: ninguno (los puntos de producto tienen un default conservador y reversible).

---

## Problem Statement

Un CDT inmoviliza dinero hasta su vencimiento, y hoy Oikos no lo ve en ninguna parte: ese capital
sale del radar de "¿cuánto tengo?", no se sabe cuánto ha rendido ni cuándo se libera, y el
vencimiento se descubre cuando el banco avisa (o no). Mezclarlo con el fondo de emergencia sería
un error: el fondo es dinero disponible en horas y un CDT no lo es.

## Solution

Un módulo propio para registrar CDT: nombre/entidad, moneda, capital, tasa E.A., fecha de apertura
y de vencimiento. El backend calcula el **interés causado a hoy** (rendimiento informativo), el
valor al vencimiento, los días que faltan y un **estado de aviso** (`ok` / `due_soon` ≤ 15 días /
`matured`). Cuando vence, el dueño lo **redime**: el CDT pasa a `redeemed` con la fecha y el monto
final. El CDT suma al **patrimonio total** (vista de stock, campo `net_worth` del dashboard) y **no**
al disponible real ni al fondo de emergencia.

## User Stories

1. Registrar "CDT Bancolombia, $10.000.000, 11,5 % E.A., del 2026-06-01 al 2026-12-01".
2. Ver cuánto ha rendido a hoy, cuánto valdrá al vencimiento y en cuántos días vence.
3. Ver un aviso claro cuando faltan 15 días o menos, y cuando ya venció sin redimir.
4. Redimirlo (a tiempo o anticipado) registrando la fecha y el monto final recibido.
5. Ver mi patrimonio total (cuentas + CDT vigentes) sin que el CDT cuente como dinero disponible.
6. Corregir un dato mal digitado mientras el CDT esté vigente; borrar uno creado por error.
7. Tener CDT en dólares sin mezclar monedas.

## Implementation Decisions

Convención de IDs: **D** decisión, **B** backend, **F** frontend, **T** testing, **X** docs.

### Decisiones tomadas por el agente, pendientes de revisión del dueño

**D1 — El CDT es una tabla propia y no toca el libro contable.** `cdts` no referencia cuentas
ni transacciones. Crear, editar, redimir o borrar un CDT **no** mueve `Account.balance`, no crea
`Transaction` y no usa `ledger.py`. Justificación: sin transferencias entre cuentas (QA-030) no hay
forma honesta de "sacar" el capital de una cuenta sin registrarlo como gasto (que distorsionaría
los KPI de flujo); la visión §2.5 pide exactamente este aislamiento. *Consecuencia aceptada:* el
dueño es responsable de que el capital ya no figure en el saldo de ninguna cuenta (p. ej. con el
ajuste de saldo de la cuenta); la UI lo avisa al crear. *Alternativa descartada:* campo
`account_id` + descontar del saldo — acopla el módulo al ledger.

**D2 — Interés causado: E.A. compuesto diario, base 365, `Decimal`, bruto.** Con `r = tasa_ea/100`
y `d` = días transcurridos: `interes = capital × ((1 + r)^(d/365) − 1)`, calculado con
`Decimal.ln()/exp()` (precisión de contexto 28) y redondeado a centavo `ROUND_HALF_UP`. `d` =
`dia_local(hoy) − opened_on` acotado a `[0, plazo]` (después del vencimiento el interés deja de
causarse; antes de abrir vale 0). **Bruto**: sin retención en la fuente, GMF ni comisiones.
Justificación: es la definición estándar de E.A.; el neto depende de reglas fiscales que no se
modelan. Es una función pura (TDD). Fechas de calendario (`Date`), "hoy" de `periods.dia_local`
con `ahora` inyectado y la zona del usuario.

**D3 — Vencimiento solo en la UI: sin job, sin push, sin fila en `notifications`.** El backend
expone `days_to_maturity` y `alert` (`ok` | `due_soon` ≤ 15 días | `matured` si `maturity_on ≤
hoy` y sigue vigente); la UI muestra banner/insignia y una tarjeta en el dashboard. Justificación:
mismo criterio que Fase 37 (D2): el scheduler sigue siendo uno solo y se evita escribir en un GET.
*Deuda anotada en TODO:* push/aviso en la bandeja si el dueño lo pide.

**D4 — Redimir solo cambia de estado y guarda el monto final.** `POST /cdts/{id}/redeem` con
`{redeemed_on?: date, final_amount?: Decimal}`: `status → redeemed`, `redeemed_on` (por defecto hoy;
no antes de `opened_on` ni futura) y `final_amount` (por defecto capital + interés causado a
`redeemed_on`; el dueño puede corregirlo con lo que el banco realmente pagó, ya neto). **No crea
transacción ni ingreso** y no mueve saldos (D1). Justificación (conservadora): registrar el retorno
como ingreso inflaría el flujo mensual con capital propio, y el reingreso del capital a una cuenta
necesita transferencias (QA-030). El interés realizado (`final_amount − principal`) queda
disponible para esa fase. Se puede redimir antes o después del vencimiento. No hay "deshacer";
si fue un error se borra y se recrea.

**D5 — Patrimonio total = cuentas + CDT vigentes.** Un CDT `active` aporta `principal +
interés causado a hoy` a `cdt_total` (por moneda); `net_worth = accounts_total + cdt_total`. Un CDT
redimido deja de contar (su dinero volvió a una cuenta, o se registró aparte). **`free_to_spend`,
`committed`, `balances` y el fondo de emergencia no cambian** (invariante probada en test).
`GET /dashboard/summary` agrega `cdt_total` y `net_worth` (listas `BalanceByCurrency`, sobre todas
las cuentas/CDT, foto de HOY, ignoran `?year=&month=`, como `accounts_total`).

**D6 — Moneda propia por CDT, sin conversión.** `currency` (patrón `CURRENCY_PATTERN` de Cuentas,
default `COP`). Los totales se agrupan por moneda; nunca se suman monedas.

**D7 — Tasa como porcentaje E.A.** `rate_ea` `Numeric(7,4)`, en puntos porcentuales (`11.5` = 11,5 %),
`0 < rate_ea ≤ 100`. `0` se rechaza (un CDT sin rendimiento no tiene sentido aquí).

**D8 — Validaciones de fechas y monto.** `maturity_on > opened_on` y plazo ≤ 10 años; `opened_on`
entre hoy − 10 años y hoy + 1 año (se permite registrar uno que abre mañana); `principal > 0` con los
límites de dinero (`MAX_DIGITS_MONEY`, `decimal_places=2`). Todo `422` con `ValidationError`.

**D9 — Edición solo mientras está vigente.** `PUT` permite cambiar nombre, moneda, capital, tasa y
fechas de un CDT `active` (se cometen errores al digitar); uno `redeemed` responde `409`. Sin
historial de cambios.

**D10 — Borrar es real.** `DELETE /cdts/{id}` borra la fila en cualquier estado, sin tocar nada más
(D1). Sin `SoftDeleteMixin`.

**D11 — Tope de 50 CDT por usuario** (`422`), como los 100 de recurrentes: guarda de abuso barata.

**D12 — Lista y totales.** `GET /cdts?status=active|redeemed` (sin parámetro: todos; vigentes
primero por vencimiento ascendente, luego redimidos por `redeemed_on` descendente). Respuesta
`{items, totals}`; `totals` por moneda **solo de los vigentes**: `principal`, `accrued_interest`,
`current_value` (capital + interés) y `maturity_value`. Cada ítem trae: campos propios,
`term_days`, `elapsed_days`, `accrued_interest`, `current_value`, `maturity_interest`,
`maturity_value`, `days_to_maturity` (negativo si ya venció, `null` si está redimido), `alert`.
El frontend **no recalcula** ninguna de estas cifras.

**D13 — Aislado de sobres y recurrentes.** Borrar una cuenta o categoría no se ve afectado (no hay
FK). Borrar el usuario (`core/user_deletion.py`) borra sus CDT. El seed de dev crea CDT.

**D14 — Interés realizado en redimidos.** Un ítem `redeemed` expone `final_amount` y
`realized_interest = final_amount − principal` (puede ser < 0 si hubo penalización por redimir
anticipado); no entra en `totals`.

**D15 — Zona horaria.** `opened_on`, `maturity_on`, `redeemed_on` son `Date` en la zona del
usuario. Prohibido construir `datetime` naive o resolver "hoy" desde UTC fuera de `core/periods.py`.
Cambiar la zona no mueve las fechas guardadas.

**D16 — Frontend.** Página `/cdts` (entrada "CDT" en el Sidebar): tarjetas vigentes con barra de
progreso del plazo, rendimiento a hoy, valor al vencimiento y estado de aviso; sección de
redimidos; formulario crear/editar; modal de redención; borrar con confirmación accesible. Aviso en
el formulario de creación sobre D1. Dashboard: línea de "Patrimonio total" (`net_worth`) y tarjeta
"N CDT por vencer" cuando alguno está en `due_soon` o `matured`. Invalidaciones: toda mutación de
CDT invalida `cdts` y `dashboard`; ninguna toca `accounts`/`transactions`/`funds`.

### Modelo de datos (B1)

**B1. Migración Alembic** (`alembic-migration`), `down_revision = "a9c3d6e1f845"`: tabla `cdts`:

| Columna | Tipo | Notas |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | FK `users.id`, NOT NULL | |
| `name` | String(100), NOT NULL | |
| `currency` | String(3), NOT NULL | |
| `principal` | Numeric(14,2), NOT NULL | CHECK `> 0` |
| `rate_ea` | Numeric(7,4), NOT NULL | CHECK `> 0 AND <= 100` |
| `opened_on` | Date, NOT NULL | |
| `maturity_on` | Date, NOT NULL | CHECK `maturity_on > opened_on` |
| `status` | String(10), NOT NULL, default `active` | CHECK `IN ('active','redeemed')` |
| `redeemed_on` | Date, NULL | |
| `final_amount` | Numeric(14,2), NULL | CHECK `IS NULL OR >= 0` |
| `created_at`, `updated_at` | DateTime(tz) | patrón de `Fund` |

CHECK de coherencia: `(status = 'redeemed') = (redeemed_on IS NOT NULL AND final_amount IS NOT NULL)`.
Índice `ix_cdts_user_id_status`. `downgrade` borra índice y tabla; `alembic check` verde. Pasa de
16 a 17 modelos (actualizar la cifra en `AGENTS.md` y en la arquitectura).

### Servicio (B2–B5) — `app/services/cdt.py`

**B2. Funciones puras** (sin DB, TDD, fechas inyectadas): `dias_transcurridos(opened_on, maturity_on,
hoy)` (acotado, D2), `interes_causado(capital, tasa_ea, dias)` (D2), `alerta(maturity_on, hoy,
estado)` (D3), `dias_para_vencer(maturity_on, hoy)`.
**B3. Con DB** (no comitean; el router es dueño del `commit`): `listar`, `crear`, `actualizar`,
`redimir`, `eliminar`, `patrimonio(db, user, ahora, moneda_preferida)` (D5). `actualizar` y
`redimir` toman `SELECT … FOR UPDATE` de la fila (un `redeem` doble → el segundo `409`).
**B4. Errores solo `DomainError`** (`NotFoundError`, `ConflictError`, `ValidationError`).
**B5. Zona horaria** vía `periods.dia_local` con `ahora` inyectado (D15).

### API (B6–B8)

**B6. `schemas/cdt.py`** (re-export en `schemas/schemas.py`): `CdtCreate`, `CdtUpdate` (`extra="forbid"`),
`CdtRedeem`, `CdtResponse`, `CdtTotals`, `CdtListResponse`; `DashboardSummary` suma `cdt_total` y
`net_worth` (sin default, como `accounts_total`).
**B7. `api/cdt.py`** (delgado, `/api/v1/cdts`, tag "CDT"):

| Método y ruta | Qué hace |
|---|---|
| `GET /` | lista + totales (D12) |
| `POST /` | crea (D6–D8, D11) |
| `PUT /{id}` | edita un vigente (D9) |
| `POST /{id}/redeem` | redime (D4) |
| `DELETE /{id}` | borra (D10) |

**B8. `main.py`** monta el router; `api/dashboard.py` mezcla `cdt.patrimonio(...)` en el resumen;
`core/user_deletion.py` borra los CDT del usuario; `core/seed.py` agrega CDT (vigente, por vencer,
vencido sin redimir, redimido con rendimiento, en USD).

### Frontend (F1–F4)

**F1.** Tipos regenerados (`pnpm gen:types` contra el backend de dev `:8001`), `lib/hooks/useCdts.ts`,
claves en `lib/queryKeys.ts`. **F2.** Página `/cdts`, Sidebar, tarjetas y estados vacío/carga/error
(`QueryErrorState`). **F3.** `CdtFormModal`, `CdtRedeemModal`, borrar con confirmación accesible.
**F4.** Dashboard: patrimonio total y tarjeta "CDT por vencer". `STATE_AND_FETCHING.md` y
`COMPONENTS_GUIDE.md` actualizados.

## Testing Decisions

Backend en Postgres 16 (testcontainers). T1 con TDD.

- **T1.** Puras: interés (0 días = 0; 365 días = r exacto; plazo completo; redondeo; acotado tras vencer; antes de abrir = 0), `alerta` (borde 15/16 días, vencido, redimido), `dias_para_vencer`.
- **T2.** CRUD: validaciones (`rate_ea` 0/101, `maturity ≤ opened`, plazo > 10 años, monto `≤ 0`/exceso, moneda inválida, tope 50), aislamiento entre usuarios (`404`), editar vigente / `409` si redimido.
- **T3.** `redeem`: defaults, `final_amount` explícito, fecha futura/anterior a apertura `422`, doble redención `409`, **no crea transacción ni cambia saldo**.
- **T4.** Lista/totales por moneda solo de vigentes, orden, zona horaria en el borde de día (hoy local ≠ UTC).
- **T5.** Dashboard: `cdt_total`/`net_worth` correctos; **`free_to_spend`, `committed`, `balances` y `/funds` no cambian por tener CDT** (contrato); redimido no cuenta.
- **T6.** `concurrencia`: dos `redeem` simultáneos → un `200` y un `409`.
- **T7.** Migración sube/baja y `alembic check`; borrado de usuario con CDT; seed.
- **T8.** Navegador (Playwright) a 390 px y desktop: crear, aviso por vencer, redimir, borrar, dashboard.

## Out of Scope

- Cualquier otro instrumento (fondos, acciones, cripto); tracking de inversiones.
- Transferencias entre cuentas, registrar el reingreso del capital o el interés como ingreso (QA-030, futuro).
- Retención en la fuente, GMF, interés neto, renovación automática, CDT con pago periódico de intereses.
- Push o fila en `notifications` por vencimiento; job nuevo en el scheduler.
- Conversión de moneda; incluir el CDT en el fondo de emergencia o el disponible real (decidido: nunca).
- Seguridad/auth/hardening y Fases 39+.

## Further Notes

- El `scheduler` sigue siendo uno solo (resumen semanal).
- Despliegue (pasos del dueño): `pg_dump` previo; la migración corre sola en el `CMD` de Docker;
  reconstruir la imagen (solo código, sin dependencias nuevas).

---

## Orden de ejecución

1. [backend] `models.py` (`Cdt`) + migración Alembic — D6–D8, B1.
   Depende de: —
2. [backend] [P] `services/cdt.py` funciones puras con TDD (T1) — D2, D3, B2.
   Depende de: —
3. [backend] `schemas/cdt.py` + re-export + campos del dashboard — D5, D12, B6.
   Depende de: 1
4. [backend] `services/cdt.py` con DB — D1, D4, D5, D9–D12, D14, D15, B3–B5.
   Depende de: 1, 2, 3
5. [backend] `api/cdt.py`, montaje, dashboard, `user_deletion`, seed — D13, B7, B8.
   Depende de: 4
6. [backend] tests T2–T7.
   Depende de: 5
7. [frontend] tipos, hooks, claves de query e invalidaciones — D16, F1.
   Depende de: 5
8. [frontend] [P] página `/cdts`, Sidebar, tarjetas — D3, D12, D14, D16, F2.
   Depende de: 7
9. [frontend] [P] formulario, redención, borrado — D1, D4, D9, D10, D16, F3.
   Depende de: 7
10. [frontend] [P] dashboard (patrimonio + tarjeta) — D3, D5, D16, F4.
    Depende de: 7
11. [docs] `API_REFERENCE.md`, `API_CONTRACT.md`, `BUSINESS_RULES.md`, `STATE_AND_FETCHING.md`, `ARCHITECTURE.md` (backend y frontend), `COMPONENTS_GUIDE.md`.
    Depende de: 5
12. [verif] `/run-tests`, navegador (T8), `/code-review`, `/analyze-spec 38 cierre`.
    Depende de: 6, 8, 9, 10, 11
13. [docs] cierre (CHANGELOG, ROADMAP, TODO, AGENTS, VISION §2.5), `graphify update .`, PR en borrador.
    Depende de: 12
