# Archivo del ROADMAP — registro de los `/grilling` de las Fases 26 a 32

> Movido tal cual desde `docs/ROADMAP.md` el 2026-10-03 para dejar el roadmap solo con lo vigente.
> Es el **registro de decisiones** (Q1–Qn, estado del código relevado, supuestos y "fuera de
> la fase") que las specs `docs/specs/fase_26..32_spec.md` citan como su base. Las fases están
> completadas: el resumen está en `docs/CHANGELOG.md` y el detalle de implementación en cada spec.
> No se edita; lo vigente vive en `docs/ROADMAP.md`.

---

## Fase 26 — completada (2026-09-19): JWT en cookies httpOnly

Retomó el diseño de Fase 25 (§25.5, decisiones J1–J8): `login`/`login_google`/`refresh` setean
`access_token`/`refresh_token`/`csrf_token` como cookies `httpOnly` (más CSRF double-submit)
además del body de siempre; `get_current_user` acepta el cookie como fallback detrás del
header; el camino de API keys (`Authorization: Bearer oikos_pat_...`, Atajos de iOS) queda
intacto. Producción se consolidó en el dominio HTTPS del Tailscale Funnel como único origen
soportado para login por cookie (`COOKIE_SECURE=true` por default) — el acceso por IP directa
de Tailscale queda deprecado para sesión de navegador, no para API keys. Dos correcciones
encontradas en la revisión final antes de mergear (Path del cookie de refresh demasiado
angosto para que el logout revocara server-side; deadlock en el interceptor de refresh del
frontend si el refresh mismo devolvía 401) — ver `docs/CHANGELOG.md` para el detalle completo.
Spec: `docs/specs/fase_26_spec.md`.

La Fase 29 (navegación por mes + selector de moneda) se completó el 2026-09-26 — ver "Fase 29 —
completada" abajo. La Fase 30 (chip "Esta semana" en Transacciones, KPIs de Analítica desde el
backend y la deuda chica que dejó la Fase 29) también, el mismo día — ver "Fase 30 — completada".
La Fase 31 (corrección de los hallazgos de la QA 2026-09-26) se completó el 2026-09-27 — ver
"Fase 31 — completada". La Fase 32 (suite de tests sobre Postgres por defecto) también, el
2026-10-02 — ver "Fase 32 — completada".

---

## Fases 27–28 — completadas (2026-09-19): cierre de deuda de documentación/arquitectura/modularidad

Antes de retomar el backlog de features, se cerraron los últimos ítems de deuda de modularidad
que la auditoría 2026-09-19 (`CODE_REVIEW.md`) todavía marcaba como abiertos — a pedido explícito
del dueño del producto, revirtiendo la propia recomendación de la auditoría de tratarlos como
trabajo oportunista sin fase dedicada.

- **Fase 27** — `frontend/app/(dashboard)/transactions/page.tsx` (646 líneas, sobre el umbral de
  alerta) descompuesto en `TransactionFilters`/`TransactionList`/`EditTransactionModal`; la página
  queda en 313 líneas como orquestador. Refactor puro, sin cambio de comportamiento. Spec:
  `docs/specs/fase_27_spec.md`.
- **Fase 28** — `app/core/exceptions.py` deja de ser un piloto de `transactions.py` (Fase 25) y
  cubre los 65 `raise HTTPException` que quedaban en los 10 routers restantes, con una taxonomía
  genérica por status code (400–422, más 500/503 agregados durante la implementación). Cero
  cambio de contrato de API. Spec: `docs/specs/fase_28_spec.md`.

Con esto, la deuda de modularidad de `docs/TODO.md` 🟢 queda cerrada salvo la nomenclatura mixta
español/inglés (documentada como irrelevante en solitario) y la migración oportunista de call
sites a tipos generados desde OpenAPI (sin fecha, convivencia deliberada desde Fase 16 §16.3). La
próxima fase (29) retoma el backlog priorizado abajo.

---

## Fase 29 — completada (2026-09-26): navegación por mes y selector de moneda

Primera fila del backlog ("Filtros de fecha y categoría en dashboard"), redefinida en el
`/grilling` del 2026-09-26. **Estado: implementada y cerrada el 2026-09-26** — spec en `docs/specs/fase_29_spec.md`, resumen
en `docs/CHANGELOG.md`. Esta sección queda como registro del grilling que la originó (decisiones
Q1–Q16, tomadas por el dueño).

**Cambio de alcance respecto al backlog original:** el **filtro por categoría queda fuera** (el
dueño quiere pensarlo más a fondo, ver "Fuera de la Fase 29" abajo). En su lugar entra un
**selector de moneda**: la necesidad real detectada es que "Gastos por categoría" del dashboard
solo muestra la moneda preferida y la única forma de ver otra es cambiar la configuración.

### Estado del código relevado (2026-09-26)

- `GET /dashboard/summary` no recibe parámetros: fijo al mes en curso (día 1 → hoy, UTC), y
  cuenta **solo cuentas destacadas** si hay alguna. Ya devuelve `monthly_expense_by_currency`
  (las monedas con gasto en el mes, preferida primero).
- `GET /dashboard/budgets-progress` solo conoce el mes actual y llama
  `ensure_recurring_budgets_for_period` (genera presupuestos recurrentes al consultarse).
- `cashflow-series` y `category-distribution` ya aceptan `start_date`/`end_date`/`currency`/
  `account_id`. `GET /transactions/` acepta `start_date`/`end_date`/`category_id`, y
  `/transactions` en el front ya lee `?start=&end=` de la URL.
- `User.monthly_income` es un valor único **sin historial** (`models.py:31`).
- Analítica (`analytics/page.tsx`) tiene presets semana (últimos 7 días móviles) / mes / año /
  personalizado, todos terminando en *hoy*, con estado en la URL. Su moneda se deriva del filtro
  de cuenta ("Todas las cuentas" = preferida) y muestra un aviso de "cuentas en otra moneda no
  incluidas". No tiene selector de moneda libre.
- **Bug** — `app/(dashboard)/page.tsx:404`: el monto de "Transacciones recientes" se formatea con
  `config.currency` en vez de `tx.currency` (una transacción en USD se muestra como COP).
