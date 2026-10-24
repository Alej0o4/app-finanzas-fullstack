# Spec — Fase 39: Transferencias entre cuentas (QA-030) + vínculo CDT↔cuenta + corrección de saldo inicial

> Cierra **QA-030** y la deuda "Redención con retorno a una cuenta" de la Fase 38. Aditiva en el
> modelo (tabla `transfers`, categoría base "Rendimientos" en el catálogo) pero **toca `ledger.py`,
> `reconciliar_cuenta` y el módulo CDT**: es la primera fase desde la 36 que cambia cifras
> existentes (los saldos de cuentas con CDT) y por eso lleva migración de datos con respaldo.

**Estado:** especificada el 2026-10-24. Decisiones D1–D17 tomadas por el dueño en un `/grilling`
(Q1–Q17 de la sesión; el ID de cada decisión conserva el número de la pregunta). Marcadores
`[NEEDS CLARIFICATION]` abiertos: ninguno.

**Renumeración:** esta fase toma el número **39**. "Págate primero" pasa a la **40** y "cierre de
mes con puntaje" a la **41** (actualizar `AGENTS.md`, `docs/ROADMAP.md` y
`docs/VISION_FINANZAS_RESPONSABLES.md` al cerrar la fase; las menciones anteriores son históricas).

---

## Problem Statement

El saldo de Bancolombia en la app (8.994.000 COP) no refleja la realidad del banco (2.614.000 COP,
bolsillo incluido). Hay dos causas: la cuenta se creó con saldo inicial 0 aunque ya tenía dinero
(≈ 25.620.000 COP sin registrar), y 32.000.000 COP salieron de la cuenta hacia dos CDT sin que la
app lo sepa (el CDT está aislado a propósito desde la Fase 38). Resultado: el patrimonio cuenta esos
32 millones dos veces.

Además, mover dinero propio entre cuentas solo se puede registrar como gasto + ingreso. La compra de
200 USD (642.000 COP, 2026-10-05, de Bancolombia a Plenti) infla el gasto de octubre en COP y el
ingreso en USD, y lo mismo ocurre con la dona, Analítica y las alertas de presupuesto.

## Solution

Una **transferencia** es un movimiento entre dos cuentas propias (o entre una cuenta y un CDT) que
mueve los saldos y **no es flujo**: no entra a los KPI, la dona, Analítica, presupuestos ni alertas.
Se guarda en su propia tabla, soporta cambio de moneda (monto de salida y de entrada, con tasa
derivada) y aparece en la lista de movimientos con un estilo neutro. El CDT se conecta de forma
opcional con la cuenta de la que salió el dinero y a la que vuelve al redimir; el interés realizado
al redimir sí es ingreso. Un script único, con respaldo previo, deja los datos reales en la
verdad: saldo inicial de Bancolombia corregido y los dos CDT con su transferencia de origen.

## User Stories

