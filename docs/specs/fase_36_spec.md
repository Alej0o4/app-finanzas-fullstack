# Spec — Fase 36: gasto contra sobre

> Segunda fase del enfoque "finanzas responsables" (`docs/VISION_FINANZAS_RESPONSABLES.md` §2.3).
> Sintetiza el `/grilling` que el dueño cerró el **2026-10-17** (Q1–Q17 → D1–D17). Aditiva sobre la
> Fase 35 (`Fund`/`FundEntry`, libro append-only, `services/funds.py`): **toca el núcleo contable**
> (`api/transactions.py`), pero no `ledger.py` ni la regla de saldo de cuentas.

**Estado:** **en implementación (2026-10-17); `/analyze-spec 36` previo sin CRÍTICO/ALTO.** Sin marcadores `[NEEDS CLARIFICATION]`: las 17
decisiones están resueltas. Cómo se leyeron las que llegaron ambiguas está en "Desvíos y hallazgos".

---

## Problem Statement

Con la Fase 35 el dinero apartado para el seguro o el computador vive en un sobre, pero **pagar** ese
gasto no mueve el sobre: el saldo del sobre solo baja con retiros manuales. Pagas el seguro, el flujo
del mes se hunde y el sobre sigue lleno — el disponible real queda doblemente descontado y el mes
parece un desastre cuando el gasto estaba previsto. Los sobres no se vuelven reales hasta que un gasto
se imputa contra ellos.

## Solution

Enlazar un **gasto** a un sobre al crearlo o editarlo (`fund_id`). El servidor aplica al sobre
`min(gasto, saldo)` con una entrada del libro enlazada a la transacción (`fund_entries.transaction_id`),
y el flujo la muestra como **planeado** sin cambiar ninguna cifra existente:

- El gasto **sigue siendo gasto real** (regla de la Fase 31 intacta): KPI, presupuestos, alertas y
  Analítica no cambian de valor. Solo se agrega el desglose `planned_expense`.
- Borrar o editar la transacción reajusta el sobre (devuelve o aplica la diferencia) en la misma
  transacción SQL.
- Nada de esto es una transferencia: el gasto sale de la misma cuenta que respalda el sobre.

## User Stories

1. Como dueño quiero marcar "Pagar con sobre: Seguro del carro" al registrar el pago del seguro, para
   que el sobre baje solo y no tenga que retirar a mano.
2. Quiero que, si el gasto supera lo apartado, el sobre quede en 0 y el resto cuente como gasto normal,
   y que la app me diga cuánto salió del sobre.
3. Quiero ver en el dashboard cuánto del gasto del mes fue **planeado**, para que un gasto previsto no
   haga ver el mes como un desastre — sin que cambie el total gastado.
4. Quiero que borrar o editar un gasto enlazado devuelva o reajuste lo apartado.
5. Quiero ver en el detalle de un sobre los gastos que se pagaron con él.
6. Quiero que el fondo de emergencia no cuente lo pagado con sobres como "gasto normal" al promediar.
7. Quiero que borrar un sobre con gastos enlazados me avise qué se pierde, y que los gastos queden
   intactos.

## Implementation Decisions

Convención de IDs: **D** decisión del grilling (dueño, 2026-10-17), **B** backend, **F** frontend,
**T** testing, **X** docs.

### Decisiones resueltas con el usuario (2026-10-17)

**D1 (Q1) — Cómo cuenta en el flujo.** Un gasto enlazado cuenta como gasto **real** (regla de la
Fase 31 intacta) y se muestra aparte como "planeado". KPI, presupuestos y Analítica **no cambian de
cifra**; solo se agrega el desglose.

**D2 (Q2) — Misma cuenta.** El gasto debe salir de la cuenta que respalda el sobre
(`transaction.account_id == fund.account_id`); si no, `422`. Sin transferencias entre cuentas
(QA-030 sigue abierto en `docs/TODO.md`).

**D3 (Q3) — Gasto mayor al saldo.** Se permite. Se aplica `min(gasto, saldo)`, el sobre queda en 0 y
el excedente cae como gasto normal. La entrada del libro es por el monto aplicado; la respuesta
informa lo aplicado (`fund_applied_amount`). Con saldo 0 no se aplica nada: no se crea entrada (el
libro prohíbe `amount = 0`) y la transacción queda **sin enlace** (`fund_id = null`,
`fund_applied_amount = 0`).