- **Inconsistencia** — `app/(dashboard)/page.tsx:44`: las barras por categoría del dashboard
  mandan el inicio de mes en hora **local** (`new Date(y, m, 1)`), mientras el backend calcula
  el mes de `summary` en **UTC** → en UTC-5 una transacción del día 1 entre 00:00 y 05:00 UTC
  cuenta en la tarjeta pero no en las barras.

### Decisiones tomadas con el dueño

| # | Decisión | Resolución |
|---|---|---|
| Q1 | ¿Qué pantalla? | **Ambas**: el dashboard (`/`) se vuelve navegable **por mes completo** (no rangos libres — `monthly_income`, presupuestos y alertas son mensuales); Analítica sigue siendo la pantalla de rangos libres. |
| Q2 | ¿Cómo se eligen fechas? | Dashboard: navegador `◀ ▶` de meses. Analítica: navegador `◀ ▶` aplicado al preset elegido (semana/mes/año) + el personalizado tal como está. |
| Q3 | Filtro por categoría | **Fuera de la Fase 29** — reemplazado por el selector de moneda (Q4/Q5). |
| Q4 | Selector de moneda en "Gastos por categoría" del dashboard | Chips/segmented (`COP \| USD`) en el encabezado de la sección. Opciones = monedas de `summary.monthly_expense_by_currency` del mes elegido + la preferida siempre. **Oculto si hay una sola moneda.** Estado en `useState`, default la preferida. |
| Q5 | ¿Selector de moneda también en Analítica? | **Sí**, mismo componente de chips (ver Q14). |
| Q6 | ¿Qué sigue al mes elegido en el dashboard? | **Todo**: tarjeta ingresos/gastos/balance, presupuestos, "Gastos por categoría" y transacciones (pasan a "últimas 5 **del mes**" + link "ver todas" a `/transactions?start=&end=` de ese mes). Mes en la URL: `?month=YYYY-MM`. |
| Q7 | Presupuestos recurrentes en meses pasados | `ensure_recurring_budgets_for_period` se llama **solo para el mes actual** (como hoy). Meses pasados muestran solo los presupuestos que existieron; si no hay, estado vacío "No había presupuestos en <mes>". Nada de filas retroactivas. |
| Q8 | Balance de flujo en meses pasados | Mes actual: `monthly_income − gasto` (sin cambio). **Meses cerrados: ingresos reales registrados − gastos reales**, calculado en el backend. Sin historial de `monthly_income`, sin migración. |
| Q9 | Límites de navegación | `▶` bloqueado en el mes actual (sin futuro). `◀` hasta el mes de la **primera transacción**, expuesto por el backend en `summary` (`first_transaction_month`). |
| Q10 | Bug de `tx.currency` en transacciones recientes | Se arregla **dentro de la Fase 29** (misma sección que se modifica). |
| Q11 | Contrato de API del mes | `GET /dashboard/summary` y `GET /dashboard/budgets-progress` aceptan `?year=&month=` (enteros, opcionales, **ambos o ninguno**; default = mes actual). **422** (`ValidationError`) si el mes es futuro, está incompleto o `month` fuera de 1–12. |
| Q12 | ¿Cómo sabe el front qué balance ve? | Campo nuevo en `summary`: `monthly_flow_basis: "declared" \| "actual"` junto a `monthly_flow_balance`. El front elige el rótulo ("Te quedan…" / "Balance de agosto"). En meses pasados el balance nunca es `null`. |
| Q13 | Navegador en Analítica | "Semana" pasa a **semana calendario lunes–domingo** ("Esta semana" = lunes → hoy). Estado **absoluto** en la URL: `?ref=YYYY-MM-DD` (inicio del período), no un offset relativo. Período actual termina hoy, pasados completos, `▶` bloqueado en el actual. El personalizado no tiene `◀ ▶`. |
| Q14 | Selector de moneda en Analítica | Opciones = monedas distintas de las cuentas del usuario (`accounts/` ya se carga ahí, sin endpoint nuevo). Visible solo con "Todas las cuentas"; con una cuenta elegida la moneda es la de la cuenta (como hoy). **Elimina el aviso de "cuentas en otra moneda no incluidas".** Estado en la URL (`?currency=`), consistente con los demás filtros de Analítica. |
| Q15 | UI del navegador del dashboard | `◀ Agosto 2026 ▶` en el encabezado de la página, sobre la tarjeta principal, **no sticky**. Botón "Volver a este mes" fuera del mes actual. El formulario inline de ingreso mensual (Fase 11) solo aparece en el mes actual. FAB/captura sin cambios (siempre fecha de hoy). |
| Q16 | Cuentas destacadas | Se **mantiene** el comportamiento actual (`summary` cuenta solo destacadas si hay; barras y presupuestos cuentan todas) — también para el balance "actual" de meses pasados. Unificarlo es una decisión de producto aparte → anotar como deuda en `docs/TODO.md`. |

### Supuestos aceptados (sin pregunta dedicada)

1. **Bordes de mes en UTC** en el front, con un único helper de rango de mes (mismo criterio que
   `buildDateRange` de Analítica) — corrige la inconsistencia de `page.tsx:44`.
2. Si al cambiar de mes la moneda elegida en los chips del dashboard no tiene gastos en ese mes,
   vuelve a la preferida.
3. `?ref=` a mitad de período se normaliza al inicio del período; `?ref=`/`?month=` futuro o
   inválido se trata como el período actual (no rompe la página).
4. Las query keys de TanStack incluyen el mes; las mutaciones siguen invalidando por prefijo, de
   modo que capturar una transacción refresca cualquier mes en caché. Actualizar
   `frontend/docs/STATE_AND_FETCHING.md`.
5. Verificación: tests pytest de los parámetros nuevos (mes pasado, mes futuro → 422, año/mes
   incompleto → 422, `monthly_flow_basis`, balance "actual", no generación retroactiva de
   presupuestos, `first_transaction_month`) + prueba con Playwright en desktop y 390×844.
6. Contrato de API cambia → actualizar **ambos** `backend/docs/API_REFERENCE.md` y
   `frontend/docs/API_CONTRACT.md`.

### Fuera de la Fase 29