1. Como dueño, quiero transferir dinero entre mis cuentas, para que mover plata propia no cuente como gasto ni ingreso.
2. Como dueño, quiero transferir de una cuenta en COP a una en USD indicando cuánto salió y cuánto entró, para registrar la compra de dólares tal como pasó.
3. Como dueño, quiero dar la tasa de cambio en vez del monto de entrada, para no calcularlo a mano.
4. Como dueño, quiero ver la tasa implícita ("1 USD = 3.210 COP") en cada transferencia entre monedas, para verificar que la cargué bien.
5. Como dueño, quiero que una transferencia entre cuentas de la misma moneda exija montos iguales, para no perder ni crear plata por error.
6. Como dueño, quiero que las transferencias no aparezcan en los KPI de ingreso/gasto del dashboard, para que mi flujo mensual diga la verdad.
7. Como dueño, quiero que las transferencias no cuenten en la dona, Analítica, presupuestos ni alertas, para que esas vistas reflejen solo gasto real.
8. Como dueño, quiero ver las transferencias en la lista de `/transactions` mezcladas por fecha con un estilo neutro, para poder conciliar el saldo de una cuenta contra el banco.
9. Como dueño, quiero filtrar la lista para ocultar las transferencias, para ver solo gastos e ingresos.
10. Como dueño, quiero un botón "Transferir" separado de "Nueva transacción", para no confundirlos.
11. Como dueño, quiero editar una transferencia, para corregir un monto, una fecha o una cuenta mal elegida.
12. Como dueño, quiero borrar una transferencia, para deshacer una que cargué por error.
13. Como dueño, quiero pagar mi tarjeta de crédito desde Bancolombia como una transferencia, para que el pago no cuente como gasto.
14. Como dueño, quiero que usar la tarjeta siga contando como gasto cuando compro, para no ocultar mi consumo.
15. Como dueño, quiero poder transferir aunque la cuenta de origen tenga sobres, para no depender de que el sistema me bloquee.
16. Como dueño, quiero un aviso en el formulario si la transferencia deja la cuenta por debajo de lo comprometido en sobres, para saber que mi disponible real quedará negativo.
17. Como dueño, quiero elegir la cuenta de origen al crear un CDT, para que el capital salga del saldo de esa cuenta.
18. Como dueño, quiero poder crear un CDT sin cuenta de origen, para registrar uno cuyo dinero nunca estuvo en la app.
19. Como dueño, quiero elegir la cuenta destino al redimir un CDT, para que el capital vuelva a esa cuenta.
20. Como dueño, quiero que el interés realizado al redimir entre como ingreso en una categoría "Rendimientos", para que mi flujo del mes incluya lo que gané.
21. Como dueño, quiero que redimir sin elegir cuenta siga funcionando como hoy, para no romper el caso aislado.
22. Como dueño, quiero que editar el capital o la apertura de un CDT vinculado actualice su transferencia, para que cuenta y CDT no se contradigan.
23. Como dueño, quiero que borrar un CDT vigente con vínculo devuelva el dinero a la cuenta, para deshacer un CDT creado por error.
24. Como dueño, quiero que un CDT redimido con transferencias no se pueda borrar, para no alterar el historial real de la cuenta.
25. Como dueño, quiero poder borrar un CDT redimido sin vínculo, como hasta ahora.
26. Como dueño, quiero que el patrimonio deje de contar dos veces el dinero de los CDT, para ver mi patrimonio real.
27. Como dueño, quiero que el disponible real siga siendo cuentas − comprometido, para que no cambie su significado.
28. Como dueño, quiero que Bancolombia muestre 2.614.000 COP al terminar la migración, para que la app coincida con el banco.
29. Como dueño, quiero que el saldo inicial de Bancolombia se corrija una sola vez con un script con respaldo previo, para no abrir la edición libre de saldos iniciales.
30. Como dueño, quiero que la reconciliación de saldo de una cuenta incluya las transferencias, para que `balance` siga siendo `opening_balance + neto` también con ellas.
31. Como dueño, quiero que borrar una cuenta con transferencias se rechace, para no alterar el saldo de la otra cuenta involucrada.
32. Como dueño, quiero que las fechas de transferencia sigan las reglas de zona horaria de las transacciones, para que el mes de una transferencia sea coherente con el resto.

## Implementation Decisions

Convención de IDs: **D** decisión (número de pregunta del `/grilling`), **B** backend, **F** frontend,
**T** testing, **X** docs.

### Modelo y reglas

**D1 — Tabla `transfers`, sin filas en `Transaction`.** Campos: `user_id`, `from_account_id` y
`to_account_id` (nulables), `cdt_id` (nulable), `amount_out`, `currency_out`, `amount_in`,
`currency_in` (`Numeric(14,2)`, `Decimal` siempre), `date`, `description`, `updated_at`. Los KPI,
la dona, Analítica, presupuestos, alertas, el resumen semanal y el fondo de emergencia no leen la
tabla, así que no cambian. `ledger.py` gana el cálculo del delta de saldo por transferencia y
`reconciliar_cuenta` pasa a ser `opening_balance + neto de transacciones + neto de transferencias`.

**D2/D9 — Cambio de moneda y tasa derivada.** Se persisten solo `amount_out` y `amount_in`; la
tasa no se guarda. La API acepta `amount_out` y **exactamente uno** de `amount_in` o
`exchange_rate` (si no, `422`). `exchange_rate` se expresa siempre como **COP por 1 unidad de la
moneda extranjera**, sea cual sea el sentido de la transferencia, y el backend calcula el monto
faltante con `Decimal` (redondeo `ROUND_HALF_UP` a centavo); el frontend nunca recalcula cifras
financieras. Misma moneda: se fuerza `amount_in == amount_out` y se rechaza `exchange_rate`. Pares
sin COP (p. ej. USD→EUR): se exige `amount_in` y se rechaza `exchange_rate` (`422`). La respuesta
expone la tasa implícita (`COP por unidad extranjera`) como dato derivado. Sin ganancia/pérdida
cambiaria.

