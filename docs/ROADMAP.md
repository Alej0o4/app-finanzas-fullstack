# Roadmap — Oikos

> Visión de producto, qué está en curso y qué sigue. El historial de fases completadas (Fase 0 a
> Fase 32) vive en `docs/CHANGELOG.md`, con un resumen por fase; las decisiones numeradas del
> `/grilling` de cada una, el estado del código relevado y las verificaciones están en
> `docs/specs/fase_NN_spec.md`. Este archivo ya no los repite. El registro original de los
> `/grilling` de las Fases 26–32 (tablas Q1–Qn que las specs citan) se movió sin cambios a
> `docs/archive/ROADMAP_fases_26-32.md`.
>
> Formato: `[ ]` pendiente · `[x]` resuelto (con fecha).

---

## Cambio de enfoque vigente — 2026-09-19: vuelta a uso personal

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
a features que mejoren el trackeo y análisis de gastos — ver "Backlog priorizado" abajo.

Los hallazgos de la auditoría del 2026-09-15 (`CODE_REVIEW.md`) calibrados para un modelo de
amenaza multi-usuario (TTL/scopes de API keys, rate limiting distribuido) pasaron de "pendiente"
a "fuera de scope" con este cambio; los demás se resolvieron en las Fases 23–26.

## Contexto histórico (resumen)

- **2026-08-22 — pivote a producto multi-usuario** (revertido arriba). Dejó cosas que se
  quedaron: Alembic, testing automatizado y versionado de API (Fase 7), y el **cambio de stock a
  flujo**: el dashboard responde *"¿cuánto gasté este mes y cuánto me queda?"*, con los saldos de
  cuentas como vista secundaria. `Account.balance` sigue siendo dato de cara al usuario, así que
  su fiabilidad (idempotencia, reconciliación, bugs de moneda) sigue en scope. Decisiones de
  entonces: autenticación por email + Google (Fase 20), push web con PWA y VAPID (Fase 13).
- **El MVP en cinco componentes**, todo implementado (Fases 8–15, ver changelog): captura de
  transacción en 3 toques, categorías default curadas y personalizables, dashboard mensual,
  presupuestos con alertas al 80 % y 100 %, y resumen semanal automático — más el onboarding de
  3 minutos.
- **Fases 16–32:** automatizaciones móviles (API keys, captura por nombre), categorías y analítica
  por cuenta, correos con marca y Google OAuth, ajustes de cuenta, cierre del account-takeover,
  capa de servicios/schemas/excepciones, sesión en cookies `httpOnly` (26), navegación por mes y
  selector de moneda (29–30), corrección de la QA del 2026-09-26 (31) y suite de tests sobre
  Postgres por defecto (32). Todas completadas — ver `docs/CHANGELOG.md`.

---

## En curso — Flujo corto: bugs de la segunda pasada de QA (2026-10-03)

El flujo corto de QA-014/016/017/018 ya está mergeado. La segunda pasada del `qa-engineer`
(352 tests en verde, lint limpio, saldos de las 65 cuentas dev cuadrados) encontró QA-023 a
QA-033. Todo lo corregible sin decisión de producto se agrupa en **un solo flujo corto** de
`docs/WORKFLOW.md` (fix → test → `/run-tests` → `/code-review` → PR), en este orden:

**Estado: completado y mergeado (2026-10-03).** 406 tests en verde, lint limpio.