- **Filtro por categoría** (dashboard o Analítica) — el dueño lo quiere revisar más a fondo;
  queda en el backlog como fila propia.
- Presets "últimos 3 / 12 meses" en Analítica (el personalizado ya los cubre).
- Navegación por mes en `/budgets`.
- Unificar el criterio de cuentas destacadas entre `summary` y el resto (→ `docs/TODO.md`).
- Historial de `monthly_income`.

---

## Fase 30 — completada (2026-09-26): semana calendario en Transacciones y deuda chica post-Fase 29

Surge del `/grilling` del 2026-09-26: llevar a `/transactions` el criterio de "Esta semana"
(lunes → hoy) que la Fase 29 (Q13) introdujo en Analítica, y aprovechar para cerrar los ítems
chicos de `docs/TODO.md` que la propia Fase 29 dejó anotados. **Estado: implementada y cerrada
el 2026-09-26** — spec en `docs/specs/fase_30_spec.md`, resumen en `docs/CHANGELOG.md`. Esta
sección queda como registro del grilling que la originó (decisiones Q1–Q10, tomadas por el
dueño). Flujo completo de `docs/WORKFLOW.md` (spec corta), porque Q6 cambia un contrato de API.

### Estado del código relevado (2026-09-26)

- `components/transactions/TransactionFilters.tsx:11-16`: chips `Todo el histórico / Últimos 7
  días / Este mes / Este año` (`DatePreset = 'all' | '7d' | 'month' | 'year' | 'custom'`).
- `app/(dashboard)/transactions/page.tsx:28-53` (`getPresetDates`) mezcla getters **locales**
  (`getFullYear()`/`getMonth()`/`setDate`) con `toISOString()` (**UTC**) — mismo tipo de bug que
  la Fase 29 corrigió en el dashboard (H4): después de las 19:00 hora Bogotá "Este mes" puede
  arrancar en un mes y terminar en otro. `lib/dateRanges.ts` ya tiene la semana lunes–domingo en
  UTC (`periodStartUtc`, hoy no exportada).
- `GET /dashboard/cashflow-series` responde una **lista pelada** (`list[CashflowData]`); su único
  consumidor es `analytics/page.tsx:249`, que suma los totales en un `useMemo` (`totals`,
  `:310`) — también los usa la dona como denominador (`income-total`).
- `GET /accounts/{id}/monthly-summary` arma su techo a mano (`api/accounts.py:142-145`, último
  día 23:59:59) en vez de `core/periods.limites_mes_utc` (techo = ahora en el mes en curso).
- `lib/hooks/useUserPreferences.ts:53-54` invalida solo `currentUser` y
  `dashboard.categoryBreakdown` al cambiar la moneda preferida.
- `app/(auth)/login/page.tsx:84` y `components/auth/GoogleAuthButton.tsx:55` redirigen a
  `/dashboard` (404; el dashboard vive en `/`).
- `app/(dashboard)/page.tsx:284`: el saludo dice **siempre** "Buenas tardes" y además produce un
  hydration mismatch ("de nuevo" en el server, el nombre en el cliente).

### Decisiones tomadas con el dueño

| # | Decisión | Resolución |
|---|---|---|
| Q1 | ¿Qué reemplaza a "Últimos 7 días"? | Chip **"Esta semana"** (lunes → hoy, UTC), misma semántica que Analítica. Los tres presets (semana/mes/año) calculan sus fechas con `lib/dateRanges.ts` (exportando el cálculo de inicio de período) — elimina la mezcla local/UTC de `getPresetDates`. |
| Q2 | Links viejos con `?preset=7d` | **Sin alias**: `7d` sale de la whitelist y cae a `all` (uso personal, no hay links compartidos que valga preservar). |
| Q3 | `◀ ▶` en Transacciones | **Fuera de la Fase 30** — anotado en el backlog abajo. |
| Q4 | Ítems de `docs/TODO.md` que entran | Los tres 🟠 triviales (invalidación por moneda, redirect `/dashboard`, hydration del saludo) + **KPIs de Analítica desde el backend** + **techo de `monthly-summary`**. |
| Q5 | Saludo | Depende de la **hora local del navegador** (es un saludo, no un borde de datos), calculado en cliente tras el montaje. |
| Q6 | Contrato de los KPIs de Analítica | `cashflow-series` pasa a responder un **objeto** `{ buckets: [...], total_income, total_expense, net }`. Rompe la forma, aceptado porque tiene un solo consumidor y el dueño confirmó que **no hay atajos/scripts propios que lo lean** (las API keys solo crean transacciones). Se elimina el `useMemo` de `totals`; la dona usa `total_income` del backend. |
| Q7 | Techo de `monthly-summary` | Solo **unificar** usando `limites_mes_utc` (techo = ahora en el mes en curso). **Sin** período consultable `?year=&month=` (la vista por cuenta no navega por mes). |
| Q8 | Qué invalidar al cambiar la moneda preferida | **Todo el prefijo `dashboard`** + las queries de Analítica que dependen de la moneda por defecto (verificar las keys al escribir la spec). |
| Q9 | Franjas del saludo | "Buenos días" 5:00–11:59, "Buenas tardes" 12:00–18:59, "Buenas noches" 19:00–4:59. Antes del montaje: **"Hola"**, con el nombre también diferido, para que server y cliente rendericen igual. |
| Q10 | Flujo de trabajo | **Flujo completo** (`/to-spec` → `/analyze-spec` → implementar → `/run-tests` → `/code-review` → `/analyze-spec cierre` → docs → PR), spec corta. |

### Supuestos aceptados (sin pregunta dedicada)

1. "Esta semana" termina **hoy** (igual que el período en curso de Analítica), no el domingo.
2. Contrato de API cambia → actualizar **ambos** `backend/docs/API_REFERENCE.md` y
   `frontend/docs/API_CONTRACT.md`, y regenerar `frontend/types/generated/api.ts`.
3. Verificación: pytest de la forma nueva de `cashflow-series` (totales = suma de buckets, filtro
   por moneda/cuenta) y del techo de `monthly-summary` (transacción con fecha futura del mes en
   curso no cuenta) + prueba con Playwright de los chips de `/transactions` en desktop y 390×844.
