# Roadmap — Oikos

> Visión de producto y qué sigue. Para el historial de fases ya completadas (Fase 0 a Fase 26),
> ver `docs/CHANGELOG.md` — cada fase tiene ahí un resumen de 3-5 líneas y un pointer a su spec
> en `docs/specs/fase_NN_spec.md`.
>
> Formato: `[ ]` pendiente · `[x]` resuelto (con fecha).

---

## Cambio de enfoque — 2026-09-19: vuelta a uso personal

Oikos deja de perseguir el objetivo de "producto que cualquier persona pueda usar" del
2026-08-22. No hay plan de publicarlo, comercializarlo ni abrirlo a usuarios externos en el
futuro cercano — vuelve a ser una herramienta personal para su único dueño/desarrollador.

**Qué NO cambia:** el listón de calidad de código. Alembic, tests automatizados, versionado de
API y la capa de arquitectura (`app/services/`, `app/schemas/`, `app/core/exceptions.py`)
siguen en scope — no porque haya un modelo de amenaza multi-usuario, sino porque hacen que sea
más fácil seguir agregando features sin que el código se pudra. Mantenibilidad, escalabilidad
(del código, no de infraestructura) y modularidad siguen siendo objetivos explícitos.

**Qué SÍ cambia:** dejar de invertir esfuerzo en seguridad, autenticación y resistencia a abuso
más allá de lo que ya existe. El baseline llegado a la Fase 26 (cookies `httpOnly` + CSRF,
verificación de email, rate limiting básico, la corrección del account-takeover de Google OAuth
en Fase 23) se considera suficiente para un solo usuario de confianza. No proponer trabajo nuevo
de seguridad/auth salvo que algo esté roto de verdad (ej. el login de Google caído en
producción, ver `docs/TODO.md`) o el usuario lo pida explícitamente. El esfuerzo por defecto va
a features que mejoren el trackeo y análisis de gastos — ver "Backlog priorizado" abajo,
reordenado en base a este criterio.

Consecuencia directa sobre la auditoría del 2026-09-15 (`CODE_REVIEW.md`, ver memoria del
agente): su score de Seguridad (5/10) y varios de sus hallazgos de alta prioridad estaban
calibrados para un modelo de amenaza multi-usuario que ya no aplica. La mayoría de esos
hallazgos igual se resolvieron (Fases 23-26, antes de este pivote) por buenas razones
independientes del paradigma — pero los que seguían abiertos como "producto" (TTL/scopes de API
keys, rate limiting distribuido) pasan de "pendiente" a "fuera de scope" con este cambio, ver
abajo.

---

## Cambio de enfoque — 2026-08-22 (histórico, ver arriba)

Oikos deja de ser una app personal de un solo usuario para convertirse en un producto que
cualquier persona pueda usar. Esto invalida tres decisiones que estaban documentadas como "fuera
de scope": **Alembic, testing y versionado de API**. Las tres volvieron a scope en la Fase 7 (ver
`docs/CHANGELOG.md`).

El MVP se redefinió alrededor de **cinco componentes funcionales** — todos implementados, ver
"El MVP en cinco componentes" abajo y Fases 8–15 en el changelog.

### El cambio conceptual más importante

El producto actual es de **stock**: las cuentas guardan un saldo y el dashboard responde
*"¿cuánto tengo?"*. El nuevo MVP es de **flujo**: el dashboard responde
*"¿cuánto gasté este mes y cuánto me queda?"*.

Ambos conviven, pero el **dato principal del dashboard pasa a ser el flujo mensual**
(`ingreso mensual − gastos del mes`). Los saldos de cuentas siguen visibles, en vista
secundaria.

### Decisiones tomadas (2026-08-22)

| Decisión | Resolución | Consecuencia |
|---|---|---|
| ¿Cuentas visibles en v1? | **Sí, visibles** | `Account.balance` sigue siendo dato de cara al usuario → su fiabilidad **sigue en scope** (idempotencia + reconciliación). Multi-moneda sigue alcanzable → los bugs de moneda debían corregirse (Fase 11). |
| ¿Balance del dashboard? | **Flujo mensual**, con vista secundaria de saldos | Tarjeta principal reemplazada; se agregó `User.monthly_income`. |
| ¿Autenticación? | **Solo email** al inicio | Google OAuth se sumó después (Fase 20). Recuperación de contraseña fue bloqueante desde el día 1 (Fase 7). |
| ¿Canal de notificaciones? | **Push web** | PWA instalable + service worker + VAPID (Fase 13). |

