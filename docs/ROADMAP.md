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

## Completada — Fase 33: corrección de la tercera pasada de QA (2026-10-04)

**Decisión del dueño (2026-10-04): se aplaza la fase de ingresos y gastos recurrentes** (ver más
abajo) **hasta cerrar todo lo relacionado con QA.** Son suficientes hallazgos como para dedicarles
una fase con el **workflow completo** de `docs/WORKFLOW.md` (`/grilling` → `/to-spec` →
`/analyze-spec` → implementar → `/run-tests` → `/code-review` → `/analyze-spec` de cierre → docs
de cierre → PR), no un flujo corto. La numeración pasa: esta es la **Fase 33**; la unificación de
zonas horarias queda como **Fase 34 probable** y recurrentes como **Fase 35 probable**.

La tercera pasada (stack dev aislado + Playwright con Chromium, cubriendo lo que la segunda dejó
pendiente: escritura en la UI, onboarding, modales, estados de error, push/alertas de punta a
punta y el borde domingo/lunes del resumen semanal) encontró **QA-034 a QA-041**; el `/analyze-spec` de la spec sumó **QA-042**. Reporte con
pasos, causas y capturas: `.scratch/qa-2026-10-03/REPORTE_QA_3.md`. Lo que sí quedó verificado en
verde: saldos tras crear/editar/borrar desde la UI, onboarding con cuenta nueva, alertas 80 %/100 %
sin duplicados y push real con FCM.

**Estado: implementada (2026-10-04), spec en `docs/specs/fase_33_spec.md`.** Los hallazgos
están en `docs/TODO.md` como `QA-034` a `QA-042`, resueltos. Una sola PR (rama `fix/qa-tercera-pasada`),
backend primero y frontend en paralelo.

| Ítem | Qué pasa | Lado |
|---|---|---|
| **QA-037** 🔴 | El job del lunes 07:00 (Bogotá) resume la semana que *acaba de empezar* (`weekly_summary.py:160-163`, cron en `main.py:162`): llega "no registraste gastos" aunque la semana cerrada tuviera gasto (W41 = 0 vs W40 = 1.850.000 en dev). Los tests no lo cazan porque llaman a la función con la fecha ya elegida. | backend |
| **QA-038** 🟠 | `_limites_semana` devuelve límites *naive* en hora de Bogotá y se comparan contra `Transaction.date` (`timestamptz`, UTC): ventana corrida 5 h. Caso reproducido: total 57 en vez de 60 (entra un gasto de la semana anterior, se pierde uno propio). Se corrige junto con QA-037, mismo archivo. | backend |
| **QA-040** 🟠 | Con el backend caído, `/accounts`, `/categories` y `/analytics` muestran datos vacíos sin error ni "Reintentar"; Cuentas enseña "Balance Total $ 0" como si fuera real. Mismo patrón que QA-004/QA-010. | frontend |
| **QA-034** 🟡 | En móvil (390 px) el aviso "Instalar" (PWA, `fixed z-50`) tapa el botón "Guardar" del modal de transacción. | frontend |
| **QA-035** 🟡 | "Nueva transacción" no valida la cuenta: manda `account_id: 0`, el backend responde 404 y el toast dice "no existe o no te pertenece". | frontend |
| **QA-036** 🟡 | En móvil el panel de notificaciones (`absolute left-0 w-80` anclado a la campana del sidebar) se sale 68 px de la pantalla y corta los textos. | frontend |
| **QA-039** 🟡 | El confirm de borrado (`useConfirmStore`) no tiene `role="dialog"`/`alertdialog` ni `aria-modal` y el foco no entra; la corrección de QA-014 solo cubrió `ModalShell`. | frontend |
| **QA-041** 🟢 | Voseo visible (8 textos en 3 archivos: Ajustes, paso de moneda del onboarding, gráfico de flujo) frente al tuteo del resto y mayúsculas CSS en "De"/"P. M." de las fechas de 4 feeds. `?onboarding=1` **se deja**: es el mecanismo de la Fase 15 (Decisión 15.5.1), no una fuga. | frontend |
| **QA-042** 🟢 | El email del usuario en el Sidebar se ve `Qa3@Test.com` por un `capitalize` de CSS. Hallado al analizar la spec de la Fase 33. | frontend |

**Decisiones del `/grilling` (2026-10-04):**

- **QA-037:** el job pasa `ahora − 7 días`; `build_weekly_summary` no cambia. El texto del resumen
  pasa a hablar de "la semana pasada".
- **QA-038:** límites aware en la constante `America/Bogota`; sin más cambios de zona en esta fase.
- **Choque de `period_key`** (el cron del 28-sep guardó `2026-W40` con contenido falso y el primer
  resumen correcto lo reutilizaría): SQL puntual que borra los `weekly_summary` existentes, sin
  migración; dev lo corre el agente, prod el dueño antes del lunes 5-oct 07:00 Bogotá.