4. Al cerrar, marcar como resueltos en `docs/TODO.md` los 5 ítems que entran.

### Fuera de la Fase 30

- `◀ ▶` en los chips de `/transactions` (Q3).
- Guard de `GET /budgets/?month=&year=` en meses cerrados (sin call site en el frontend).
- Unificar el filtro de cuentas destacadas; alinear el mes UTC con la hora Bogotá.
- Login con Google caído (externo), puertos de docker (teórico), codegen de tipos y nomenclatura.

---

## Fase 31 — completada (2026-09-27): corrección de los hallazgos de la QA 2026-09-26

Sale de la primera pasada de QA (agente `qa-engineer` + Playwright, 2026-09-26, sobre `bc9dcb9`,
re-verificada contra Postgres 16). Reporte completo:
`.scratch/qa-2026-09-26/REPORTE_QA.md` (no versionado); ítems con causa y fix probable en
`docs/TODO.md` (`QA-001` a `QA-022`). Desde `bc9dcb9` solo entraron commits de docs, así que las
referencias de archivo y línea del reporte siguen vigentes.

**Estado: completada el 2026-09-27** (ver `docs/CHANGELOG.md` y la spec): 17 de los 22 ítems
de la QA resueltos; QA-014, QA-016, QA-017 y QA-018 quedan para flujo corto (Q1) y QA-002 ya
estaba resuelto. Historia previa: `/grilling` hecho el 2026-09-27 (decisiones Q1–Q16, tomadas por el dueño) y `/to-spec`
escrito el mismo día: `docs/specs/fase_31_spec.md`, sin marcadores abiertos (B10 resuelto: opción a) y
revisado con `/analyze-spec 31` el mismo día (sin CRÍTICO/ALTO, ajustes aplicados): listo para implementar.** **Flujo completo** de `docs/WORKFLOW.md`: la fase toca backend y frontend a la vez,
cambia reglas de `backend/docs/BUSINESS_RULES.md` (Q9, Q10) y contratos de API (Q9, QA-015).

Es una fase de bugs, no de features. Entra porque varios hallazgos rompen las dos garantías
centrales del proyecto: *el backend es la fuente de verdad de los saldos* (QA-003) y *el dueño
puede entrar a su app* (QA-021, QA-004). QA-021 toca auth, pero no es hardening nuevo: es un bug
que impide iniciar sesión (criterio "algo está roto de verdad" del pivote 2026-09-19).

### Alcance (Q1)

Bloques A a D más QA-001. Los ítems de entorno, seed, accesibilidad y detalles cosméticos (QA-016,
QA-014, QA-017, QA-018) quedan fuera y se hacen por flujo corto después de la fase.

| Bloque | Ítems |
|---|---|
| **A. Integridad contable (backend)** | QA-003 🔴 carrera en `DELETE`/`PUT /transactions/{id}` que descuadra el saldo · QA-015 🟠 `500` por overflow de `Numeric(14,2)` · QA-006 🟡 `total` cuenta las borradas · QA-019 🟢 techo del mes sin fracción de segundo · QA-020 🟢 misma `Idempotency-Key` con payload distinto en carrera → `200` en vez de `409` · QA-022 🟢 sesión Postgres asumida en UTC |
| **B. Frontend que se rompe o bloquea** | QA-021 🟠 bucle de recargas en `/login` · QA-004 🟠 un `422` con `detail` en lista tumba la página · QA-005 🟠 el onboarding no aparece tras registrarse con contraseña · QA-010 🟡 error de API mostrado como lista vacía en `/transactions` · QA-013 🟡 paso de ingreso del onboarding sin mensaje de error |
| **C. Montos que se muestran mal** | QA-007 🟡 todo redondeado a la unidad · QA-008 🟡 "Te quedan" no cuadra con "Ingresos del Mes" · QA-012 🟡 `BudgetRing` topa en 100% · QA-011 🟡 detalle de cuenta/categoría truncado a 100 |
| **D. Reglas de dominio** | QA-009 🟡 el modal de edición muestra una categoría y envía otra |
| **Entorno** | QA-001 🟠 el entorno dev de Docker comparte base, puertos y proyecto con producción |

### Estado del código relevado (2026-09-27)

- `components/auth/GoogleAuthButton.tsx:55` ya manda a `/capture?onboarding=1` si
  `!has_transaction_history`; `app/(auth)/login/page.tsx:85` usa la misma condición pero manda a
  `/capture` sin el flag. `has_transaction_history` es `true` con **2 o más** transacciones
  (`api/users.py:113`). En `/capture`, el paso de moneda del wizard depende solo del flag de la URL;
  el de ingreso, de `monthly_income == null`.
- `backend/tests/conftest.py` crea siempre un engine SQLite en memoria. En SQLite,
  `with_for_update()` no hace nada y `Numeric(14,2)` no se aplica: por eso QA-003 y QA-015 no los
  detectó la suite.
- `lib/formatters.ts` (`formatCurrency`) fija `minimumFractionDigits: 0, maximumFractionDigits: 0`
  para todas las monedas.
- `components/charts/BudgetRing.tsx:30` hace `Math.min(Math.max(raw, 0), 100)` antes de mostrar el
  porcentaje.
- `GET /transactions` ya filtra por `account_id` y `category_id` (`limit` 100 por defecto), y
  `/transactions` en el front ya lee `?account=` y `?category=` de la URL.
- `User.monthly_income` solo se usa en un cálculo: `monthly_flow_balance` del mes en curso
  (`api/dashboard.py:186`). En la UI aparece en el paso de ingreso del onboarding, en `/settings` y
  en el formulario inline del dashboard.
- **Categorías con transacciones de ambos tipos (reembolsos) — diseño deliberado.** El modal de
  creación (`TransactionModal.tsx:48-52`) tiene un toggle "ver todas las categorías" para registrar,
  por ejemplo, un ingreso en "Restaurante" cuando los amigos devuelven su parte, y
  `GET /dashboard/category-distribution?neto=true` (`api/dashboard.py:386`) netea `gasto − ingreso`
  por categoría (Analítica, `?neto=true`). El bug real de QA-009 está en
  `EditTransactionModal.tsx:156`: filtra estrictamente por tipo, sin toggle, y al cambiar el tipo el
  `<select>` muestra la primera opción visible mientras el estado conserva el `category_id` anterior.
  Fuera de la dona, el reembolso cuenta como ingreso en la tarjeta del dashboard y en los KPIs de
  Analítica, y los presupuestos solo suman gastos (`core/budget_alerts.py:29`).