**D3/D10 — El destino "CDT" se modela en la misma tabla.** `cdt_id` nulable y las dos cuentas
nulables, con un `CHECK` que obliga: sin `cdt_id` → ambas cuentas presentes y distintas; con
`cdt_id` → exactamente una cuenta presente (origen = constitución, destino = redención). Un CDT
tiene a lo sumo una transferencia de constitución y una de redención. Un único libro de movimientos
internos y un solo lugar donde reconciliar.

**D5 — Cuentas de crédito.** Se permiten como origen o destino sin reglas especiales: el servicio
resta del origen y suma al destino con la misma aritmética de `ledger.py`. Pagar la tarjeta es una
transferencia; comprar con ella sigue siendo gasto.

**D6 — Sobres.** Una transferencia puede dejar el saldo de la cuenta por debajo de lo comprometido
en sus sobres; **no bloquea** (coherente con la Fase 35). El disponible real puede quedar negativo.
`POST` y `PUT /transfers` devuelven un campo `warnings` (lista, vacía si no hay) calculado por el
backend; cada aviso es `{code: "BELOW_COMMITTED", account_id, currency, committed, balance_after}` con
saldo resultante de la cuenta y monto comprometido en sus sobres activos (solo cuentas de origen; el
destino sube su saldo). El formulario muestra el aviso tras guardar; el frontend no resta saldos por
su cuenta.

**D7 — Editar y borrar.** `PUT` y `DELETE` revierten el efecto anterior sobre los saldos y aplican
el nuevo, con row-lock sobre ambas cuentas en **orden fijo por id de cuenta** (evita deadlocks) y
la transacción de base de datos como unidad. Borrado real, sin soft-delete propio.

**D11 — Interés al redimir.** `POST /cdts/{id}/redeem` acepta una `account_id` destino opcional.
Con cuenta: crea la transferencia de redención por el **capital** (`principal`) y, si
`final_amount > principal`, una `Transaction` de **ingreso** por `final_amount − principal` en la
cuenta destino, con categoría base nueva **"Rendimientos"** (ingreso, `user_id = NULL`, agregada
a `DEFAULT_CATEGORIES` y sembrada por `ensure_default_categories` en el arranque, como las demás; la
pre-siembra de ocultas del registro y `seed.py` la cubren por el mismo catálogo). Esa transacción es un ingreso normal: cuenta en flujo, usa
`ledger.registrar_impacto` y el flujo habitual de alertas. La moneda de la cuenta destino debe
coincidir con la del CDT (`422` si no). Con cuenta y `final_amount < principal` → `422` (la
pérdida se registra a mano; caso fuera de alcance). El ingreso se crea desde el servicio CDT con
`ledger.registrar_impacto` (no genera alertas de presupuesto, que son solo de gasto), fechado en
`redeemed_on`; la creación de transacciones hoy vive en el router, así que se reutiliza o extrae lo
mínimo necesario sin cambiar su comportamiento. Sin `account_id`,
redimir se comporta exactamente como hoy (solo cambia de estado). Sin retención ni GMF.

**D12/D16 — Ciclo de vida del CDT vinculado.**
- Crear: `POST /cdts` acepta `source_account_id` opcional; con ella crea la transferencia de
  constitución (cuenta → CDT) en la fecha `opened_on`. La moneda de la cuenta debe coincidir con la
  del CDT.
- Editar (solo vigente, como hoy): cambiar `principal` u `opened_on` actualiza la transferencia de
  constitución vinculada y los saldos; cambiar la cuenta de origen se permite en la misma operación.
- Borrar un CDT **vigente** con transferencia: elimina la transferencia y revierte el saldo, en la
  misma transacción.
- Borrar un CDT **redimido con transferencias vinculadas**: `409` (las transferencias y el
  ingreso son historia real). "Deshacer redención" queda fuera de alcance.
- Borrar un CDT redimido **sin vínculo**: como hoy (D10 de la Fase 38).

**D13 — Fechas.** Mismas reglas que `Transaction`: solo-día `YYYY-MM-DD` en la zona del usuario
(si es hoy conserva la hora real; si es otro día queda a las 12:00 locales) o datetime; toda la
aritmética de calendario en `app/core/periods.py`, sin `datetime(...)` naive.