---

## El MVP en cinco componentes

Los cinco están implementados — ver Fases 8–15 en `docs/CHANGELOG.md` para el detalle de cada uno.

1. **Captura de transacción en 3 toques** — pantalla principal, no modal. (Fase 10)
2. **Categorías default curadas**, luego ampliadas y personalizables. (Fases 8, 18)
3. **Dashboard mensual simple** — gastado / ingresado / balance + barras por categoría. (Fase 11)
4. **Presupuestos por categoría con alertas** — avisos al 80% y 100%. (Fase 13)
5. **Resumen semanal automático** — push cada lunes, cero esfuerzo del usuario. (Fase 14)

Más el **onboarding de 3 minutos** que lleva al usuario a su primer gráfico (Fase 15).

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

La siguiente fase planeada es la 29 — ver "Fase 29 — en definición" abajo.

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

## Fase 29 — en definición (grilling 2026-09-26): navegación por mes y selector de moneda

Primera fila del backlog ("Filtros de fecha y categoría en dashboard"), redefinida en el
`/grilling` del 2026-09-26. **Estado: grilling cerrado con entendimiento compartido; siguiente
paso `/to-spec` → `docs/specs/fase_29_spec.md`.** Esta sección es la entrada de ese paso — las
decisiones de abajo ya están tomadas por el dueño, no son propuestas.

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

## Pendientes abiertos

- [ ] **Login con Google caído en producción** (`disabled_client`) — sigue siendo prioritario
      porque afecta directamente el uso diario del dueño del producto, no porque sea
      "seguridad". Ver `docs/TODO.md` 🟠 para el estado de la apelación y el workaround activo.
- [ ] **Acceder y verificar el flujo completo desde celular vía Tailscale** (heredado de Fase 4A)
      — sigue siendo el canal de acceso diario real.
- [ ] **Seed automático tras el primer startup en Docker** (heredado de Fase 4B) — conveniencia
      personal, no bloqueante.
- [ ] **Script `scripts/deploy.sh`** (git pull → `docker compose up --build -d`) (heredado de
      Fase 4B) — conveniencia personal.
- [ ] **Generar credenciales reales de Google Cloud Console** para el despliegue
      (`GOOGLE_CLIENT_ID` / `NEXT_PUBLIC_GOOGLE_CLIENT_ID`) — el plumbing de Docker ya las
      propaga (Fase 20); depende de que se resuelva primero el `disabled_client` de arriba.
- [ ] **Evaluar reemplazar Lucide** por otra librería de íconos (Fase 12) — cambio de ~20
      archivos para un beneficio principalmente estético, sin prioridad.

Items que dejan de estar en esta lista tras el pivote del 2026-09-19 (rate limiting distribuido,
TTL/scopes de API keys como decisión de producto) pasaron a "Fuera de scope" abajo — ya no son
"pendientes", son decisiones cerradas mientras el proyecto sea de un solo usuario.

Ver también `docs/TODO.md` para deuda técnica y bugs confirmados no ligados a una fase específica.

---

## Backlog priorizado — reordenado 2026-09-19 para uso personal

Con las Fases 27–28 cerradas (arriba), este backlog retoma la numeración desde **Fase 29**: el
primer candidato de la tabla de abajo (navegación por mes + selector de moneda) está en
definición — ver "Fase 29 — en definición" arriba.

Criterio de prioridad: ¿esto hace que trackear y entender mis propios gastos sea más fácil o más
claro? Ya no hay criterio de "adquisición", "retención de usuarios" ni "efecto wow" de
marketing — se reformulan abajo en términos de valor de uso personal directo.