- `docker-compose.dev.yml` no define `name:` ni puertos y no toca el volumen `pgdata`. El servicio
  `backup` de `docker-compose.yml` sube a Google Drive con retención de 30 días, y hoy también se
  levanta con el override dev.

### Decisiones tomadas con el dueño

| # | Decisión | Resolución |
|---|---|---|
| Q1 | ¿Qué entra en la fase? | Bloques A–D + QA-001. QA-016, QA-014, QA-017 y QA-018 van por flujo corto después de la fase. |
| Q2 | QA-003: cómo se serializan `PUT`/`DELETE` | `SELECT … FOR UPDATE` sobre la fila de la transacción al empezar `PUT` y `DELETE`, más borrado condicional como segunda defensa (`UPDATE … WHERE deleted_at IS NULL`; sin filas afectadas → `404` sin tocar el saldo). **No** se bloquean las cuentas: el `UPDATE balance = balance + x` ya es atómico. |
| Q3 | QA-003: test de regresión, y SQLite vs Postgres | `conftest.py` acepta `TEST_DATABASE_URL` para **toda la suite** (default SQLite). Test concurrente marcado `postgres`, saltado sin `TEST_DATABASE_URL`. Tests secuenciales en SQLite (segundo `DELETE` → `404` con saldo intacto; `PUT` sobre una transacción borrada → `404`). Receta del Postgres desechable en tmpfs documentada. Antes de cerrar, la suite completa se corre contra Postgres. **Mover la suite a Postgres por defecto es la Fase 32** (abajo): el dueño coincide en que es lo correcto, pero no se mezcla con una fase de bugs sin saber cuántos tests fallan. |
| Q4 | QA-005: cuándo aparece el onboarding | Un helper compartido por el login con contraseña y `GoogleAuthButton`: `!has_transaction_history` → `/capture?onboarding=1`. El paso de moneda solo se muestra si `monthly_income == null` (onboarding ya hecho = ingreso fijado). Sin migración. |
| Q5 | QA-021: bucle en `/login` | Frontend: el interceptor de `lib/api.ts` no redirige si ya está en una ruta de `(auth)`. Backend: el `401` de `POST /auth/refresh` llama a `limpiar_cookies_de_sesion`. Sin cambiar `haySesionActiva()`. Pasa por `security-reviewer` en el paso 9 del flujo, para no romper la base de la Fase 26. |
| Q6 | QA-004: `getApiError` y validación | `getApiError` aplana `detail` (lista u objeto) a texto legible. Además, `/capture` y los modales validan antes de enviar máximo 2 decimales y 12 dígitos enteros, con error de campo visible; el formulario no se pierde. |
| Q7 | QA-010: `/transactions` | Rango invertido → error de campo ("La fecha final es anterior a la inicial") y no se consulta; `min`/`max` en los inputs como ayuda. Un error de la API se muestra como error con "Reintentar" (patrón Fase 24), no como "Aún no tienes movimientos". Los filtros siguen visibles durante los reintentos. |
| Q8 | QA-007: decimales | Mínimo según la moneda (COP 0; USD, EUR y el resto 2) y máximo 2 siempre: un monto en COP con centavos los muestra, en USD siempre se ven. Ejes y etiquetas compactas de los gráficos no cambian. |
| Q9 | QA-008: "Te quedan" | **El balance del mes en curso pasa a ser ingreso real − gasto real**, igual que los meses cerrados. Revierte la base "ingreso declarado" de la Fase 11: tras semanas de uso, "Te quedan" sobre lo declarado confunde y no representa lo que realmente queda. `monthly_flow_basis` se conserva en el contrato, siempre `"actual"`, documentado como obsoleto. Rótulo "Balance de <mes>". Antes de cobrar, el balance del mes puede ser negativo, y eso es correcto. |
| Q14 | Ingreso declarado (`monthly_income`) tras Q9 | Queda como **referencia visual sin cálculo** en la tarjeta (p. ej. "Ingresos del mes $3.200 · esperado $3.000"), para dar contexto a un balance negativo a principio de mes. El paso del onboarding, `/settings` y el formulario inline se quedan, con copy ajustado para no prometer que alimenta un cálculo. |
| Q10 | QA-009: categoría vs tipo de transacción | **Se mantiene que una categoría acepte transacciones de ambos tipos** (reembolsos, neto de Analítica). El modal de edición gana el mismo toggle "ver todas" que el de creación: arranca activado si la categoría actual es de la otra naturaleza, y si al cambiar el tipo la categoría deja de estar visible se resetea. Así lo visible siempre coincide con lo enviado. Sin `422` en el backend y sin bloquear el cambio de naturaleza de una categoría con movimientos. La regla queda escrita en `BUSINESS_RULES.md` ("un ingreso en una categoría de gasto se interpreta como reembolso"), con su limitación actual: solo la dona netea. |
| Q15 | ¿Netear los reembolsos en toda la app? | **Fuera de la Fase 31.** Es un cambio de modelo (tarjeta, KPIs, presupuestos, alertas, resumen semanal) → fila nueva en el backlog, con su propio `/grilling`. |
| Q11 | QA-011: detalle truncado a 100 | `/accounts/[id]` y `/categories/[id]` muestran los últimos 20 movimientos más un link "Ver todos los movimientos" a `/transactions?account=<id>` / `?category=<id>`, que ya filtra y pagina. |
| Q12 | QA-012: `BudgetRing` por encima del 100% | El texto muestra el porcentaje real (106%) **y** el anillo representa el exceso (ver Q16). |
| Q16 | Cómo se dibuja el exceso | Segunda vuelta superpuesta en un rojo más intenso (estilo anillos de Apple Watch): 106% = anillo lleno + arco del 6%. Topada visualmente en 200%; el texto sigue mostrando el valor real. |
| Q13 | QA-001: aislar el entorno dev | `docker-compose.dev.yml` con `name: oikos-dev` (el volumen pasa a `oikos-dev_pgdata` y los contenedores son otros) y puertos reemplazados con `!override` (3001/8001, porque Compose suma las listas de puertos). **El servicio `backup` queda excluido en dev**: si no, subiría la base de dev al mismo remoto y la rotación de 30 días podría ir desplazando backups reales. Se corrige el comando dev de `CLAUDE.md`. |