**D4 (Q4) — Borrar la transacción.** Devuelve el monto aplicado al sobre con una entrada `adjustment`
positiva (el libro es append-only: no se borra la original). Si el sobre ya no existe, se ignora el
enlace sin error.

**D5 (Q5) — Editar la transacción enlazada.**
- Cambiar el monto reajusta con un `adjustment` por la diferencia (con el tope de D3).
- Cambiar de cuenta o pasar a ingreso → `409`, salvo que el mismo `PUT` mande `fund_id: null`
  (desvincular primero).
- `fund_id: null` desvincula y devuelve lo aplicado.
- Cambiar a otro sobre: devolver al viejo y aplicar al nuevo **en la misma transacción SQL**.
- `fund_id` ausente en el `PUT` conserva el enlace (semántica `model_fields_set`, como QA-026).

**D6 (Q6) — Cómo se enlaza.** Campo `fund_id` en `TransactionCreate` y en el schema del `PUT`; también
enlaza una transacción existente (`PUT` con `fund_id` a una sin enlace). Sin endpoint aparte.

**D7 (Q7) — Solo gastos.** Solo `expense` se enlaza. Ingreso con `fund_id` → `422`. (Ingresos contra
sobre quedan fuera de alcance.)

**D8 (Q8) — Presupuestos.** Los presupuestos y sus alertas cuentan **todo** el gasto, incluido lo
pagado con sobre, sin excepciones. Anotar en `docs/TODO.md` como deuda consciente: "no alertar por lo
planeado". Anotar en `BUSINESS_RULES.md`.

**D9 (Q9) — Qué es "planeado".** Planeado = **monto total de la transacción** enlazada (no solo lo
aplicado al sobre). Se expone como `planned_expense`, por moneda, en `GET /dashboard/summary` (del
mes) y en `GET /dashboard/cashflow-series` junto a `total_expense`. UI: insignia en la lista de
transacciones y lista "Gastos de este sobre" en el detalle del sobre. **No** hay desglose por
categoría ni presupuestos. **Sin columna nueva** en `Transaction`.

**D10 (Q10) — Sobre gastado.** Tras gastarse, el sobre no cambia de fecha solo: queda `active` con
saldo 0 y la UI muestra "pagado" (no "atrasado"); la renovación anual automática es de la Fase 37.

**D11 (Q11) — Fondo de emergencia.** Lo pagado con sobre se **excluye** del `promedio_gasto_mensual`
(meta y runway): se excluye la transacción completa, consistente con D9.

**D12 (Q12) — Borrar un sobre con gastos enlazados: se PERMITE.** Se borran sus entradas; las
transacciones quedan intactas; `Account.balance` y totales no cambian; solo se pierde el desglose
"planeado" de esos gastos. `GET /funds/{id}` devuelve `linked_expenses_count` y
`linked_expenses_total`, y el diálogo dice: "Este sobre tiene N gasto(s) enlazado(s) (X). Si lo
borras, quedan como gasto normal, sin marca de planeado. Si solo quieres cerrarlo, archívalo."
Archivar conserva el historial.

**D13 (Q13) — Representación en el libro.** El gasto enlazado es una entrada `withdrawal` (negativa)
con `transaction_id`, por el monto aplicado; los reajustes y devoluciones son `adjustment` con el
**mismo** `transaction_id`. Monto aplicado a una transacción = `-SUM(fund_entries.amount WHERE
transaction_id = tx.id)`. El retiro manual sigue siendo `withdrawal` con `transaction_id = NULL`.
Único cambio de esquema: **índice no único** sobre `fund_entries.transaction_id`; que una transacción
pertenezca a lo sumo a un sobre lo garantiza el servicio con el row-lock (D17), no la BD. Verificado:
el CHECK de signo (`ck_fund_entries_sign`) solo restringe `contribution` y `withdrawal`, así que
`adjustment` de cualquier signo ya lo acepta; no hace falta tocarlo.