**D15 — Patrimonio.** Las fórmulas de `GET /dashboard/summary` no cambian: `net_worth = cuentas +
CDT vigentes`, `free_to_spend = cuentas − comprometido`. Cambian los valores de las cuentas, no los
campos. Sin desglose nuevo en el dashboard.

**D17 — Borrar cuentas.** `DELETE /accounts/{id}` responde `409` mientras la cuenta tenga
transferencias (como origen o destino), igual que con reglas recurrentes (a diferencia del `400`
actual por transacciones; diferencia consciente). Las cuentas se borran con `deleted_at`, así que la
FK no se rompe. `delete_user_cascade`
borra las transferencias del usuario antes de cuentas y CDT.

### Corrección de saldo inicial y migración de datos

**D4 — Script único, sin endpoint.** `opening_balance` sigue inmutable en la API. Un script
revisado (`scripts/`, con confirmación `--confirmo-copia` y `pg_dump` previo, patrón de
`scripts/fase34_reporte_x1.py`) corrige el saldo inicial de Bancolombia **y** `balance`
(+25.620.000 COP) y crea las transferencias vinculadas de los dos CDT:

| Qué | Monto | Fecha |
|---|---|---|
| Bancolombia → CDT de 22.000.000 COP | 22.000.000 | 2026-09-22 |
| Bancolombia → CDT de 10.000.000 COP | 10.000.000 | 2026-10-17 |
| Saldo inicial de Bancolombia (corrección) | 25.620.000 | — |
| **Saldo final esperado** | **2.614.000** (bolsillo incluido) | |

El script es idempotente: primero detecta el estado ya migrado (las dos transferencias existen y el
saldo es 2.614.000), en cuyo caso sale con éxito sin cambiar nada; si no, imprime el antes/después y
**aborta** si el saldo de Bancolombia no es 8.994.000, para no ejecutarse contra una base distinta. **25.620.000 no está verificado contra el extracto del banco**: es el valor que hace
cuadrar la cuenta; si aparece otro movimiento sin registrar, se ajusta antes de correrlo.

**D14 — Dólares a mano.** El dueño, ya desplegado, borra los dos movimientos "Dolares plenti" y
crea la transferencia de 642.000 COP → 200 USD (tasa 3.210) del 2026-10-05 desde la UI. No entra
al script.

Resultado esperado tras migrar y reclasificar: Bancolombia 2.614.000 COP; disponible real
1.614.000 COP (el millón del bolsillo ya está comprometido en el sobre del fondo de emergencia); el
patrimonio deja de contar los 32 millones dos veces; el gasto de octubre deja de incluir los
642.000.

### Backend

**B1 — Migración Alembic**: tabla `transfers` (FK a `users`, `accounts`, `cdts`; `CHECK`s de D3 y de
montos `> 0`; índices por `user_id, date`, `from_account_id`, `to_account_id`, `cdt_id`). La categoría
"Rendimientos" no va en la migración: va en el catálogo (D11). Skill `alembic-migration`; `alembic check` debe pasar.

**B2 — Servicio de transferencias** (`app/services/transfers.py`): casos de uso crear / editar /
borrar con locks (D7), función pura de cálculo de monto/tasa (D2) y la regla de coherencia de
monedas. Sin lógica en el router.

**B3 — Router `/api/v1/transfers`**: `POST`, `GET` (lista filtrable por cuenta y rango de fechas,
zona del usuario), `GET /{id}`, `PUT /{id}`, `DELETE /{id}`. `POST`/`PUT` devuelven `warnings` (D6).
Sin idempotencia por clave: no se replica el `IdempotencyKey` de `Transaction` (ver Out of Scope). Schemas Pydantic en
`app/schemas/transfers.py`; todo error vía subclases de `DomainError`.

**B4 — Feed de movimientos (`UNION`)**: endpoint nuevo `GET /api/v1/movements` que une
transacciones (no eliminadas) y transferencias en una sola consulta `UNION ALL` ordenada por
`date DESC, id DESC` y paginada en la base (misma forma de paginación que `GET /transactions`), con
un discriminador `kind` (`transaction` | `transfer`). Filtros: rango de fechas (zona del usuario),
`account_id` (una transferencia aparece si la cuenta es origen o destino) y `include_transfers`
(por defecto `true`). Los filtros que no tienen sentido para una transferencia (`category_id`, `type`
income/expense, búsqueda de texto) **excluyen** las transferencias. `GET /transactions` y todos sus
totales KPI **no cambian**: ningún agregado existente lee `transfers`. `/transactions` (frontend) pasa
a leer de `movements` solo para la lista; los KPI siguen viniendo de los endpoints actuales.