| Ítem | Qué se hizo | Lado |
|---|---|---|
| **QA-023** 🔴 | Validación `Query(ge/le)` en `budgets.py` (`month` 1–12, `year` 2020–2100); guarda de rango en `ensure_recurring_budgets_for_period`; `BudgetResponse` sin `ge/le` (mata el 500 eterno); estado de error + "Reintentar" en `budgets/page.tsx`. Limpieza SQL de basura provista para dev (`-p oikos-dev`) y prod (manual). | backend + frontend |
| **QA-024** 🔴 | Lápida del soft-delete: `select()` Core en `budget_recurrence.py` para que la fila borrada bloquee su período; borrar = saltar ese mes, la recurrencia sigue. Copy del confirm actualizado. | backend |
| **QA-025** 🟠 | `Query(ge/le)` en `transactions.py` (`le=1000`), `accounts.py` (`le=200`), `notifications.py` (`le=1000`). Patrón `^[A-Z]{3}$` en schemas de request (`AccountBase`, `TransactionBase`, `BudgetBase`, `PreferencesUpdate`); response models redeclarados sin patrón (tolerancia a filas heredadas). | backend |
| **QA-026** 🟡 | `PUT /transactions` usa `model_fields_set`: ausente conserva, `null` explícito limpia (aplicado a `description` y `payment_method`; `date` queda `is not None` porque el response exige `datetime`). | backend |
| **QA-027** 🟡 | `PUT /categories` bloquea cambio de `type` si hay transacciones o presupuestos activos → `ConflictError` 409. Reembolsos cruzados previos intactos. | backend |
| **QA-028** 🟡 | Validador `strip` + no-vacío en `CategoryBase.name` y `AccountBase.name` (compartido en `schemas/common.py`). Unicidad por usuario y `type` entre activas, comparando normalizado (NFKD→ascii→strip→lower). Pre-chequeo en API, sin restricción en DB. | backend |
| **QA-031** 🟢 | Eliminada query redundante de `cuenta_vieja` en `PUT /transactions`; se pasa `transaccion_db.account_id` (mismo efecto, `ledger` ya no-opera sobre soft-deleted). | backend |

Decisiones tomadas al implementar: **QA-024 → lápida** (la fila borrada es tombstone); **QA-028 → unicidad por (usuario, type)**; **moneda minúsculas → 422** (no normalizar). Aprobadas en el flujo corto, sin `/grilling` adicional.

**Pendiente de verificar (la segunda pasada no lo cubrió):** escritura en la UI (crear/editar
transacciones, onboarding con cuenta nueva, modales, estados de error y carga), push y alertas de
presupuesto de punta a punta, y el borde domingo/lunes del resumen semanal. El MCP de Playwright no
tiene Chromium instalado; el agente usó `playwright-core` de la caché de npx. Instalar el browser
antes de la siguiente pasada, o verificar esos flujos a mano al cerrar este flujo corto.

**Decisiones de producto separadas (no entran al flujo corto):**

- **QA-029** 🟡 — Una cuenta de crédito no puede crearse con deuda inicial (`AccountCreate.balance`
  exige `ge=0`); el seed solo logra −250.000 por vía interna. Decidir: permitir saldo negativo
  solo en crédito, o un campo "deuda inicial".
- **QA-030** 🟡 — No hay transferencias entre cuentas: mover dinero propio hay que registrarlo
  como gasto + ingreso, lo que infla los KPI de flujo, la dona y las alertas. Decidir junto con
  la fila "Reembolsos" del backlog (`/grilling` antes de spec).
- **QA-032 / QA-033** 🟢 — Desfase UTC/Bogotá visible en el dashboard (ya aceptado) y tarjeta
  "Balance" que ignora monedas distintas de la preferida sin advertencia. Candidatas a un aviso
  discreto en UI; sin prioridad.

Los hallazgos entran a `docs/TODO.md` como `QA-023+` al implementar. Nunca verificar contra el
stack por defecto de Docker, que es producción.

---

## Siguiente fase probable — Fase 33: ingresos y gastos recurrentes

Primera fila de prioridad Alta del backlog (abajo). El scheduler ya existe desde la Fase 14. Antes
de implementar toca `/grilling` → `/to-spec` → `/analyze-spec`. Preguntas abiertas: ¿la regla
genera la transacción sola o propone una para confirmar?; qué hacer con los días en que el
scheduler no corrió; frecuencia (mensual, semanal, día 31); cómo se edita o se salta una
ocurrencia; qué cuenta y moneda usa la regla. Los *sinking funds* (siguiente fila Alta) se apoyan
en gastos periódicos conocidos, por eso van después.

---

## Pendientes abiertos