Ítems sin decisión de producto, con el fix probable de `docs/TODO.md`: QA-015 (`max_digits=14,
decimal_places=2` en los schemas + overflow del saldo traducido a `ValidationError`), QA-006
(`count` con el filtro de soft-delete), QA-019 (techo exclusivo `< primer día del mes siguiente` en
`core/periods.py`), QA-020 (comparar `request_hash` en la rama `except IntegrityError`), QA-022
(`-c timezone=UTC` en `database.py`) y QA-013 (error de campo visible, patrón Fase 24 §24.2).

### Supuestos aceptados (sin pregunta dedicada)

1. Cada fix de backend lleva su test de regresión en pytest. El frontend se verifica con Playwright
   en desktop y 390×844 en el entorno aislado de la QA, **nunca** contra el stack de Docker local,
   que es producción.
2. Al cerrar, una segunda pasada corta del `qa-engineer` sobre los ítems resueltos, y se marcan `[x]`
   con fecha en `docs/TODO.md`.
3. Cambian contratos (validación de QA-015, `monthly_flow_basis` obsoleto y nuevo cálculo del
   balance en Q9) → actualizar **ambos** `backend/docs/API_REFERENCE.md` y
   `frontend/docs/API_CONTRACT.md`, y `BUSINESS_RULES.md` (Q9, Q10).

### Fuera de la Fase 31

- **Por flujo corto, después de la fase:** QA-016 (seed descuadrado y conteo de `CLAUDE.md`),
  QA-014 (accesibilidad de `ModalShell` y botones de categoría), QA-017 (hydration en `/settings`),
  QA-018 (detalles cosméticos).
- **Suite de tests en Postgres por defecto** → Fase 32 (Q3).
- **Reembolsos como gasto negativo en toda la app** → backlog (Q15).
- **Deuda ya aceptada que la QA confirmó vigente:** filtro de cuentas destacadas inconsistente
  (decisión de producto aparte), mes/semana en UTC frente a hora Bogotá (incluye la fecha por
  defecto del modal, que propone el día siguiente después de las 19:00), y
  `GET /budgets/?month=&year=` en meses cerrados.
- **Observaciones de la QA que no son bugs:** aviso en Ajustes de que el ingreso declarado se
  reinterpreta al cambiar la moneda principal, transferencias como tipo propio, cobertura baja
  de `email.py`/`user_deletion.py`/`weekly_summary.py`, warnings de pytest (`SAWarning`,
  `DeprecationWarning`, `passlib`/`crypt`) y `pnpm.onlyBuiltDependencies`. Candidatas a flujo
  corto aparte.
- Login con Google caído (externo), tests de frontend y CI (fuera de scope).
- QA-002 ya está resuelto (usuario semilla borrado de producción el 2026-09-26).

---

## Fase 32 — completada (2026-10-02): suite de tests sobre Postgres por defecto

Sale de la Q3 del `/grilling` de la Fase 31. Hasta esta fase `backend/tests/conftest.py` corría
siempre contra SQLite en memoria, mientras producción corre en Postgres 16, y esa diferencia dejó
fuera de la suite a QA-003 (SQLite serializa las escrituras y no aplica `FOR UPDATE`) y QA-015
(SQLite no aplica `Numeric(14,2)`). Probar contra el mismo motor que producción es la práctica
recomendada.

**Estado: implementada y cerrada el 2026-10-02** — spec en `docs/specs/fase_32_spec.md`, resumen
en `docs/CHANGELOG.md`. Historia previa: `/grilling` hecho el 2026-09-27 (decisiones Q1–Q10,
tomadas por el dueño) y `/to-spec` escrito al día siguiente, sin marcadores abiertos (B6 resuelto
con el dueño el 2026-09-28). Esta sección queda como registro de ese grilling y del terreno que se
midió antes de implementar. Suite verificada en los dos motores (supuesto 6): **351 pasan / 0 skip**
en el default de Postgres vía `testcontainers`, **341 pasan / 10 skip** en el opt-in
`TEST_DATABASE_URL=sqlite://`. El motor nuevo no destapó bugs nuevos (Q5).

Parte de lo que dejó la Fase 31: `conftest.py` ya aceptaba `TEST_DATABASE_URL` y la suite
completa ya se había corrido una vez contra Postgres, así que el inventario de tests que fallan por
diferencias de motor existía antes de empezar — y se volvió a medir para este grilling.

### Inventario medido (2026-09-27, contra HEAD)

Medido sobre un `postgres:16-alpine` desechable en tmpfs, con la receta de `AGENTS.md` (puerto
5433, base `oikos_test`):

| Corrida | Resultado | Tiempo |
|---|---|---|
| SQLite en memoria (default actual) | 341 pasan, 9 skip | 135 s |
| `TEST_DATABASE_URL=…oikos_test` | **349 pasan, 1 falla** | 149 s |

- El único fallo es
  `tests/test_soft_delete.py::TestUpdatedAt::test_updated_at_changes_on_put_but_not_on_read` —
  artefacto del fixture `db_session`, no bug de producción (Q4). Inventariado en
  `docs/TODO.md` §"Deuda nueva consciente de la Fase 31".
- **Postgres es ~10% más lento, no más rápido.** El argumento "SQLite es rápido" no sostiene el
  default, y el arranque del mecanismo que eligió Q1 es irrelevante contra los ~2.5 min de
  suite: un `docker run` pelado son 1-3 s, y el `PostgresContainer` de testcontainers medido en
  esta máquina tarda **8,6 s** (incluye el import de la librería y la espera del log de
  readiness).