| Prioridad | Feature | Nota |
|---|---|---|
| Alta | **Navegación por mes en dashboard + selector de moneda** → **Fase 29, en definición** | Antes "Filtros de fecha y categoría en dashboard"; redefinida en el grilling 2026-09-26 (ver sección "Fase 29" arriba). El filtro por categoría se separó a su propia fila. |
| Media | **Filtro por categoría** (dashboard/Analítica) | Separado de la Fase 29 el 2026-09-26 — el dueño quiere revisarlo más a fondo antes de decidir alcance (¿una o varias categorías? ¿qué gráficos filtra? interacción con "ocultar categoría" de la dona). `GET /transactions/` ya soporta `category_id`; `category-distribution`/`cashflow-series` todavía no. |
| Alta | **Automatización de ingresos/gastos recurrentes** | El scheduler ya existe desde Fase 14. Reduce fricción de captura, que es tiempo que se puede invertir en mirar los datos en vez de cargarlos. |
| Alta | **Sinking funds** (gastos distribuidos en cuotas mensuales virtuales) | Validado por YNAB para presupuesto personal serio. Encaja directo con "cuánto me queda" del dashboard de flujo. |
| Media | **Vistas de tendencia / comparación entre meses** (nueva candidata) | No estaba en el backlog anterior porque el enfoque previo priorizaba features de producto sobre profundidad analítica. Encaja con el objetivo explícito de "que me facilite el análisis de mi dinero" — a definir alcance en una próxima sesión de spec. |
| Media | **Registro por nota de voz con IA** | Reencuadrada como conveniencia de captura personal, no "efecto wow" de marketing. Depende de la captura por nombre (Fase 16, ya lista). |
| Baja | **Multi-moneda ampliado** (tasas de cambio) | El modelo ya soporta agrupación por moneda; la conversión no está y no se necesita todavía. |
| Baja | **Sincronización offline** | Las columnas `updated_at` de Fase 8 la dejan preparada. |

`App nativa iOS/Android` se retira del backlog — ver "Fuera de scope" abajo, ya no tiene
justificación de distribución a otros usuarios.

---

## Fuera de scope (no hacer)

- ~~**Tracking de inversiones con vinculación de brokers**~~ — Es un producto distinto. Diluye la propuesta de valor. Como mucho, un campo manual de "patrimonio neto" en el futuro.
- ~~**Tarjetas de crédito avanzadas** (puntos, millas, intereses de mora, cuotas)~~ — Cada banco calcula distinto y las reglas cambian constantemente. Pesadilla operativa sin equipo dedicado.
- ~~**Temas visuales dinámicos**~~ — El modo claro/oscuro actual es suficiente. Ya implementado.
- ~~**Multi-idioma / i18n**~~ — Lanzamiento en español. Ya no aplica: sin plan de usuarios fuera de LATAM ni de usuarios externos en absoluto.
- ~~**CI/CD**~~ — Sin equipo ni usuarios externos que protejan de una regresión ajena; `run-tests` manual sigue siendo suficiente.
- ~~**Apple Sign-In**~~ — Evaluado en Fase 20 y descartado: Developer Program pago (99 USD/año) y complejidad desproporcionada para un proyecto web-only.
- ~~**Rol admin en la API**~~ — Evaluado en Fase 21 y descartado: el proyecto no tiene ningún concepto de roles hoy (authz es siempre "¿sos el dueño del recurso?") y agregarlo solo para operaciones de mantenimiento es desproporcionado. Se usa un script de management en su lugar.
- ~~**Rate limiting distribuido**~~ *(2026-09-19, antes "diferido")* — `slowapi` en memoria alcanza mientras el backend siga en un worker único, y con el pivote a uso personal no hay razón para escalar a múltiples réplicas. Diseño (Redis + `storage_uri`) queda documentado en `docs/specs/fase_07_spec.md` §2.6.1 por si algún día cambia el contexto, pero no es trabajo planeado.
- ~~**TTL obligatorio y scopes en API keys**~~ *(2026-09-19, antes "pendiente de decisión de producto")* — eran decisiones de "producto" pensadas para múltiples usuarios con distintos niveles de confianza. Con un solo dueño de todas las keys, el riesgo que mitigarían no aplica.
- ~~**App nativa iOS/Android**~~ *(2026-09-19, movida desde el backlog)* — la única justificación real (widgets, push nativas, Face ID) era secundaria incluso bajo el enfoque de producto; sin necesidad de distribución a otros usuarios, no justifica el esfuerzo frente a la PWA ya existente (Fase 13).
- ~~**Endurecimiento de seguridad adicional más allá de la Fase 26**~~ *(2026-09-19)* — el baseline actual (cookies httpOnly + CSRF, verificación de email, rate limiting básico, fix del account-takeover de Google OAuth) se considera suficiente para un solo usuario de confianza. No se audita ni se invierte tiempo de desarrollo en esto salvo que algo esté roto de verdad.