- [ ] **Login con Google caído en producción** (`disabled_client`) — sigue siendo prioritario
      porque afecta directamente el uso diario del dueño del producto, no porque sea
      "seguridad". Ver `docs/TODO.md` 🟠 para el estado de la apelación y el workaround activo.
- [ ] **Acceder y verificar el flujo completo desde celular vía Tailscale** (heredado de Fase 4A)
      — sigue siendo el canal de acceso diario real.
- [ ] **Seed automático tras el primer startup en Docker** (heredado de Fase 4B) — conveniencia
      personal, no bloqueante. Relacionado con QA-016 (orden seed/arranque).
- [ ] **Script `scripts/deploy.sh`** (git pull → `docker compose up --build -d`) (heredado de
      Fase 4B) — conveniencia personal.
- [ ] **Generar credenciales reales de Google Cloud Console** para el despliegue
      (`GOOGLE_CLIENT_ID` / `NEXT_PUBLIC_GOOGLE_CLIENT_ID`) — el plumbing de Docker ya las
      propaga (Fase 20); depende de que se resuelva primero el `disabled_client` de arriba.
- [ ] **Evaluar reemplazar Lucide** por otra librería de íconos (Fase 12) — cambio de ~20
      archivos para un beneficio principalmente estético, sin prioridad.
- [ ] **Deuda aceptada de las Fases 29–31**, sin fecha: filtro de cuentas destacadas
      inconsistente entre `summary` y el resto (decisión de producto), mes/semana en UTC frente a
      hora Bogotá (incluye la fecha por defecto del modal, que propone el día siguiente después
      de las 19:00) y `GET /budgets/?month=&year=` en meses cerrados (con efecto de escritura; el caso de períodos inválidos es QA-023, en curso).
- [ ] **Candidatas a flujo corto aparte** (observaciones de la QA que no son bugs): aviso en
      Ajustes de que el ingreso declarado se reinterpreta al cambiar la moneda principal, cobertura
      baja de `email.py`/`user_deletion.py`/`weekly_summary.py`, warnings de pytest (`SAWarning`,
      `DeprecationWarning`, `passlib`/`crypt`), `pnpm.onlyBuiltDependencies` y borrar el modo
      SQLite opt-in del conftest si nunca se usa (Fase 32, Q2).

Ver también `docs/TODO.md` para deuda técnica y bugs confirmados no ligados a una fase específica.

---

## Backlog priorizado — reordenado 2026-09-19 para uso personal

Criterio de prioridad: ¿esto hace que trackear y entender mis propios gastos sea más fácil o más
claro? Ya no hay criterio de "adquisición", "retención de usuarios" ni "efecto wow" de
marketing. Las Fases 27–32 salieron de otras fuentes (deuda de modularidad, ajustes post-Fase 29,
la QA y la infraestructura de tests) y no consumieron filas de esta tabla, salvo la Fase 29.

| Prioridad | Feature | Nota |
|---|---|---|
| Alta | **Automatización de ingresos/gastos recurrentes** | **Fase 33 probable.** El scheduler ya existe desde Fase 14. Reduce fricción de captura, que es tiempo que se puede invertir en mirar los datos en vez de cargarlos. |
| Alta | **Sinking funds** (gastos distribuidos en cuotas mensuales virtuales) | Validado por YNAB para presupuesto personal serio. Encaja directo con "cuánto me queda" del dashboard de flujo. |
| Media | **Filtro por categoría** (dashboard/Analítica) | Separado de la Fase 29 el 2026-09-26 — el dueño quiere revisarlo más a fondo antes de decidir alcance (¿una o varias categorías? ¿qué gráficos filtra? interacción con "ocultar categoría" de la dona). `GET /transactions/` ya soporta `category_id`; `category-distribution`/`cashflow-series` todavía no. |
| Media | **Reembolsos como gasto negativo en toda la app** | Sale de la Q15 del grilling de la Fase 31. Hoy un ingreso en una categoría de gasto (p. ej. los amigos devuelven su parte del restaurante) solo se netea en la dona de Analítica (`?neto=true`): la tarjeta del dashboard y los KPIs lo cuentan como ingreso, y los presupuestos y sus alertas cuentan el gasto completo. Tratarlo como gasto negativo toca 5–6 cálculos del backend y varios contratos — a definir en su propio `/grilling`. |
| Media | **Vistas de tendencia / comparación entre meses** | Encaja con el objetivo explícito de "que me facilite el análisis de mi dinero" — a definir alcance en una próxima sesión de spec. |
| Media | **Registro por nota de voz con IA** | Conveniencia de captura personal, no "efecto wow" de marketing. Depende de la captura por nombre (Fase 16, ya lista). |
| Baja | **`◀ ▶` en los chips de `/transactions`** | Separado de la Fase 30 (Q3). Mismo patrón que Analítica (`?ref=`, título dinámico); falta decidir cómo convive con las fechas editadas a mano. |
| Baja | **Multi-moneda ampliado** (tasas de cambio) | El modelo ya soporta agrupación por moneda; la conversión no está y no se necesita todavía. |
| Baja | **Sincronización offline** | Las columnas `updated_at` de Fase 8 la dejan preparada. |