**B5 — CDT**: `crear`, `actualizar`, `redimir` y `eliminar` de `app/services/cdt.py` integran
transferencias según D11/D12 (incluye reutilizar o extraer la creación del ingreso "Rendimientos" desde el router de transacciones); el item del CDT expone `source_account_id` y las cuentas de las
transferencias vinculadas.

**B6 — Reconciliación y cuentas**: `reconciliar_cuenta` y `ledger.py` incorporan transferencias
(D1); `DELETE /accounts/{id}` aplica D17; `delete_user_cascade` las borra.

**B7 — Script de migración de datos** (D4).

### Frontend

**F1 — Modal "Transferir"** (origen, destino cuenta o CDT, monto de salida; monto de entrada **o**
tasa si las monedas difieren; fecha; descripción). Muestra la tasa implícita devuelta por el
backend y los `warnings` de D6.
**F2 — Lista de `/transactions`** (lee de `GET /movements`, B4): filas de transferencia con icono de flechas y color neutro, sin
signo de gasto/ingreso; filtro para ocultarlas; editar/borrar.
**F3 — CDT**: selector opcional de cuenta de origen en el formulario; selector opcional de cuenta
destino en el modal de redención; el borrado de un redimido vinculado muestra el `409` con copy
claro.
**F4 — Invalidaciones de TanStack Query**: crear/editar/borrar transferencia invalida cuentas,
transacciones, dashboard, CDT y sobres (mapa en `frontend/docs/STATE_AND_FETCHING.md`).

### Documentación

**X1 — Ambos contratos** (`backend/docs/API_REFERENCE.md` y `frontend/docs/API_CONTRACT.md`),
`backend/docs/BUSINESS_RULES.md` (regla nueva: **las transferencias no son flujo**), arquitectura
backend/frontend, `docs/CHANGELOG.md`, `docs/ROADMAP.md` (cerrar QA-030; renumerar 40 y 41),
`docs/TODO.md` (cerrar la deuda de redención de la Fase 38), `AGENTS.md` y
`docs/VISION_FINANZAS_RESPONSABLES.md`.

## Testing Decisions

- **Qué es un buen test aquí**: ejercita comportamiento externo (respuestas HTTP y saldos
  resultantes), no la forma de las funciones internas.
- **Seam principal**: la **API HTTP** con `TestClient` sobre Postgres 16 desechable (prior art:
  `test_transactions.py`, `test_funds_gasto.py`, `test_cdt.py`). Un solo seam para casi todo.
- **Seam secundario**: funciones puras de cálculo de monto/tasa (prior art: `test_cdt_logic.py`,
  `test_funds_logic.py`).
- **T1 — Puras**: monto desde tasa, redondeo, misma moneda, par sin COP.
- **T2 — CRUD de transferencias**: saldos origen/destino tras crear, editar y borrar; cambio de
  moneda con y sin tasa; `422` por validaciones (misma cuenta, monedas, `amount_in` y tasa a la
  vez); cuentas `credit`; `404` entre usuarios.
- **T3 — Invariante de flujo (contrato)**: con transferencias existentes, KPI del dashboard, dona,
  `cashflow-series`, Analítica, presupuestos/alertas y resumen semanal **no cambian**.
- **T4 — Reconciliación**: `balance == opening_balance + neto de transacciones + neto de
  transferencias`, incluyendo ediciones y borrados.
- **T5 — CDT**: crear con y sin cuenta; editar capital/apertura actualiza la transferencia; borrar
  vigente revierte; borrar redimido vinculado → `409`; redimir con cuenta crea transferencia +
  ingreso "Rendimientos"; `final_amount < principal` → `422`; redimir sin cuenta como hoy; tras crear un CDT vinculado, `net_worth` no cuenta dos veces el capital
  (D15).
- **T6 — Sobres y disponible real**: transferir bajo lo comprometido se permite, `warnings` trae
  `BELOW_COMMITTED` con los montos correctos (y vacío si no aplica) y el disponible real puede ser
  negativo.
