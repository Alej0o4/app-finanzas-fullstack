# Spec — Fase 37: recurrentes y calendario de cargos anuales

> Tercera fase del enfoque "finanzas responsables" (`docs/VISION_FINANZAS_RESPONSABLES.md` §2.4).
> Era la Fase 35 original del plan (recurrentes), renumerada el 2026-10-17. **Aditiva**: una tabla
> nueva (`recurring_rules`), un servicio nuevo (`app/services/recurring.py`) y un router nuevo
> (`/api/v1/recurring`). **No modifica** `Transaction`, `ledger.py` ni ninguna cifra existente: una
> ocurrencia confirmada crea una transacción normal por el camino contable de siempre.

**Estado:** **implementada y cerrada el 2026-10-18; decisiones D1–D20 revisadas y confirmadas por el dueño el 2026-10-18** (único cambio: guarda de moneda en `PUT /accounts/{id}`, D7) (783 tests en Postgres 16; ver "Desvíos y hallazgos" y "Cierre"). **Sin `/grilling` previo**: las decisiones D1–D20 las tomó el agente contra el código y la visión (precedente: Fase 35); el dueño las revisó una por una después y las mantuvo — ver "Decisiones tomadas por el agente, pendientes de revisión del dueño". Marcadores `[NEEDS CLARIFICATION]` abiertos: ninguno (los puntos más de producto tienen un default conservador).

---

## Problem Statement

El arriendo, el salario, Netflix y el seguro anual se repiten, pero Oikos los trata como si cada mes
fueran nuevos: hay que teclearlos a mano (fricción de captura) y la app no sabe qué viene. Sin saber
qué se repite no se puede decir "llego a fin de mes", y las obligaciones que no se estaban
provisionando (un cargo anual que se olvidó) solo se descubren cuando ya golpearon el flujo.

## Solution

Una **regla recurrente** (nombre, tipo, monto, cuenta, categoría, frecuencia, fecha de inicio) que
**propone** una transacción cada vez que vence una ocurrencia; el dueño la **confirma** (un toque,
con el monto editable) o la **salta**. Nada se registra solo (principio de la visión: la app
propone, el usuario confirma). Sobre las reglas activas:

- **Pendientes**: las ocurrencias vencidas (hoy o antes) listas para confirmar o saltar. Se calculan
  **bajo demanda** a partir de la fecha de la próxima ocurrencia de cada regla: no dependen de que
  un job haya corrido, así que "los días en que el scheduler no corrió" dejan de ser un problema.
- **Calendario de 12 meses**: los próximos cargos e ingresos por mes y por moneda, con el costo
  **mensualizado** de cada obligación (un seguro anual de $1.200.000 pesa $100.000 al mes).
- **Detección de cargos anuales**: la app revisa el historial y sugiere crear una regla para un gasto
  que se repitió con ~12 meses de distancia y todavía no es recurrente.

## User Stories

1. Como dueño quiero registrar "Arriendo, $1.500.000, día 1 de cada mes, cuenta Bancolombia, categoría
   Vivienda" una sola vez, para no teclearlo cada mes.
2. Quiero ver un aviso "Tienes 2 recurrentes por confirmar" y confirmarlos con un toque, corrigiendo
   el monto si esta vez cambió (la factura de la luz).
3. Quiero saltar una ocurrencia (no pagué Netflix este mes) sin que el gasto se registre.
4. Quiero pausar una regla (me fui de la suscripción) y reanudarla sin que aparezcan meses atrasados.
5. Quiero ver los próximos 12 meses: cuánto sale cada mes, qué meses concentran cargos anuales y
   cuánto cuesta al mes todo lo que se repite.
6. Quiero que la app me avise "pagaste el seguro del carro en octubre del año pasado y este año; ¿lo
   agrego como recurrente anual?".
7. Quiero que un salario recurrente sea un ingreso y un arriendo un gasto, ambos en la moneda de su
   cuenta.

## Implementation Decisions

Convención de IDs: **D** decisión (tomada por el agente, sección siguiente), **B** backend, **F**
frontend, **T** testing, **X** docs.

### Decisiones tomadas por el agente, pendientes de revisión del dueño