---

## Fuera de scope (no hacer)

- ~~**Tracking de inversiones con vinculación de brokers**~~ — Es un producto distinto. Diluye la propuesta de valor. Como mucho, un campo manual de "patrimonio neto" en el futuro.
- ~~**Tarjetas de crédito avanzadas** (puntos, millas, intereses de mora, cuotas)~~ — Cada banco calcula distinto y las reglas cambian constantemente. Pesadilla operativa sin equipo dedicado.
- ~~**Temas visuales dinámicos**~~ — El modo claro/oscuro actual es suficiente. Ya implementado.
- ~~**Multi-idioma / i18n**~~ — Lanzamiento en español. Ya no aplica: sin plan de usuarios fuera de LATAM ni de usuarios externos en absoluto.
- ~~**CI/CD**~~ — Sin equipo ni usuarios externos que protejan de una regresión ajena; `run-tests` manual sigue siendo suficiente. Tests de frontend (Vitest + React Testing Library): también fuera.
- ~~**Apple Sign-In**~~ — Evaluado en Fase 20 y descartado: Developer Program pago (99 USD/año) y complejidad desproporcionada para un proyecto web-only.
- ~~**Rol admin en la API**~~ — Evaluado en Fase 21 y descartado: el proyecto no tiene ningún concepto de roles hoy (authz es siempre "¿sos el dueño del recurso?") y agregarlo solo para operaciones de mantenimiento es desproporcionado. Se usa un script de management en su lugar.
- ~~**Rate limiting distribuido**~~ *(2026-09-19, antes "diferido")* — `slowapi` en memoria alcanza mientras el backend siga en un worker único, y con el pivote a uso personal no hay razón para escalar a múltiples réplicas. Diseño (Redis + `storage_uri`) queda documentado en `docs/specs/fase_07_spec.md` §2.6.1 por si algún día cambia el contexto, pero no es trabajo planeado.
- ~~**TTL obligatorio y scopes en API keys**~~ *(2026-09-19, antes "pendiente de decisión de producto")* — eran decisiones de "producto" pensadas para múltiples usuarios con distintos niveles de confianza. Con un solo dueño de todas las keys, el riesgo que mitigarían no aplica.
- ~~**App nativa iOS/Android**~~ *(2026-09-19, movida desde el backlog)* — la única justificación real (widgets, push nativas, Face ID) era secundaria incluso bajo el enfoque de producto; sin necesidad de distribución a otros usuarios, no justifica el esfuerzo frente a la PWA ya existente (Fase 13).
- ~~**Endurecimiento de seguridad adicional más allá de la Fase 26**~~ *(2026-09-19)* — el baseline actual (cookies httpOnly + CSRF, verificación de email, rate limiting básico, fix del account-takeover de Google OAuth) se considera suficiente para un solo usuario de confianza. No se audita ni se invierte tiempo de desarrollo en esto salvo que algo esté roto de verdad.