**D14 (Q14) — Frontend.** Selector "Pagar con sobre" en los formularios de crear y editar, visible
solo si el tipo es gasto y la cuenta elegida tiene sobres activos; al cambiar a ingreso o de cuenta se
limpia. Muestra el saldo del sobre pero **no calcula** lo que se aplicará (el servidor es la fuente de
verdad). Tras guardar, un aviso muestra lo que devolvió el servidor ("$X salieron del sobre; $Y
salieron del disponible libre"). Al editar permite cambiar o quitar el sobre.

**D15 (Q15) — Contrato.** `TransactionCreate` y el schema del `PUT` aceptan `fund_id`;
`TransactionResponse` agrega `fund_id` (nullable) y `fund_applied_amount` (nullable) en crear, editar
y listar; el listado los calcula en **una sola consulta**. Las API keys `oikos_pat_...` aceptan
`fund_id` igual. Errores: sobre ajeno o inexistente `404`; archivado `409`; cuenta distinta o
ingreso `422`. Se actualizan `backend/docs/API_REFERENCE.md` y `frontend/docs/API_CONTRACT.md` en el
mismo cambio.

**D16 (Q16) — Sobre archivado.** Un sobre archivado **no** recibe devoluciones ni ajustes. Borrar o
editar una transacción enlazada a uno archivado procede normalmente (el dinero vuelve al disponible
libre vía la cuenta), pero con una limitación documentada: el `planned_expense` histórico de ese mes
puede cambiar (al editar/borrar la transacción cambia su monto total, o desaparece del desglose).
Cambiar o quitar el enlace de una transacción ligada a un sobre archivado → `409` (desarchívalo
primero).

**D17 (Q17) — Locks y estructura.** Orden de locks: **transacción → sobre → cuentas** (cuentas por id
ascendente). En crear, el sobre se bloquea antes del `INSERT` y de `ledger.registrar_impacto`; en
editar/borrar la fila de la transacción ya está bloqueada. La lógica nueva (aplicar, ajustar,
devolver) vive en `app/services/funds.py`, llamada desde `transactions.py`; los routers siguen
delgados y dueños del `commit`. Tests `concurrencia`: (a) gastos concurrentes contra un sobre no lo
dejan negativo; (b) gasto + retiro manual tampoco; (c) borrar el sobre mientras se crea un gasto
enlazado no deja entradas huérfanas; (d) dos `DELETE` simultáneos de la misma transacción enlazada
devuelven al sobre una sola vez.

### Modelo de datos (B1)

**B1. Migración Alembic** (`alembic-migration`), `down_revision = "d5f2a8c1e703"`: crea
`ix_fund_entries_transaction_id` sobre `fund_entries(transaction_id)`; `downgrade` lo borra. Sin
cambios de columnas ni de CHECK. `alembic check` verde. `models.py`: `Index(...)` en `__table_args__`
de `FundEntry`; se actualiza el docstring (ya no "siempre NULL").

### Servicio (B2–B5) — `app/services/funds.py`

**B2. Funciones puras** (sin DB, TDD): `monto_a_aplicar(gasto, saldo)` = `min(gasto, max(saldo, 0))`
(D3) y `delta_reajuste(aplicado_actual, gasto_nuevo, saldo)` → monto a mover (+ aplica más, − devuelve)
con el tope de D3.

**B3. Con DB** (todas dentro de la transacción del caller; **no** comitean):
- `aplicar_gasto(db, user, fund_id, tx, ahora) -> Decimal`: toma `FOR UPDATE` del sobre (404 si no
  existe/ajeno), valida `status = active` (409), `tx.type = expense` (422), `tx.account_id ==
  fund.account_id` (422); calcula `min(gasto, saldo)` y, si es > 0, agrega `withdrawal` con
  `transaction_id`. Devuelve lo aplicado.
- `monto_aplicado(db, tx_id) -> Decimal` y `vinculos(db, tx_ids) -> {tx_id: (fund_id, aplicado)}`:
  una sola consulta agrupada por `transaction_id` con `HAVING SUM(amount) < 0`; el `fund_id` sale de
  `fund_entries.fund_id`. Un enlace es una suma neta negativa (un desvincular deja suma 0).
- `reajustar_gasto(db, user, tx, nuevo_monto, ahora)`: bloquea el sobre del enlace actual, calcula el
  delta (D5) y agrega `adjustment` (con signo) con el mismo `transaction_id`. Sobre archivado ⇒ no
  hace nada (D16).
- `devolver_gasto(db, user, tx, ahora) -> Decimal`: `adjustment` positivo por el monto aplicado
  (D4). Sobre inexistente o archivado ⇒ no hace nada, sin error (D4, D16).
- `cambiar_enlace(db, user, tx, nuevo_fund_id, ahora)`: devolver al viejo + aplicar al nuevo (D5).

**B4. `promedio_gasto_mensual`** excluye las transacciones enlazadas (D11): `Transaction.id NOT IN
(subconsulta de transacciones con suma neta negativa en fund_entries)`.

**B5. Errores solo con `DomainError`** (`NotFoundError`, `ConflictError`, `ValidationError`).

### API (B6–B10)

**B6. `schemas/transactions.py`:** `TransactionBase` **no** cambia (su `model_dump` construye el
`models.Transaction`). `TransactionCreate` suma `fund_id: int | None = None`; nuevo
`TransactionUpdate(TransactionBase)` con `fund_id: int | None = None` lo usa el `PUT` (hoy usa
`TransactionBase`). `TransactionResponse` suma `fund_id: int | None = None` y `fund_applied_amount:
Decimal | None = None`. El router saca `fund_id` del `model_dump` antes de armar el modelo.

**B7. `crear_transaccion`:** con `fund_id`, **antes** del `INSERT` toma el lock del sobre y valida (D2,
D7, D15); tras `db.add`+`flush` del id, `aplicar_gasto`; `registrar_impacto` y la `IdempotencyKey`
siguen en el mismo commit. La respuesta carga `fund_id`/`fund_applied_amount`. El replay idempotente
devuelve los mismos campos (calculados desde el libro).

**B8. `actualizar_transaccion`:** tras el lock de la transacción, resuelve el enlace actual con
`vinculos`; aplica D5/D16 (409 por cuenta/tipo, desvincular, cambiar de sobre, enlazar una existente,
reajustar monto) en el mismo `try` y commit que `ledger.aplicar_edicion`. Los hooks de presupuesto
no cambian (D8).

**B9. `eliminar_transaccion`:** después del `UPDATE` condicional exitoso (rowcount = 1) y del
`ledger.revertir_impacto`, `devolver_gasto`. Así dos `DELETE` simultáneos devuelven una sola vez (D17-d).

**B10. `obtener_transacciones`:** una consulta extra `vinculos(db, [ids de la página])` y se adjuntan
`fund_id`/`fund_applied_amount` a cada ítem (sin N+1).

### Dashboard y sobres (B11–B12)

**B11. `planned_expense`** (D9): `GET /dashboard/summary` suma `planned_expense:
list[BalanceByCurrency]` (preferida primero; mismo universo y rango de mes que
`monthly_expense_by_currency`; Σ monto total de las transacciones `expense` no borradas con enlace
neto). `GET /dashboard/cashflow-series` suma `planned_expense: Decimal` (mismos filtros que
`total_expense`). Ningún campo existente cambia de valor ni de nombre.

**B12. `FundResponse`** suma `linked_expenses_count: int` y `linked_expenses_total: Decimal` (Σ monto
total de las transacciones enlazadas vivas; D12, calculado en `_construir` con una consulta
agrupada). `FundDetailResponse` suma `linked_expenses: list[LinkedExpense]` (las 50 más recientes:
`transaction_id`, `amount`, `applied_amount`, `date`, `description`, `category_name`).
`FundEntryResponse` suma `transaction_id: int | None`. `eliminar` (A1) **no cambia**: ya borra todas
las entradas del sobre, enlazadas o no (D12).

### Frontend (F1–F5)

**F1.** `types/api.ts` (y `types/generated/api.ts` con `pnpm gen:types` contra dev): `fund_id`,
`fund_applied_amount` en `Transaction`; `planned_expense` en `DashboardSummary` y `CashflowSeries`;
`linked_expenses_*` y `LinkedExpense` en `Fund`/`FundDetail`.
**F2.** Selector "Pagar con sobre" (D14) en `TransactionModal`, `QuickTransactionModal` y
`EditTransactionModal` (los formularios que crean/editan gastos con cuenta elegible). Usa
`useFunds()`; visible solo con tipo gasto y sobres activos en la cuenta. `TransactionCaptureForm`
(captura de pantalla completa) queda fuera: no tiene selector de cuenta propio (ver Desvíos).
**F3.** Aviso tras guardar con lo aplicado (toast/mensaje del flujo existente).
**F4.** `TransactionList`/`RecentTransactionsSection`: insignia "Planeado" cuando `fund_id != null`.
Detalle `/funds/[id]`: sección "Gastos de este sobre". Tarjeta/estado: sobre con saldo 0 y gastos
enlazados muestra "pagado" (D10). Dashboard: línea "de los cuales planeado" bajo el gasto del mes
(`planned_expense`), sin cambiar el total; Analítica: ídem en el KPI de gasto.
**F5.** `DeleteFundButton`: el `ConfirmDialog` incluye el texto de D12 cuando
`linked_expenses_count > 0`. Invalidaciones: crear/editar/borrar transacción invalida además `funds`
y `dashboardSummary` (ya invalida este último) — actualizar `frontend/docs/STATE_AND_FETCHING.md`.

## Testing Decisions

Seam: el más alto y ya existente — pytest a nivel de API (`TestClient`) en `test_funds.py` /
`test_transactions.py` (y un archivo nuevo `test_funds_gasto.py` si crece), más tests de lógica pura
para las funciones nuevas y los `concurrencia`.

- **T1. Puras** (TDD): `monto_a_aplicar` (gasto < saldo, = saldo, > saldo, saldo 0), `delta_reajuste`
  (sube, baja, sin cambio, tope).
- **T2. Crear:** con/sin exceso (D3: aplicado, saldo 0, excedente), saldo 0 ⇒ sin enlace; cuenta
  distinta ⇒ 422 (D2); ingreso con `fund_id` ⇒ 422 (D7); sobre ajeno/inexistente ⇒ 404; archivado ⇒
  409; `Account.balance` baja por el total; `committed` baja por lo aplicado; idempotency replay
  devuelve los campos; API key acepta `fund_id`.
- **T3. Editar:** subir/bajar monto (adjustment), cambiar de sobre, `fund_id: null`, enlazar una
  existente, `fund_id` ausente conserva, cambio de cuenta/tipo ⇒ 409 y con `fund_id: null` ⇒ ok,
  sobre archivado (D16).
- **T4. Borrar:** devuelve lo aplicado (D4); sobre ya borrado ⇒ sin error; sobre archivado no recibe.
- **T5. Listado:** `fund_id`/`fund_applied_amount` correctos y **una sola consulta** extra.
- **T6. Dashboard:** `planned_expense` en summary (mes, moneda, universo de cuentas) y
  cashflow-series; totales existentes **idénticos** con y sin enlace (D1); presupuestos cuentan el
  gasto enlazado (D8).
- **T7. Emergencia:** el promedio excluye lo enlazado (D11).
- **T8. Borrar sobre con gastos** (D12): permitido; transacciones intactas; `linked_expenses_*` antes
  de borrar; `Account.balance` igual.
- **T9. `@pytest.mark.concurrencia`** (a)–(d) de D17.
- **T10. Migración:** `alembic check` (en `test_migrations.py`) + upgrade/downgrade manual.
- **T11. Frontend:** `pnpm lint`/`prettier`; verificación manual en navegador contra el stack dev
  aislado (`-p oikos-dev`): gasto enlazado con y sin exceso, editar, borrar, borrar el sobre con
  gastos; 390 px y claro/oscuro.

## Out of Scope

Transferencias entre cuentas (QA-030); renovación anual automática del sobre (Fase 37); no alertar por
lo planeado en presupuestos (deuda D8); ingresos contra sobre; enlace por nombre de sobre; selector en
la pantalla de captura; desglose por categoría de lo planeado; seguridad/auth.

## Further Notes

- Despliegue: `pg_dump` previo; la migración (solo un índice) corre sola en el `CMD` de Docker.
- Limitación documentada (D16): `planned_expense` histórico de un mes puede cambiar al editar/borrar
  una transacción enlazada.

## Desvíos y hallazgos

*(se llena durante la implementación y el cierre)*

- **Lectura de decisiones ambiguas (el brief llegó con texto corrupto):** D2 se leyó como "el gasto
  debe salir de la cuenta del sobre; si no, 422"; D9 como "planeado = monto total de la transacción"
  (no solo lo aplicado); D12 como "borrar el sobre se PERMITE"; D13 como "índice no único + unicidad
  por servicio"; D15 nombra el campo `fund_applied_amount`; D16 como "el planeado histórico puede
  cambiar". En todos se eligió la lectura más conservadora y coherente con el resto.
- **D3 con saldo 0:** no se crea entrada (CHECK `amount <> 0`) y la transacción queda sin enlace.
- **D16 ampliada:** cambiar o quitar el enlace de una transacción ligada a un sobre archivado ⇒ `409`
  (no se puede devolver a un archivado).
- **B12:** `linked_expenses_count/total` también van en `FundResponse` (no solo en el detalle) para que
  el diálogo de borrar desde la tarjeta tenga el dato sin otra llamada.
- **F2 (revisado en la implementación):** `TransactionCaptureForm` **sí** tiene selector de cuenta propio
  y `QuickTransactionModal` (el FAB) solo lo envuelve, así que ese es el camino principal de captura. Se
  le agregó el selector "Pagar con sobre" (`PayWithFundSelect`, compartido con `TransactionModal` y
  `EditTransactionModal`); queda dentro del alcance, sin cambio de contrato.
- **Editar y cambiar de cuenta:** el selector se limpia y el modal manda `fund_id: null`, así que un
  gasto enlazado que cambia de cuenta queda desvinculado a la vista del usuario, en lugar de recibir el
  `409` (que solo ocurre si un cliente API cambia de cuenta sin mandar `fund_id: null`).
- **`types/generated/api.ts`** se regenera con `pnpm gen:types` contra el stack dev (paso de verificación).

## Orden de ejecución

1. [backend] `models.py` (índice) + migración Alembic — D13, B1.
   Depende de: —
2. [backend] [P] `services/funds.py` funciones puras con TDD — D3, D5, B2.
   Depende de: —
3. [backend] `schemas/transactions.py` + `schemas/funds.py` (campos nuevos) — D6, D15, B6, B12.
   Depende de: 1
4. [backend] `services/funds.py` con DB (`aplicar_gasto`, `vinculos`, `reajustar_gasto`,
   `devolver_gasto`, `cambiar_enlace`) + exclusión en `promedio_gasto_mensual` — D2, D3, D4, D5, D7,
   D11, D13, D16, D17, B3, B4, B5.
   Depende de: 1, 2, 3
5. [backend] integración en `api/transactions.py` (crear/editar/borrar/listar) — D2, D4, D5, D6, D15,
   D17, B7–B10.
   Depende de: 4
6. [backend] `planned_expense` en dashboard + `linked_expenses_*` en sobres — D1, D8, D9, D12, B11,
   B12.
   Depende de: 4
7. [backend] tests T1–T10 (los de lógica pura van con el paso 2).
   Depende de: 5, 6
8. [frontend] tipos, hooks e invalidaciones — F1, F5 (invalidaciones).
   Depende de: 5, 6  (contrato)
9. [frontend] [P] selector y aviso en los modales de transacción — D14, F2, F3.
   Depende de: 8
10. [frontend] [P] insignia, desglose, "pagado", dashboard/Analítica y diálogo de borrar sobre —
    D9, D10, D12, F4, F5.
    Depende de: 8
11. [docs] `API_REFERENCE.md`, `API_CONTRACT.md`, `BUSINESS_RULES.md`, `STATE_AND_FETCHING.md`,
    `ARCHITECTURE.md` de backend — D8, D15, D16.
    Depende de: 5, 6
12. [verif] `/run-tests`, navegador (T11), `/code-review`, `/analyze-spec 36 cierre`.
    Depende de: 7, 9, 10, 11
13. [docs] cierre (CHANGELOG, ROADMAP, TODO con D8 y D16, AGENTS, VISION §2.3), `graphify update .`,
    PR en borrador.
    Depende de: 12