- `alembic upgrade head` contra base limpia aplica las 12 migraciones sin problema, y
  **`alembic check` responde "No new upgrade operations detected"**: hoy no hay drift entre las
  migraciones y `models.py`, así que Q3 no requiere remediación previa — es ganancia pura.
  Ojo con el matiz que sí importa: ese `check` hay que correrlo contra una base **migrada**.
  Contra la base que arma el `create_all` de la suite (sin `alembic_version`) responde
  `FAILED: Target database is not up to date`, que es un falso positivo, no drift. De ahí el
  aislamiento que la spec le prescribe al test de drift.
- Entorno: Docker 29.7.2 y compose v5.5.0 disponibles. `testcontainers` **no** instalado
  (agregarlo es dependencia nueva); `psycopg2-binary` ya es dependencia; `pytest-xdist` tampoco.

### Estado del código relevado (2026-09-27)

- `conftest.py:68-88` — fixture `engine` de sesión: `drop_all`/`create_all` sobre
  `TEST_DATABASE_URL`, o `sqlite://` + `StaticPool`. `conftest.py:42-53` — guarda: el nombre de la
  base debe contener `test`. `conftest.py:56-65` — `pytest_collection_modifyitems` autoskippea el
  marker `postgres` si no hay env var. `conftest.py:271-404` — el seam `pg_*`: 4 fixtures que dan
  **sesión real por request** (con commits reales) en vez del savepoint único de `db_session`.
- `conftest.py:91-113` — `db_session` = **una sola conexión** con transacción externa + savepoints.
  Es lo que impide probar `FOR UPDATE`, y también lo que congela `now()` (Q4).
- `test_concurrency_pg.py:24` — marker a nivel de módulo. `:278,311` — lee
  `os.environ["TEST_DATABASE_URL"]` **directo** y duplica `create_engine` +
  `engine_kwargs_for_url` (ya disponibles por el fixture `engine`). `:284,300,317,359` —
  `ALTER DATABASE … SET timezone`, que es **a nivel de base**, con restore en `finally`.
- `conftest.py:306-313` — el teardown de `pg_client` hace `TRUNCATE` de tablas **globales**.
- `test_seed.py:46-55` — arma su **propio engine SQLite** con `PRAGMA foreign_keys=ON`; su
  docstring (`test_seed.py:1-9`) dice explícitamente que sin ese pragma la regresión que vigila
  pasaría inadvertida.
- `test_money_limits.py:206` — el otro test con marker `postgres` (overflow del saldo).
- `alembic/env.py:23` — la URL sale de `SQLALCHEMY_DATABASE_URL` (de `app.core.database`, que la
  construye **al import** desde `DATABASE_URL`), no de `alembic.ini`; `env.py:66-70` usa
  `engine_from_config` sin el `options: -c timezone=UTC` de `engine_kwargs_for_url`.
- La rama SQLite de `engine_kwargs_for_url` (`database.py:13-28`) es **código de producción** — el
  fallback de `app/core/database.py:10` para correr sin Docker —, no solo de test; ya está cubierta
  como función pura por `test_database.py`.
- Docs que nombran la base de test: `AGENTS.md:138,143-154` (§Tests) y
  `.agents/skills/run-tests/SKILL.md:14-17` (ese paso es el que la Fase 32 reescribe: hoy no nombra
  la base de test ni menciona Docker). `README.md:11`, `backend/README.md:43`,
  `backend/docs/DEPLOYMENT.md:11` y `backend/docs/ARCHITECTURE.md:30` hablan del fallback SQLite de
  la **app**, no de los tests → no se tocan. `scripts/git-hooks/pre-commit` no corre pytest (solo
  ruff/eslint/prettier) → no se toca. Sin CI (fuera de scope).

### Decisiones tomadas con el dueño