- **T7 — Cuentas**: `DELETE /accounts/{id}` → `409` con transferencias; borrado de usuario en
  cascada.
- **T8 — Concurrencia** (`@pytest.mark.concurrencia`, patrón de `test_funds_gasto_concurrency.py`):
  dos transferencias cruzadas A→B y B→A simultáneas no hacen deadlock; saldos correctos.
- **T9 — Migración de datos**: el script sobre una copia sintética del estado actual (Bancolombia
  8.994.000) deja 2.614.000; una segunda corrida sale con éxito sin cambios; aborta si el saldo de
  partida no coincide y no está ya migrado.
  `tests/test_migrations.py` cubre `alembic check` de la tabla nueva.
- **T11 — Feed `UNION`**: orden por fecha, paginación sin duplicados ni saltos al cruzar transacciones
  y transferencias, `include_transfers=false`, filtro por cuenta (origen o destino), y los filtros de
  categoría/tipo/texto excluyen transferencias.
- **T10 — Navegador (Playwright, 390 px y desktop)**: crear transferencia COP→USD con tasa,
  verla en la lista con estilo neutro, ocultarla con el filtro, crear/redimir un CDT vinculado,
  comprobar dashboard.

## Out of Scope

- "Reembolsos como gasto negativo" (fila separada del backlog).
- Deshacer redención de un CDT.
- Ganancia o pérdida cambiaria y tabla histórica de tasas.
- Interés neto (retención en la fuente, GMF) y renovación de CDT.
- Tasas para pares de monedas sin COP.
- Editar `opening_balance` desde la API o la UI (solo el script único).
- Registrar la pérdida cuando `final_amount < principal` (se rechaza con `422`).
- Idempotencia por clave en `POST /transfers`.
- Cualquier cambio de seguridad/auth.

## Further Notes

- **Despliegue**: `pg_dump` previo; la migración de Alembic (tabla + categoría) corre sola en el
  `CMD` de Docker; el script de datos (D4) lo corre el dueño a mano **después** de la migración, y
  antes verifica contra el extracto del banco que 25.620.000 es la cifra correcta. La
  reclasificación de los dólares (D14) se hace después, desde la UI.
- **Riesgo**: la fase toca `ledger.py` y los saldos reales. Correr `analyze-spec` antes de
  implementar y `/code-review` al terminar.
- **Verificar al implementar**: que la categoría base "Rendimientos" no exista ya con otro nombre en
  `DEFAULT_CATEGORIES` o en la base real.

## Orden de ejecución

1. [backend] [P] Migración `transfers` — D1, D3, D13, B1.
   Depende de: —
2. [backend] [P] Función pura de monto/tasa + schemas, y "Rendimientos" en el catálogo — D2, D9, D11, B2.
   Depende de: —
3. [backend] Servicio de transferencias (con `warnings`), `ledger.py` y `reconciliar_cuenta` — D1, D5, D6, D7, B2, B6.
   Depende de: 1, 2
4. [backend] [P] Router `/transfers` y endpoint `/movements` (`UNION`) — D6, D7, D13, B3, B4.
   Depende de: 3
5. [backend] [P] Integración CDT (crear/editar/redimir/borrar, creación del ingreso) — D3, D11, D12, B5.
   Depende de: 3
6. [backend] [P] Guardas de cuentas y borrado de usuario — D17, B6.
   Depende de: 3
7. [verif] Tests de API, invariante de flujo, reconciliación, CDT, concurrencia, feed — T1–T8, T11.
   Depende de: 4, 5, 6
8. [docs] Contratos (ambos), BUSINESS_RULES, arquitectura — X1.
   Depende de: 4, 5
9. [frontend] Modal "Transferir", lista mixta, filtro, invalidaciones — F1, F2, F4.
   Depende de: 4, 8
10. [frontend] [P] CDT: selectores de cuenta y copy del `409` — F3.
    Depende de: 5, 8
11. [backend] Script de migración de datos + test — D4, B7, T9.
    Depende de: 3, 5
12. [verif] Prueba en navegador (Playwright) — T10.
    Depende de: 9, 10
13. [docs] Cierre: CHANGELOG, ROADMAP (QA-030, renumeración 40/41), TODO, AGENTS, VISIÓN.
    Depende de: 12
14. [infra] Despliegue: `pg_dump`, migración, script de datos, reclasificación de dólares (D14).
    Depende de: 13