**D1 — Propone, no registra solo.** Una regla nunca crea una transacción sin que el dueño la
confirme. Justificación: es el principio de fricción de la visión §2.4 ("la app propone, el usuario
confirma"), evita registrar un monto equivocado (servicios variables, salario con deducciones) y
elimina de raíz el riesgo de duplicar/contabilizar mal si algo falla. *Alternativa descartada:*
auto-registro con aviso; es más cómodo pero toca el saldo sin que el dueño mire. Reversible: un flag
`auto_confirm` por regla se puede agregar después sin romper nada.

**D2 — Sin job: ocurrencias pendientes perezosas.** Cada regla guarda `next_date` (la próxima
ocurrencia **no resuelta**). Una ocurrencia está **pendiente** si `next_date <= hoy` (en la zona del
usuario, `periods.dia_local`). Confirmar o saltar avanza `next_date`. No se agrega ningún job al
scheduler (el único sigue siendo el resumen semanal). Justificación: responde "qué hacer con los días
en que el scheduler no corrió" (nada se pierde: las pendientes se acumulan) y evita un segundo job
con idempotencia por usuario/zona. *Consecuencia aceptada:* no hay notificación push de pendientes
(queda en `docs/TODO.md`).

**D3 — Frecuencias: `weekly`, `monthly`, `yearly`.** Semanal = cada 7 días; mensual = mismo día del
mes; anual = mismo día y mes. La quincena colombiana (15 y 30) se modela con **dos reglas
mensuales**. Sin intervalos arbitrarios ("cada 3 meses") ni días hábiles: se agregan si hacen falta.

**D4 — Día 31 y 29 de febrero se recortan al último día del mes, desde el ancla.** La ocurrencia n
se calcula **siempre desde `start_date`** (no desde la ocurrencia anterior): una regla del 31 da
31 ene, 28 feb, 31 mar (no 28 mar). Anual del 29 de febrero da 28 feb en años no bisiestos. Función
pura `siguiente_ocurrencia(inicio, frecuencia, actual)`.

**D5 — El calendario es en días de calendario (`Date`), no instantes.** `start_date` y `next_date`
son columnas `Date` interpretadas en la zona del usuario. "Hoy" sale de `periods.dia_local(ahora,
tz)` con `ahora` inyectado. Al confirmar, el `date` de la transacción es
`periods.instante_de_dia(ocurrencia, ahora, tz)` (hoy conserva la hora real, otro día = 12:00
locales, igual que `POST /transactions` con solo-día). Cambiar la zona del usuario no mueve las
reglas (son días).

**D6 — El esquema de la regla no se edita; el resto sí.** *(Desviada al implementar: `PUT` con `frequency`/`start_date`/`type` da `422`, y `account_id` solo puede cambiar a una cuenta de la misma moneda; ver "Desvíos".)* `PUT` permite cambiar `name`, `amount`,
`account_id`, `category_id` y `status`. **No** cambia `frequency` ni `start_date` (si el arriendo pasa
del día 1 al 5, se borra y se crea otra). Justificación: editar el calendario obliga a decidir qué
pasa con lo ya confirmado/saltado; borrar y recrear lo hace explícito y simple. Cambiar `account_id`
cambia la moneda efectiva de las ocurrencias futuras (permitido; las ya confirmadas no se tocan).

**D7 — Cuenta, moneda y categoría.** *(Desviada al implementar: borrar una cuenta o categoría con reglas da `409`; `account_missing`/`category_missing` quedan solo como defensa; ver "Desvíos".)* La regla guarda `account_id` y `category_id`; **la moneda es la
de la cuenta** (nunca se guarda: una cuenta no cambia de moneda, y el router de transacciones ya
hereda `cuenta.currency`). La cuenta debe ser del usuario y estar activa; la categoría debe ser base o
del usuario (mismas reglas y mismo `404` que `POST /transactions`). **No** se valida que el tipo de la
categoría coincida con el de la regla (los reembolsos por categoría cruzada son intencionales desde la
Fase 31). Si la cuenta o la categoría se borran después, la regla **deja de listarse como pendiente
y como proyección** y el `confirm` responde `404` (`AccountNotFoundError`/`CategoryNotFoundError`); la
regla sigue visible en la lista con `account_missing`/`category_missing = true` para que el dueño la
edite o la borre.

**D8 — Confirmar crea una transacción normal.** `POST /recurring/{id}/confirm` con
`{"occurrence_date": "YYYY-MM-DD", "amount": "…"|null}` crea la `Transaction` (monto de la regla o el
`amount` enviado, ambos `> 0` con los límites del dinero), mueve `Account.balance` con
`ledger.registrar_impacto` y evalúa las alertas de presupuesto (`evaluate_budget_thresholds_safely`)
**en el mismo camino** que `crear_transaccion`. `description` = nombre de la regla; sin
`payment_method`; **sin `fund_id`** (D14). Después avanza `next_date`. Todo en una sola transacción SQL;
el router es dueño del `commit`.

**D9 — Solo se resuelve la ocurrencia más antigua, y la fecha se verifica.** `confirm` y `skip`
exigen que `occurrence_date == rule.next_date` (si no, `409`). Obliga a resolver en orden (no se
puede confirmar mayo dejando abril colgada) y hace que **dos confirmaciones concurrentes no dupliquen**:
ambas toman `SELECT … FOR UPDATE` sobre la regla; la segunda ya ve `next_date` avanzada y recibe `409`.
Una ocurrencia **futura** (`> hoy`) no se puede confirmar ni saltar: `409` ("todavía no vence").

**D10 — Atrasos acotados.** `GET /recurring/pending` devuelve las ocurrencias vencidas de cada regla,
**hasta 12 por regla** (de más antigua a más nueva). Si el dueño estuvo fuera mucho más, el resto
aparece al ir resolviendo (la lista se recalcula). `start_date` no puede ser anterior a **un año**
antes de hoy (`422`): crear una regla con inicio en el pasado lejano generaría decenas de pendientes
sin sentido; el dueño que quiera su historial lo tiene en las transacciones.

**D11 — Pausar y reanudar.** `status` ∈ {`active`, `paused`}. Una regla pausada no aparece en
pendientes ni en el calendario, pero sí en la lista y cuenta como "ya es recurrente" al descartar
sugerencias (D15).
Al **reanudar**, `next_date` salta a la primera ocurrencia `>= hoy` (no se acumulan los meses de la
pausa). Pausar no toca `next_date`.

**D12 — Borrar la regla.** `DELETE /recurring/{id}` borra la fila (borrado real, sin
`SoftDeleteMixin`: no hay historial que preservar). Las transacciones ya confirmadas **no** se tocan:
`Transaction` no guarda de qué regla vino (sin columna nueva en `Transaction`). Consecuencia: no hay
"ver las transacciones de esta regla"; el filtro por descripción de `/transactions` alcanza.

**D13 — Calendario de 12 meses.** `GET /recurring/calendar` devuelve, para las reglas activas con
cuenta válida, las ocurrencias proyectadas desde el **primer día del mes actual** (zona del usuario)
durante **12 meses calendario** (el actual + 11), agrupadas por mes y con totales por moneda
(`income`, `expense`, `net`). Cada ítem lleva `is_annual` (`frequency = yearly`) y `is_overdue`
(vencida y sin resolver). Las ocurrencias **vencidas sin resolver** se muestran en su mes real aunque
sean pasadas dentro del mes actual; las de meses anteriores al actual no entran (están en pendientes).
El cálculo es del backend (el frontend nunca proyecta). Tope duro de 400 iteraciones por regla.

**D14 — Costo mensualizado.** Cada regla expone `monthly_equivalent` (en la moneda de su cuenta):
`weekly` → `amount × 52 / 12`, `monthly` → `amount`, `yearly` → `amount / 12`, redondeado a 2
decimales con `ROUND_HALF_UP`. El calendario devuelve además `monthly_commitment` por moneda: la suma
de `monthly_equivalent` de las reglas **de gasto activas**. Es **informativo**: no alimenta
`free_to_spend` ni el flujo (esas cifras no cambian). Pagar una ocurrencia **con un sobre** queda
fuera de esta fase (el dueño puede editar la transacción y enlazarla con `PUT`, Fase 36); crear un
sobre sugerido desde el calendario también (ver "Out of Scope").

**D15 — Detección de cargos anuales.** `GET /recurring/suggestions` revisa los **gastos de los últimos
26 meses** y agrupa por `(cuenta, descripción normalizada, moneda)` (normalizada = `strip` + minúsculas
+ espacios colapsados; las transacciones **sin descripción** se ignoran). Un grupo es un **candidato
anual** si tiene ≥ 2 transacciones y alguna pareja consecutiva está separada por **350 a 380 días**,
y el monto de la última difiere ≤ **20 %** del de la anterior. Se descarta si ya existe una regla (de
cualquier estado) en la misma cuenta con el mismo nombre normalizado, o si la última ocurrencia fue
hace más de 13 meses (cargo que ya no se repite) o si su próxima fecha (`última + 1 año`) cae a más de
12 meses. Sugerencia: `{name, account_id, category_id (de la última), currency, amount (la última),
last_date, suggested_start_date (= última + 1 año, recortado D4), occurrences}`. Calcular en Python
sobre los datos del usuario (volumen personal) con **una** consulta. **Sin persistir descartes**: una
sugerencia ignorada vuelve a salir mientras sea válida (deuda en `docs/TODO.md`). Solo anuales: la
detección de suscripciones mensuales queda fuera.

**D16 — Alta desde una sugerencia.** Aceptar una sugerencia en el frontend abre el formulario de
regla **prellenado** (`frequency = yearly`); no hay endpoint de "aceptar": usa `POST /recurring`. Si
`suggested_start_date` ya pasó (cargo vencido sin que el dueño lo registrara), `start_date` se
acepta (D10: dentro del último año) y aparece como pendiente.

**D17 — Dinero y límites.** `amount` es `Decimal`, `> 0`, `decimal_places = 2`,
`max_digits = MAX_DIGITS_MONEY` (mismos que `TransactionBase`); `Numeric(14, 2)` en el modelo. `name`
1–100 caracteres (se guarda como `description` de la transacción al confirmar; el de
`TransactionBase` admite 500). Límite de **100 reglas por usuario** (`422`): defensa contra bucles
del cliente sin abrir trabajo de hardening.

**D18 — Contratos y errores.** `/api/v1/recurring`, auth por cookie o API key, mismo
`Depends(get_current_user)`. Errores solo con `DomainError`: regla de otro usuario o inexistente →
`404`; fecha que no corresponde (D9) o futura → `409`; esquema inválido/monto/`start_date` fuera de
rango/tope de reglas → `422`; confirmar con cuenta o categoría borradas → `404`. Contrato en
`backend/docs/API_REFERENCE.md` y `frontend/docs/API_CONTRACT.md`.

**D19 — Frontend.** Ruta nueva `app/(dashboard)/recurring/page.tsx` ("Recurrentes", entrada en el
`Sidebar`) con cuatro bloques en una página (sin sub-rutas): **Por confirmar** (lista con
Confirmar / Editar monto / Saltar), **Reglas** (tarjetas con pausar/reanudar/editar/borrar y el costo
mensualizado), **Calendario** (12 meses, mes por mes, cargos anuales resaltados) y **Sugerencias**.
Además, una tarjeta en el dashboard ("Tienes N recurrentes por confirmar" → `/recurring`) solo si N > 0.
Estado de servidor con TanStack Query (`useRecurring.ts`), formularios en `useState`, el backend manda
todas las cifras. Verificado a 390 px y desktop.

**D20 — Concurrencia y estructura.** La lógica vive en `app/services/recurring.py` (funciones puras
con `hoy`/`ahora` inyectados, sin `datetime(...)` naive, TDD) y los routers quedan delgados y dueños
del `commit`. Orden de locks en `confirm`: **regla → cuentas** (la regla se bloquea primero; el INSERT
de la transacción y `registrar_impacto` siguen el orden de `crear_transaccion`: no se toma ningún
sobre). `borrar` bloquea la regla antes de borrar para serializar contra un `confirm`.

### Modelo de datos (B1)

**B1. Migración Alembic** (`alembic-migration`), `down_revision = "e8a1c4d7b290"`: crea la tabla
`recurring_rules`:

| Columna | Tipo | Notas |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | FK `users.id`, NOT NULL | |
| `account_id` | FK `accounts.id`, NOT NULL, index | |
| `category_id` | FK `categories.id`, NOT NULL | |
| `name` | String(100), NOT NULL | |
| `type` | String(10), NOT NULL | CHECK `IN ('income','expense')` |
| `amount` | Numeric(14,2), NOT NULL | CHECK `> 0` |
| `frequency` | String(10), NOT NULL | CHECK `IN ('weekly','monthly','yearly')` |
| `start_date` | Date, NOT NULL | ancla del calendario (D4) |
| `next_date` | Date, NOT NULL | próxima ocurrencia no resuelta |
| `status` | String(10), NOT NULL, default `active` | CHECK `IN ('active','paused')` |
| `created_at`, `updated_at` | DateTime(tz) | mismo patrón que `Fund` |

Índice `ix_recurring_rules_user_id_status` sobre `(user_id, status)`. Sin `SoftDeleteMixin`. Una
migración hecha a mano a partir de `--autogenerate`; `downgrade` borra índice y tabla; `alembic check`
verde. `models.py`: clase `RecurringRule` con docstring y `relationship`s a `Account`/`Category`. Pasa de
15 a 16 modelos (actualizar la cifra en `AGENTS.md` y en la arquitectura del backend).

### Servicio (B2–B6) — `app/services/recurring.py`

**B2. Funciones puras** (sin DB, TDD, `hoy`/fechas inyectadas): `siguiente_ocurrencia(inicio,
frecuencia, actual)` (D3, D4), `primera_desde(inicio, frecuencia, desde)` (primera ocurrencia
`>= desde`, para reanudar, D11, y para fijar `next_date` inicial = `start_date`), `ocurrencias_en(inicio,
frecuencia, desde_next, hasta, tope)` (proyección, D13), `equivalente_mensual(monto, frecuencia)` (D14),
`es_candidato_anual(fechas, montos)` (D15) y `normalizar_nombre(texto)`.

**B3. Con DB** (dentro de la transacción del caller; **no** comitean): `listar`, `crear`, `actualizar`,
`eliminar`, `pendientes`, `confirmar`, `saltar`, `calendario`, `sugerencias`. `crear` valida cuenta y
categoría (D7), `start_date >= hoy − 1 año` (D10) y el tope de 100 reglas (D17) y fija `next_date =
start_date`. `confirmar` y `saltar` bloquean la regla (`FOR UPDATE`), validan D9 y avanzan `next_date`.
`confirmar` reutiliza `ledger.registrar_impacto`; **no** se refactoriza `crear_transaccion` (desvío
posible, ver Notas: se anota si el código obliga).

**B4. Errores solo con `DomainError`** (`NotFoundError`, `ConflictError`, `ValidationError`,
`AccountNotFoundError`, `CategoryNotFoundError`).

**B5. Zona horaria**: toda "hoy"/"mes" sale de `periods.dia_local` y aritmética de `date`; prohibido
resolver "actual" desde UTC o construir `datetime` naive en el servicio. Los instantes de las
transacciones salen de `periods.instante_de_dia`.

**B6. Hook de presupuestos**: tras el `commit` de `confirmar` (solo `expense`), se llama a
`evaluate_budget_thresholds_safely` como en `crear_transaccion` (un fallo del motor no revierte lo
confirmado, Decisión 13.3.4).

### API (B7–B9)

**B7. `schemas/recurring.py`** (re-exportado en `schemas/schemas.py`): `RecurringCreate`,
`RecurringUpdate`, `RecurringConfirm`, `RecurringSkip`, `RecurringResponse` (con `currency`,
`monthly_equivalent`, `is_annual`, `is_due`, `account_missing`, `category_missing`),
`PendingOccurrenceResponse`, `CalendarResponse` (`months[]`, `monthly_commitment[]`),
`SuggestionResponse`.

**B8. `api/recurring.py`** (router delgado, montado en `/api/v1/recurring`):

| Método y ruta | Qué hace |
|---|---|
| `GET /` | reglas del usuario (activas y pausadas) |
| `POST /` | crea (D7, D10, D17) |
| `PUT /{id}` | edita `name`/`amount`/`account_id`/`category_id`/`status` (D6, D11) |
| `DELETE /{id}` | borra (D12) |
| `GET /pending` | ocurrencias vencidas, ≤ 12 por regla (D10) |
| `POST /{id}/confirm` | crea la transacción y avanza (D8, D9) |
| `POST /{id}/skip` | avanza sin registrar (D9) |
| `GET /calendar` | 12 meses + `monthly_commitment` (D13, D14) |
| `GET /suggestions` | cargos anuales detectados (D15) |

Las rutas fijas (`/pending`, `/calendar`, `/suggestions`) se declaran **antes** de `/{id}`.

**B9. `main.py`** monta el router con `include_router(..., prefix="/api/v1/recurring", tags=["Recurrentes"])`.

### Frontend (F1–F5)

**F1.** Tipos regenerados (`pnpm gen:types` contra el backend de dev `:8001`), `lib/hooks/useRecurring.ts`
(`useRecurringRules`, `usePendingRecurring`, `useRecurringCalendar`, `useRecurringSuggestions`) y claves
en `lib/queryKeys.ts`.
**F2.** Página `/recurring`, entrada en `Sidebar` y bloque "Por confirmar" (confirmar con monto
editable, saltar) — D8, D9, D19.
**F3.** Reglas: `RecurringFormModal` (crear/editar; en edición `frequency` y `start_date` quedan de solo
lectura, D6), pausar/reanudar, borrar con confirmación accesible — D6, D11, D12.
**F4.** Calendario de 12 meses (mes por mes, totales por moneda, insignia "Anual", costo mensualizado)
y Sugerencias (abre el formulario prellenado, D16) — D13, D14, D15.
**F5.** Tarjeta del dashboard "N por confirmar" y **invalidaciones**: confirmar invalida
`recurring`, `transactions`, `accounts`, `dashboard`, `funds`/availability y `budgets` (como crear una
transacción); saltar/pausar/editar/borrar solo `recurring`. Documentado en `STATE_AND_FETCHING.md`.

## Testing Decisions

Backend en Postgres 16 (testcontainers, default de la Fase 32). T1 y T2 con TDD.

- **T1.** Funciones puras: `siguiente_ocurrencia` (mensual día 31 → fin de mes y vuelve a 31, año
  bisiesto, anual 29-feb, semanal cruzando año), `primera_desde`, `equivalente_mensual` (redondeo),
  `ocurrencias_en` (tope, ventana), `es_candidato_anual` (350/380 de borde, monto 20 %),
  `normalizar_nombre`.
- **T2.** CRUD: crear (cuenta/categoría ajenas `404`, monto `<= 0`/exceso `422`, `start_date` > 1 año
  atrás `422`, tope de 100), editar no cambia el calendario, borrar, aislamiento entre usuarios.
- **T3.** `pending`: solo vencidas (`<= hoy` en la zona del usuario, no UTC), tope 12, pausadas
  excluidas, cuenta borrada excluida.
- **T4.** `confirm`: crea transacción con moneda de la cuenta, mueve `Account.balance` igual que
  `POST /transactions`, `next_date` avanza, fecha `instante_de_dia`, monto editado, ingreso/gasto,
  fecha equivocada o futura `409`, dispara alertas de presupuesto.
- **T5.** `skip`: avanza sin transacción ni saldo; mismas validaciones de fecha.
- **T6.** `pause`/`resume`: reanudar salta los meses de la pausa (D11).
- **T7.** `calendar`: 12 meses exactos, ocurrencias por mes, totales por moneda, `monthly_commitment`,
  vencidas visibles, pausadas fuera; zona horaria de borde de mes.
- **T8.** `suggestions`: detecta el par a ~365 días, ignora sin descripción, descarta si ya hay regla,
  descarta si la última tiene > 13 meses, tolerancia de monto.
- **T9.** `concurrencia`: dos `confirm` simultáneos de la misma ocurrencia crean **una** transacción
  (la otra `409`); `confirm` vs `DELETE` de la regla no deja transacción a medias; saldo exacto.
- **T10.** Contrato: ninguna cifra existente cambia (dashboard summary, cashflow, presupuestos) por
  tener reglas; migración sube y baja (`alembic check` verde, `tests/test_migrations.py`).
- **T11.** UI en el navegador (Playwright) a 390 px y desktop: crear regla, confirmar con monto
  editado, saltar, pausar, calendario y sugerencia → formulario prellenado, tarjeta del dashboard.

## Out of Scope

- Auto-registro sin confirmar (D1), push/notificaciones de pendientes (D2), job nuevo en el scheduler.
- Frecuencias distintas de semanal/mensual/anual, intervalos, quincena nativa, días hábiles (D3).
- Editar `frequency`/`start_date` de una regla (D6); fecha de fin de la regla (se pausa o se borra).
- Pagar la ocurrencia con un sobre (`fund_id`) y **crear sobres sugeridos** desde el calendario o las
  sugerencias (la visión §2.4 lo prevé; queda como siguiente paso natural).
- Persistir sugerencias descartadas; detectar suscripciones mensuales o semanales.
- Vincular transacciones con su regla de origen (D12); pronóstico de caja 30/60/90 días (backlog: sale
  de esta fase pero es otra).
- Conversión de moneda; cambiar cualquier cifra del dashboard (`monthly_commitment` es informativo).

## Further Notes

- El `scheduler` sigue siendo uno solo (resumen semanal, lunes 07:00 Bogotá).
- `Account.balance` solo se toca en `confirm`, por `ledger.registrar_impacto`; las reglas y el
  calendario son proyecciones y no mueven dinero.
- Despliegue (pasos del dueño): `pg_dump` previo; la migración nueva corre sola en el `CMD` de Docker;
  reconstruir la imagen (solo código, sin dependencias nuevas).

---

## Desvíos y hallazgos (implementación backend)

- **Guarda de `start_date` futura (no estaba en la spec):** `start_date` a más de 10 años en el futuro es `422`.
  Sin tope, una fecha cerca de `9999-12-31` desbordaba `date` al calcular la siguiente ocurrencia.
- **`PUT` con `extra="forbid"`:** enviar `frequency`, `start_date` o `type` es `422` en vez de ignorarse en silencio (D6).
- **`confirm`/`skip` sobre una regla pausada → `409`** (la spec no lo decía; evita resolver ocurrencias de una regla pausada).
- **`RecurringResponse.currency` puede ser `null`** cuando la cuenta se borró (`account_missing`), porque la moneda no se guarda (D7).
- **`PendingOccurrenceResponse.is_next`** (extra): marca la única ocurrencia resoluble por regla (D9) para que el frontend habilite el botón.
- **`confirm` devuelve `TransactionResponse`**; `skip` devuelve la `RecurringResponse` ya avanzada.
- **`core/user_deletion.py`** ahora borra `RecurringRule` antes de cuentas y categorías (las FK no tienen cascada); no estaba en la spec y es necesario para `DELETE /users/me`.
- **`normalizar_nombre` de `services/recurring.py`** sigue D15 literal (strip + minúsculas + espacios colapsados, **conserva acentos**); es distinto de `core/text.normalizar_nombre` (que quita acentos).
- **`es_candidato_anual`:** "monto de la última difiere <= 20 %" se mide contra la transacción inmediatamente anterior del grupo, y el intervalo de 350-380 días puede ser cualquier pareja consecutiva.
- **Migración:** `a9c3d6e1f845` (down_revision `e8a1c4d7b290`); subida, `downgrade -1` y resubida verificadas contra Postgres 16 y `alembic check` limpio.
- **Calendario:** las ocurrencias vencidas de meses anteriores al actual se saltan con `primera_desde(inicio, frecuencia, primer_dia_del_mes)`, así el tope de 400 iteraciones no se consume en atrasos viejos.
- **Correcciones del code-review (backend):**
  1. `PUT` con `account_id` de **otra moneda** da `422` ("La cuenta debe tener la misma moneda que la cuenta actual de la regla."); la misma moneda sigue permitida. Cambia D6 (que dejaba mover la regla a cualquier cuenta).
  2. `is_due` exige también cuenta y categoría vivas (igual que `pending`).
  3. `is_overdue` del calendario es `fecha < hoy`: una ocurrencia de hoy no es "vencida" en el calendario (sí es pendiente).
  4. **Cambia D7:** `DELETE /accounts/{id}` y `DELETE /categories/{id}` dan `409` si el usuario tiene reglas recurrentes (activas o pausadas) que las usan, así una regla ya no queda huérfana por esa vía. `account_missing`/`category_missing` se mantienen como defensa (p. ej. borrados por otras vías). `crear`/`actualizar` toman `FOR UPDATE` de la cuenta, el mismo lock que el borrado de cuenta.
  5. `es_candidato_anual`: el 20 % se mide dentro de la **pareja consecutiva** de 350-380 días (la última que cumple ambas), y `last_date`/`amount`/cuenta/categoría de la sugerencia salen de esa pareja, no de las dos últimas del grupo (nueva `indice_ultima_pareja_anual`).
  6. `sumar_meses`, `ultimo_dia_mes` y `primer_dia_del_mes` viven en `core/periods.py` (con tests en `tests/test_periods.py`); `services/recurring.py` los importa.
  Quedan como deuda (no se hicieron): consulta de sugerencias, carrera del tope de 100 reglas, helper de invalidaciones del frontend. Observación: `PUT /accounts/{id}` que cambiaba la moneda de una cuenta con reglas no tenía guarda; se agregó el 2026-10-18 (`400`, como con sobres).
- **Hallazgo fuera de alcance:** el `TRUNCATE` del fixture `real_client` (tests de concurrencia) no nombra `funds`/`recurring_rules`; funciona por `CASCADE` desde `users`.

- **Desvíos del frontend:** los toasts de confirmar/saltar/borrar salen desde `useMutation`, no desde el `mutate(..., { onSuccess })` del componente (la fila se desmonta al refrescar y TanStack no corre esos callbacks); la clave de `PendingRow` incluye el monto para que "Editar monto" no mande un override obsoleto (code-review); los tipos de `types/generated/api.ts` se regeneraron con `pnpm gen:types` contra un backend de dev aislado y `types/api.ts` tiene los tipos a mano.
- **Fuera de la spec, resuelto:** `PUT /accounts/{id}` ahora responde `400` si se cambia la moneda de una cuenta con reglas recurrentes (2026-10-18).

## Cierre (2026-10-18) — `/analyze-spec 37 cierre`

| D | Estado | Dónde |
|---|---|---|
| D1, D2, D3, D4, D5, D8–D15, D17, D18, D20 | implementadas | `services/recurring.py`, `api/recurring.py`, `core/periods.py`, `models.py`, migración `a9c3d6e1f845` |
| D6, D7 | **desviadas** (registradas arriba) | `services/recurring.py`, `api/accounts.py`, `api/categories.py` |
| D16, D19 | implementadas | `components/recurring/*`, `app/(dashboard)/recurring/page.tsx`, `PendingRecurringCard` |

- Tests: T1 (`test_recurring_logic.py`, `test_periods.py`), T2–T8 y T10 (`test_recurring.py`, incl. `TestContratoSinCambios`), T9 (`test_recurring_concurrency.py`, `concurrencia`), T10 migración (`test_migrations.py`, `alembic check`). **T11** (navegador, 390 px y 1280 px) lo ejecutó el agente de frontend; las reglas con cuenta/categoría borrada y el `409` por ocurrencia resuelta en otra pestaña se revisaron solo por código.
- Docs: ambos contratos de API, `BUSINESS_RULES`, `STATE_AND_FETCHING`, `ARCHITECTURE` (backend y frontend), `COMPONENTS_GUIDE`, CHANGELOG, ROADMAP, TODO, AGENTS y VISION §2.4 actualizados.
- Veredicto: **listo para cerrar** (sin CRÍTICO/ALTO).

## Orden de ejecución

1. [backend] `models.py` (`RecurringRule`) + migración Alembic — D5, D7, D17, B1.
   Depende de: —
2. [backend] [P] `services/recurring.py` funciones puras con TDD (T1) — D3, D4, D11, D14, D15, B2.
   Depende de: —
3. [backend] `schemas/recurring.py` + re-export — B7.
   Depende de: 1
4. [backend] `services/recurring.py` con DB (CRUD, pendientes, confirmar, saltar, calendario,
   sugerencias) — D1, D2, D5–D15, D17, D18, D20, B3–B6.
   Depende de: 1, 2, 3
5. [backend] `api/recurring.py` + montaje en `main.py` — D18, B8, B9.
   Depende de: 4
6. [backend] tests T2–T10.
   Depende de: 5
7. [frontend] tipos, hooks, claves de query e invalidaciones — D19, F1, F5.
   Depende de: 5 (contrato)
8. [frontend] [P] página `/recurring`, "Por confirmar" y Sidebar — D8, D9, D19, F2.
   Depende de: 7
9. [frontend] [P] reglas: formulario, pausar/reanudar, borrar — D6, D11, D12, D19, F3.
   Depende de: 7
10. [frontend] [P] calendario, sugerencias y tarjeta del dashboard — D13, D14, D15, D16, D19, F4, F5.
    Depende de: 7
11. [docs] `API_REFERENCE.md`, `API_CONTRACT.md`, `BUSINESS_RULES.md`, `STATE_AND_FETCHING.md`,
    `ARCHITECTURE.md` de backend y frontend.
    Depende de: 5
12. [verif] `/run-tests`, navegador (T11), `/code-review`, `/analyze-spec 37 cierre`.
    Depende de: 6, 8, 9, 10, 11
13. [docs] cierre (CHANGELOG, ROADMAP, TODO con deuda consciente, AGENTS, VISION §2.4),
    `graphify update .`, PR en borrador.
    Depende de: 12