| # | Decisión | Resolución |
|---|---|---|
| Q1 | ¿Default de `pytest` y quién levanta el Postgres? | **`testcontainers-python`**: `pytest` levanta y destruye un `postgres:16-alpine` por sesión. Una `TEST_DATABASE_URL` explícita tiene prioridad si está definida. El argumento es la fricción, no la velocidad: `/run-tests` es el sustituto manual de CI y su valor depende de que `cd backend && pytest` **siempre** funcione. Un servicio de compose o un Postgres "largo" convierten "no levanté la DB" en un fallo que desincentiva correr la suite. |
| Q2 | ¿Qué pasa con SQLite? | **Sobrevive como opt-in explícito**, nunca como fallback automático. Un `pytest` "verde" en SQLite cuando se pidió Postgres es justo la clase de bug que esta fase viene a matar. Se conserva además porque la rama SQLite de `engine_kwargs_for_url` es código de producción. Si en la práctica nunca se usa, borrarlo después es un commit chico. |
| Q3 | ¿Schema por `create_all` o por `alembic upgrade head`? | **Las dos, con responsabilidades separadas**: `create_all` para la suite (rápido) + `alembic check` como test de sesión que falle si metadata y migraciones divergen. El valor real es el drift: hoy **nada** verifica que el head coincida con `models.py`, y un modelo editado sin migración pasa los 350 tests en verde y revienta en el `CMD` de Docker. |
| Q4 | El único test que falla en Postgres | **Se arregla el test, no producción.** `updated_at` se queda con `now()`: en producción cada request es su propia transacción, así que el comportamiento real es correcto y no hay bug que corregir. La restricción que ata la solución: `now()` en Postgres es `transaction_timestamp()` y **no se puede avanzar dentro de una transacción**, así que el `PUT` del test tiene que ocurrir fuera de la transacción externa de `db_session` — por el seam de sesión real por request (Q6). El `time.sleep(1.1)` se queda: sigue siendo lo que garantiza que los timestamps difieran. Resuelto en `docs/specs/fase_32_spec.md` (B6, 2026-09-28): **un solo `TestUpdatedAt` sobre el seam real**, sin partirlo en dos tests — el `INSERT` y los 4 `PUT` salen por sesiones reales por request y la lectura de `updated_at` por una sesión aparte, así que el `PUT` queda fuera de la transacción externa de `db_session`. Al usar el seam, el test se marca `concurrencia` (Q6) y **no corre en el opt-in de SQLite**: ese modo queda en 10 skips en vez de 9. Se evaluó y se descartó un teardown dialect-aware (`TRUNCATE … CASCADE` vs `DELETE FROM`) para conservarlo en los dos motores, porque volvería el teardown del seam dependiente del dialecto y del orden de borrado por FKs. |
| Q5 | Si el motor nuevo destapa bugs reales, ¿entran en la fase? | **Se anotan en `docs/TODO.md` con severidad**, no se arreglan acá. Excepción: si descuadra un saldo o rompe el login, entra igual — mismo criterio del pivote 2026-09-19 ("algo está roto de verdad" y las dos garantías centrales). La fase 32 es de infraestructura de test; mezclarla con fixes de dominio la hace inejecutable. |
| Q6 | El seam `pg_*` y el marker `postgres` | El marker **deja de ser de motor y pasa a ser de aislamiento**: `postgres` → `concurrencia`, fixtures `pg_*` → `real_*`, `test_concurrency_pg.py` → `test_concurrency.py`, y `test_money_limits.py:206` al marker nuevo. En modo SQLite se autoskippea con razón explícita ("requiere sesiones reales por request"), no porque le falte el motor. Con Postgres como default, un marker llamado `postgres` que dice "requiere Postgres" es redundante y garantiza que alguien lo skipee creyéndolo opcional. De paso, `test_concurrency_pg.py` deja de leer `os.environ["TEST_DATABASE_URL"]`. **Corregido al implementar:** no usa el fixture `engine` sino el de URL resuelta (`test_db_url`, para el nombre de la base) más un `admin_engine` nuevo (`NullPool` + `AUTOCOMMIT`), porque el `engine` de la suite no sirve ni para el `ALTER DATABASE` ni para garantizar la conexión nueva de verdad que necesita el `SHOW timezone` de control — ver B5 en `docs/specs/fase_32_spec.md`. |
| Q7 | ¿Cómo se pide explícitamente el modo SQLite? | **`TEST_DATABASE_URL=sqlite://`**, reusando la variable existente — cero conceptos nuevos, y la precedencia queda uniforme. La guarda de `conftest.py:42-53` pasa a aplicar **solo a URLs de Postgres**: existe para proteger una base real del `drop_all`, y una `sqlite://` no tiene nombre de base que proteger. Regla final: si hay `TEST_DATABASE_URL`, se usa tal cual; si no, testcontainers. |
| Q8 | `test_seed.py` y la aplicación de foreign keys | **Engine propio parametrizado por el dialecto activo**, con el `PRAGMA foreign_keys=ON` solo en SQLite. Lo que el test necesita es una *capacidad* (FKs aplicadas), no un motor: Postgres la da gratis, SQLite hay que pedirla. Usar el `engine` de la suite lo volvería **vacuo en modo SQLite** — el mismo falso verde que su propio docstring quiere evitar. |
| Q9 | `pytest-xdist` / paralelismo | **Fuera de la fase**, anotado en `docs/TODO.md` con el porqué. No está instalado y la suite no es paralelizable tal como está: `TRUNCATE` de tablas globales en el teardown de `pg_client`, una sola base compartida, y sobre todo `ALTER DATABASE … SET timezone` (a nivel de **base**) en los dos tests de timezone — eso no se aísla ni con esquemas por worker. Paralelizar obligaría a un contenedor o un `CREATE DATABASE` por worker. ~2.5 min es tolerable para un gate manual. |
| Q10 | Docs | `AGENTS.md` §Tests deja de decir "sin Docker/Postgres needed"; `run-tests/SKILL.md` gana el requisito de Docker y los dos modos; `docs/TODO.md` §"Insumo de la Fase 32" se marca resuelto; esta sección pasa a "completada" al cerrar. La receta `docker run` de `AGENTS.md:151-154` **sobrevive reducida a una línea**, reetiquetada como override: es el camino para correr la suite sin que testcontainers tenga el control, que es justo lo que uno quiere cuando el problema *es* testcontainers. No cambian `README.md` / `backend/README.md` / `DEPLOYMENT.md` / `ARCHITECTURE.md` (hablan del fallback de la app), ni el hook `pre-commit` (no corre pytest), ni las specs de Fases 7/20/29 (son historia). |

### Supuestos aceptados (sin pregunta dedicada)

1. `testcontainers` se agrega a `requirements.txt` en la sección de tests, y el contenedor usa
   `postgres:16-alpine` — la misma imagen que `docker-compose.yml`.
2. La suite se corre **completa en los dos modos** (Postgres default y SQLite opt-in) antes de dar
   la fase por cerrada, más el `alembic check` nuevo.
3. Sin cambios de contrato de API → no toca `backend/docs/API_REFERENCE.md` ni
   `frontend/docs/API_CONTRACT.md`.
4. `docs/specs/fase_07_spec.md` §4.2.1 ("SQLite en memoria para tests, no Postgres real") queda
   como historia: la Fase 32 lo revierte en la práctica, y esta sección del ROADMAP es donde se
   registra la reversión.
5. Flujo **completo** de `docs/WORKFLOW.md` (`/to-spec` → `/analyze-spec` → implementar →
   `/run-tests` → revisión de código → `/analyze-spec` cierre → docs de cierre → PR): el cambio no
   cabe en una frase, toca todo el conftest y agrega una dependencia. Spec `docs/specs/fase_32_spec.md`.
6. La suite se verifica en los **dos motores antes de cerrar** (Q2), no solo en Postgres: el modo
   SQLite es el que nadie va a ejercitar si no se corre a mano en cada cierre.

### Fuera de la Fase 32

- `pytest-xdist` / paralelismo de la suite (Q9) → `docs/TODO.md`, con el bloqueo de
  `ALTER DATABASE` anotado.
- **Borrar SQLite** del conftest si el opt-in de Q2 nunca llega a usarse — commit chico posterior.
- Tests de frontend (Vitest + React Testing Library) y CI/CD — siguen fuera de scope
  (ver "Fuera de scope").
- Los 🟡 de la QA que quedaron abiertos (QA-014, QA-016, QA-017, QA-018) — por flujo corto aparte,
  aunque `test_seed.py` se toque en esta fase. QA-016 (el seed descuadrado) **no** entra: es un bug
  del seed, no del motor de tests.
- La deuda ya aceptada de las Fases 29-31 (filtro de cuentas destacadas inconsistente, mes UTC
  contra hora Bogotá, `GET /budgets/?month=&year=` en meses cerrados) — no es de esta fase.