- **QA-040:** componente de error compartido, reemplaza los usos inline; Cuentas no muestra el
  total mientras falle la query; se auditan también `accounts/[id]`, `categories/[id]` y `/settings`.
- **QA-034:** el banner "Instalar" se oculta con un modal o confirm abierto. **QA-036:** hoja fija
  en móvil, popover absoluto desde `sm`.
- **QA-039:** estándar de QA-014 (`alertdialog`, `aria-modal`, foco inicial en "Cancelar", trampa
  de foco, restaurar foco), reutilizando la lógica de `ModalShell`.
- **QA-035:** error en línea "Elige una cuenta." y preselección con una sola cuenta.
- **QA-041:** todo a tuteo (8 textos visibles, no los comentarios), mayúsculas solo en la primera letra de las fechas; `?onboarding=1` se deja como está (resuelto al redactar la spec). **QA-042:** quitar `capitalize` del email del Sidebar.

**Fuera de la fase, a propósito:** la unificación de zonas horarias (ver Fase 34 abajo).

**Cierre esperado de la fase:** reproducir cada hallazgo con un test o un paso de Playwright antes
de corregirlo; para QA-037/QA-038, un test del *job* con `freeze_time` en lunes 12:00Z y los dos
casos de borde de domingo; y una cuarta pasada corta de verificación en el stack dev aislado.
Nunca verificar contra el stack por defecto de Docker, que es producción.

---

## Completado — Flujo corto: bugs de la segunda pasada de QA (2026-10-03)

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

**Lo que la segunda pasada no cubrió** (escritura en la UI, onboarding, modales, estados de error y
carga, push y alertas de punta a punta, borde domingo/lunes del resumen semanal) **se verificó en
la tercera pasada (2026-10-04)** con Playwright ya con Chromium — ver la Fase 33 arriba.

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

## Siguiente fase probable — Fase 34: zona horaria por usuario

Sale del `/grilling` de la Fase 33 (2026-10-04): el dueño quiere que las horas queden unificadas y
no sean un problema, idealmente en la hora local del dispositivo y, mientras tanto, en Bogotá.
Mostrar fechas en la hora del dispositivo es fácil; lo difícil es que el backend agrega por día,
semana y mes (dashboard, Analítica, períodos de presupuesto, alertas) y el resumen semanal corre en
un cron sin dispositivo, así que todo necesita una zona horaria **guardada**. Diseño base a
confirmar en su `/grilling`: `User.timezone` (detectada del navegador al registrarse o en Ajustes,
`America/Bogota` por defecto) usada por todos los cálculos; la constante `SUMMARY_TIMEZONE` de la
Fase 33 se reemplaza por la del usuario. Cubre **QA-032** (desfase visible), la fecha por defecto
del modal (propone el día siguiente después de las 19:00; un gasto con fecha solo-día se lista como
el día anterior a las 19:00 y el modal de edición muestra la fecha UTC), la discrepancia entre el
resumen semanal (Bogotá) y Analítica / `/transactions` (semanas UTC) y la deuda de mes/semana en UTC
de las Fases 29–31. Necesita `/grilling` → `/to-spec` → `/analyze-spec` antes de implementar.

---

## Siguiente fase probable — Fase 35: ingresos y gastos recurrentes

**Aplazada (2026-10-04) hasta cerrar la Fase 33 (QA) y la 34 (zonas horarias).** Era la Fase 33; se
renumera, el contenido no cambia. Primera fila de prioridad Alta del backlog (abajo). El scheduler ya existe desde la Fase 14. Antes
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
- [x] **Apagar la recurrencia de un presupuesto desde la UI** *(resuelto 2026-10-03, flujo corto — `docs/specs/corto_recurrencia_presupuestos_spec.md`)* (hallado al revisar el PR #11,
      relacionado con QA-024; ya existía antes). Desmarcar "Repetir cada mes" en el mes actual
      no detiene la serie: `ensure_recurring_budgets_for_period` clona desde la fila recurrente
      más reciente de *otro* período, así que el mes siguiente se regenera desde una plantilla
      anterior que el usuario no ve. Hoy la única forma de cortarla es editar esa fila vieja.
      Flujo corto con `/grilling` corto primero: decidir si desmarcar corta la serie hacia
      adelante desde ese mes (recomendado) o apaga toda la serie de la categoría. Test: serie
      de 3 meses → desmarcar el actual → el siguiente no se genera.
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
| Alta | **Automatización de ingresos/gastos recurrentes** | **Fase 35 probable** (aplazada tras las Fases 33 de QA y 34 de zonas horarias). El scheduler ya existe desde Fase 14. Reduce fricción de captura, que es tiempo que se puede invertir en mirar los datos en vez de cargarlos. |
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
