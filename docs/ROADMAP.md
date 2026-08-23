# Roadmap — Oikos

> Plan de desarrollo priorizado por impacto real.
> Cada fase es independiente salvo que se indique lo contrario.
>
> Formato: `[ ]` pendiente · `[x]` resuelto (con fecha).

---

## Cambio de enfoque — 2026-08-22

Oikos deja de ser una app personal de un solo usuario para convertirse en un producto
que cualquier persona pueda usar. Esto invalida tres decisiones que estaban documentadas
como "fuera de scope": **Alembic, testing y versionado de API**. Las tres vuelven a scope.

El MVP se redefine alrededor de **cinco componentes funcionales** (ver Fases 7–12).

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
| ¿Cuentas visibles en v1? | **Sí, visibles** | `Account.balance` sigue siendo dato de cara al usuario → su fiabilidad **sigue en scope** (idempotencia + reconciliación). Multi-moneda sigue alcanzable → los 3 bugs de moneda **deben corregirse**. |
| ¿Balance del dashboard? | **Flujo mensual**, con vista secundaria de saldos | Tarjeta principal se reemplaza; se agrega `User.monthly_income`. |
| ¿Autenticación? | **Solo email** por ahora | Google OAuth queda en backlog. Recuperación de contraseña pasa a bloqueante. |
| ¿Canal de notificaciones? | **Push web** | Requiere PWA instalable + service worker + VAPID. Ver advertencia en Fase 11. |

---

## El MVP en cinco componentes

1. **Captura de transacción en 3 toques** — pantalla principal, no modal.
2. **Categorías default curadas** — 8–10 con íconos, sin editor en v1.
3. **Dashboard mensual simple** — gastado / ingresado / balance + barras por categoría.
4. **Presupuestos por categoría con alertas** — avisos al 80% y 100%.
5. **Resumen semanal automático** — push cada lunes, cero esfuerzo del usuario.

Más el **onboarding de 3 minutos** que lleva al usuario a su primer gráfico.

---

## Fase 7 — Cimientos multi-usuario

**Objetivo:** que la app pueda recibir usuarios que no seas tú sin riesgo de pérdida de datos
ni de cuentas irrecuperables. **Bloquea todas las fases siguientes.**

> ⚠️ **Alembic va primero.** Todas las fases posteriores agregan columnas. Hacerlo después
> significa reescribir migraciones ya aplicadas.

### Migraciones y esquema

- [ ] **Adoptar Alembic** — reemplazar `create_all()` + los `_ensure_*_column()` ad-hoc de `main.py` — 1d
  - Generar migración inicial desde el esquema actual.
  - Retirar `_ensure_user_preference_columns()`, `_ensure_category_icon_column()`, `_ensure_account_highlighted_column()`.
  - Retirar la migración legacy de categorías `"Otro (Ingreso)"` de `seed_default_categories()` (corre en cada arranque).

- [ ] **Bug latente: `preferred_theme` nunca se agrega en DB existentes** — 1h
  - `_ensure_user_preference_columns()` agrega `preferred_currency` y `preferred_locale` pero no `preferred_theme`.
  - Se resuelve con la migración inicial de Alembic.

- [ ] **Índices en `transactions`** — `user_id`, `account_id`, `category_id`, `date` — 2h
  - Todas las queries filtran por `user_id + date`; hoy hacen table scan.
  - Índice compuesto `(user_id, date)` como mínimo.

- [ ] **Constraint `UNIQUE(user_id, category_id, month, year)` en `budgets`** — 1h
  - Hoy se valida solo en Python → dos requests concurrentes crean duplicados.

- [ ] **`nullable=False` en FKs de `transactions`** (`user_id`, `account_id`, `category_id`) — 1h

### Ciclo de vida de cuenta

- [ ] **Recuperación de contraseña** (token de un solo uso + expiración) — 1d
  - **Bloqueante absoluto.** Sin esto, un usuario que olvida su clave pierde la cuenta.
  - Requiere servicio de correo transaccional (ver Fase 11 — se puede adelantar aquí).

- [ ] **Verificación de email en registro** — 1d
  - Evita cuentas basura y valida el canal de recuperación.

- [ ] **Política de contraseñas** más allá de `min_length=8` — 2h

- [ ] **Rate limiting en registro y recuperación** (hoy solo hay en login) — 2h

- [ ] **Invalidación del access token en logout** — 4h
  - Hoy el JWT sigue válido hasta 60 min después de cerrar sesión.
  - Opción simple: bajar TTL a 15 min y apoyarse en el refresh token.

- [ ] **Rate limiting distribuido** — `slowapi` en memoria no funciona con múltiples workers — 4h

### Operación y seguridad

- [ ] **Script `scripts/backup.sh`** — `pg_dump` con rotación de 7 días — 1d
  - Con datos de terceros esto pasa de molesto a inaceptable.

- [ ] **Secretos fuera de `docker-compose.yml`** — 4h
  - Hoy: `POSTGRES_PASSWORD: oikos_secret` hardcodeado y `SECRET_KEY:-changeme_in_production` como default silencioso.
  - El default silencioso debe fallar el arranque, no continuar.

- [ ] **Retirar el regex CORS `100.x.x.x`** en despliegue público — 1h

- [ ] **Logging estructurado** — sin esto no puedes diagnosticar el reporte de un usuario — 1d

### Versionado y pruebas

- [ ] **Versionar la API bajo `/api/v1/`** — 2h
  - Barato ahora, carísimo después. Todas las fases siguientes construyen sobre las rutas versionadas.

- [ ] **Tests del módulo contable y de autenticación** (pytest + httpx) — 2d
  - No cobertura completa: solo la lógica que mueve dinero y la que da acceso.
  - Es el código de mayor riesgo del proyecto y hoy no tiene ninguna prueba.

---

## Fase 8 — Modelo de datos del nuevo MVP

**Objetivo:** las columnas y entidades que los 5 componentes necesitan. Depende de Fase 7 (Alembic).

- [ ] **`User.monthly_income`** (`Numeric(14,2)`, nullable) — 2h
  - Lo captura el onboarding; activa el balance de flujo del dashboard.

- [ ] **`Transaction.payment_method`** (nullable: `cash` / `card` / `transfer`) — 3h
  - Tag ligero, **no** un módulo de configuración de métodos de pago.
  - Distinto de `Account.type`: el método es de la transacción, no de la cuenta.

- [ ] **Presupuestos recurrentes** — 1d
  - 🔴 **Bloqueador de retención.** Hoy `Budget` exige `month`+`year` fijos: el presupuesto de enero
    desaparece en febrero y el dashboard queda vacío, rompiendo el loop registro → feedback → ajuste.
  - Opción: `is_recurring` + resolución del periodo en consulta, o generación perezosa del mes actual.

- [ ] **Categorías default ampliadas a 8–10** — 3h
  - Agregar: **Vivienda**, **Salud**, **Educación**.
  - Renombrar `Ocio` → `Entretenimiento`.
  - Revisar categorías de ingreso (hoy solo existe `Salario`).

- [ ] **Cuenta por defecto al registrarse** — 3h
  - 🔴 **Bloqueador de onboarding.** Un usuario nuevo tiene 0 cuentas, `account_id` es obligatorio
    y `QuickTransactionModal` hace `return` en silencio: el botón "Registrar" no hace nada,
    sin error ni aviso.
  - Auto-crear una cuenta "Efectivo" en el registro.

- [ ] **`updated_at` + borrado lógico en todas las entidades** — 1d
  - Trivial ahora; migración con datos reales después.
  - Habilita sincronización offline si algún día hay app nativa.

---

## Fase 9 — Captura en 3 toques

**Objetivo:** que registrar un gasto tome menos de 8 segundos. Es el corazón del producto.

- [ ] **Pantalla de captura como ruta principal** — 2d
  - Hoy la entrada es el dashboard y la captura es un modal encima.
  - El MVP invierte esto: captura primero, dashboard después de guardar.

- [ ] **Rediseño del formulario a 3 interacciones** — 2d
  - Hoy `QuickTransactionModal` pide **6 campos** (tipo, valor, cuenta, categoría, fecha, descripción)
    con dos `<select>` nativos.
  - Objetivo: monto (teclado numérico) → categoría (íconos grandes, no dropdown) → guardar.
  - Fecha = hoy por defecto, sin mostrar. Descripción oculta tras "más opciones".
  - Cuenta preseleccionada; el selector solo aparece si el usuario tiene más de una.

- [ ] **Tag de método de pago** en la captura — 4h

- [ ] **Idempotencia (`Idempotency-Key`)** en `POST /transactions` — 1d
  - Un reintento por mala señal hoy crea una transacción duplicada y descuadra el saldo.

- [ ] **Corregir el fallo silencioso del submit** — 2h
  - `if (!effectiveAccountId || !categoryId || !amount) return;` no da ninguna señal al usuario.

---

## Fase 10 — Dashboard de flujo mensual

**Objetivo:** el "aha moment" — que el usuario vea su dinero graficado lo antes posible.

- [ ] **Tarjeta principal de flujo mensual** — 1d
  - Tres datos: total gastado, total ingresado, **balance del mes**.
  - Reemplaza la tarjeta actual `Balance Total` (que suma saldos de cuentas, no flujo).

- [ ] **Desglose por categoría en barras horizontales** ordenadas de mayor a menor — 1d
  - Existe `CategoryDonutChart`; el MVP pide barras.

- [ ] **Vista secundaria de saldos de cuentas** — 4h
  - Decisión 2026-08-22: los saldos siguen accesibles, solo dejan de ser el dato principal.
  - La página `accounts/` ya cubre buena parte de esto.

- [ ] **Podar del flujo principal** — 1d
  - Página `analytics/` + `CashflowChart` + `ChartControlsPopover` + filtros de fecha → detrás del menú.
  - Editor de categorías (`categories/`, `categories/[id]`) → **ocultar, no borrar**.
  - No se elimina código: se retira de la ruta principal.

- [ ] **Corregir los 3 bugs multi-moneda restantes** — 1d
  - Como las cuentas quedan visibles y multi-moneda sigue alcanzable, estos bugs son reales:
    - `budgets-progress` suma gastos **sin filtrar por moneda** y los compara contra `Budget.currency`.
    - `cashflow-series` suma todas las monedas en una sola serie.
    - `category-distribution` mezcla monedas en los totales por categoría.
  - Mismo defecto que ya se corrigió en `/summary` en 2026-07-14.

- [ ] **`actualizar_transaccion` no actualiza `currency`** — 2h
  - Mover una transacción de una cuenta COP a una USD la deja con `currency="COP"`.

---

## Fase 11 — Presupuestos con alertas + infraestructura de notificaciones

**Objetivo:** el primer diferenciador real frente a una hoja de cálculo.

> ⚠️ **Advertencia sobre push web.** En iOS, las notificaciones push solo funcionan si el
> usuario **instaló la PWA en su pantalla de inicio** (Safari 16.4+). Un usuario que solo
> visita la web en el navegador **no recibirá nada** — ni alertas de presupuesto ni resumen
> semanal. Como dos de los cinco componentes del MVP dependen de este canal, conviene
> prototiparlo temprano y considerar un **fallback in-app** (bandeja de avisos dentro de la app)
> o correo como respaldo.

- [ ] **PWA instalable** (manifest + service worker + prompt de instalación) — 2d
  - Prerrequisito de push. Beneficio extra: cubre buena parte del caso "app móvil" sin código nativo.

- [ ] **Infraestructura de push web** (VAPID, tabla de suscripciones, envío) — 3d

- [ ] **Motor de evaluación de presupuestos** (umbrales 80% y 100%) — 2d
  - Un aviso por umbral por periodo: no repetir en cada transacción.

- [ ] **Indicador visual de progreso** que cambia de color al acercarse al límite — 1d
  - `BudgetRing` ya existe; adaptar al lenguaje visual del MVP.

- [ ] **Bandeja de avisos in-app** como fallback — 1d

---

## Fase 12 — Resumen semanal automático

**Objetivo:** re-engagement pasivo. El usuario recibe valor sin abrir la app.

> El template es barato; **el canal de entrega no**. Hoy no existe scheduler ni servicio de envío.
> Presupuestar como infraestructura, no como detalle.

- [ ] **Scheduler** (APScheduler o cron externo) — 1d
- [ ] **Cálculo del resumen semanal** — total gastado, categoría principal, comparación con la semana anterior — 1d
- [ ] **Envío vía push** + entrada en la bandeja in-app — 1d
- [ ] **Preferencia de usuario para activar/desactivar** el resumen — 4h

---

## Fase 13 — Onboarding de 3 minutos

**Objetivo:** llevar al usuario a ver su primer gráfico lo más rápido posible.
Depende de Fases 8, 9 y 10.

- [ ] **Minuto 0–1: registro sin fricción** — 1d
  - Solo email (decisión 2026-08-22). Sin formularios largos.
  - Una sola pregunta: *"¿Cuál es tu ingreso mensual aproximado?"* → `User.monthly_income`.

- [ ] **Minuto 1–2: primer gasto guiado** — 1d
  - Redirección directa a la captura con instrucción explícita.
  - Requiere la cuenta por defecto de Fase 8.

- [ ] **Minuto 2–3: el "aha moment"** — 1d
  - Redirección al dashboard mostrando el impacto: *"Has gastado X de tu ingreso mensual."*

---

## Fase 14 — Automatizaciones y preparación móvil (post-MVP)

**Objetivo:** habilitar atajos de iOS/Android. El backend ya es REST/JSON stateless con bearer
tokens, así que **no hay que rehacer nada** — solo agregar las piezas que faltan.

- [ ] **API keys personales revocables** — 2d
  - 🔑 **Es lo que habilita los atajos.** Un Shortcut de iOS no puede hacer el flujo OAuth2
    password ni refrescar un token cada 60 minutos.
  - La misma pieza sirve para la nota de voz con IA de v1.2.

- [ ] **Endpoint de captura rápida por nombre** — 1d
  - Aceptar `category: "Alimentación"` en vez de `category_id: 3`.
  - Un Shortcut no puede resolver IDs cómodamente. También es la puerta de entrada natural
    para el parseo de lenguaje natural.

- [ ] **Codegen de tipos desde OpenAPI** — 1d
  - FastAPI ya expone el schema. Elimina el drift manual entre Pydantic y TypeScript.
  - Con una app nativa serían tres copias de los tipos en vez de dos.

- [ ] **Reconciliación de saldos** — 1d
  - Como las cuentas quedan visibles, hace falta una operación "recalcular saldo desde movimientos".
  - Hoy, si un saldo se desvía, no hay forma de detectarlo ni corregirlo.
  - Separar `opening_balance` (inmutable) de `current_balance` (derivado).

---

## Backlog priorizado (después del MVP)

| Prioridad | Feature | Nota |
|---|---|---|
| Alta | **Automatización de ingresos/gastos recurrentes** | Feature de retención del mes 2, no de adquisición del día 1. Requiere scheduler (ya existirá tras Fase 12). |
| Alta | **Editor de categorías personalizable** | Segunda semana post-lanzamiento. El código ya existe, solo está oculto. |
| Alta | **Sinking funds** (gastos distribuidos en cuotas mensuales virtuales) | Diferenciador potencial para v1.1. Validado por YNAB. Feature de usuario avanzado. |
| Media | **Registro por nota de voz con IA** | v1.2. Feature de marketing / efecto "wow". Depende de la captura por nombre (Fase 14). |
| Media | **Google OAuth** | Aplazado en la decisión del 2026-08-22. |
| Media | **Filtros de fecha y categoría en dashboard** | Iteración 2, cuando haya datos de uso reales que lo justifiquen. |
| Media | **App nativa iOS/Android** | Solo si se necesitan widgets de pantalla de inicio, push nativas o Face ID. La PWA de Fase 11 cubre el resto. |
| Baja | **Multi-moneda ampliado** (tasas de cambio) | El modelo ya soporta agrupación por moneda; la conversión no está y no se necesita. |
| Baja | **Sincronización offline** | Las columnas `updated_at` de Fase 8 la dejan preparada. |

---

## Fuera de scope (no hacer)

- ~~**Tracking de inversiones con vinculación de brokers**~~ — Es un producto distinto. Diluye la propuesta de valor. Como mucho, un campo manual de "patrimonio neto" en el futuro.
- ~~**Tarjetas de crédito avanzadas** (puntos, millas, intereses de mora, cuotas)~~ — Cada banco calcula distinto y las reglas cambian constantemente. Pesadilla operativa sin equipo dedicado.
- ~~**Temas visuales dinámicos**~~ — El modo claro/oscuro actual es suficiente. Ya implementado.
- ~~**Multi-idioma / i18n**~~ — Lanzamiento en español. Revisar solo si hay plan de mercados fuera de LATAM.
- ~~**CI/CD**~~ — Revisar cuando haya usuarios reales en producción.

### Decisiones revertidas el 2026-08-22

Estas estaban "fuera de scope" bajo el supuesto de un solo usuario. Ese supuesto ya no aplica:

| Antes | Ahora | Razón |
|---|---|---|
| ~~Alembic~~ | **Fase 7** | Con usuarios reales no puedes restaurar la DB a mano. |
| ~~Testing automatizado~~ | **Fase 7** (alcance acotado) | La lógica que mueve dinero de terceros no puede no tener pruebas. |
| ~~Versionado de API~~ | **Fase 7** | Sin él no puedes evolucionar sin romper clientes externos. |

---

## Historial — Completado

| Fecha | Item |
|-------|------|
| 2026-07-06 | **Fase 0** — Security wins: SECRET_KEY regenerada, EmailStr, email normalization, model_dump(), CORS en env var |
| 2026-07-06 | **Fase 1** — Factoría de formateo + AppConfigProvider: columnas preferred_currency/locale, endpoint preferences, formatters.ts, useUserPreferences, migración formatCurrency/formatDate |
| 2026-07-06 | **Fase 2** — Tokenización tema CSS: paleta light/dark con custom properties, ThemeToggle, hardcoded colors eliminados de gráficos |
| 2026-07-08 | **Fase 3** — Columna currency en DB: modelos Account/Transaction/Budget, schemas, types, UI selector + display multi-moneda |
| 2026-07-08 | Seed data: script `backend/app/core/seed.py` con usuario test, 3 cuentas, 45 transacciones, 6 presupuestos |
| 2026-07-08 | Post-auditoría: migración `.dict()` → `model_dump()`, eliminación hex hardcodeados, corrección categories |
| 2026-07-09 | Feature Multi-Tema: preferred_theme en backend, ThemeToggle sincronizado, transiciones CSS, WCAG AA verificado |
| 2026-07-10 | Feature FAB + Transacción Rápida: FloatingActionButton, FabManager, QuickTransactionModal, integrado en dashboard layout |
| 2026-07-10 | **Fase 1** — Fixes inmediatos: CSS bug dashboard, finanzas.db excluido de git, rate limiting verificado y documentado |
| 2026-07-10 | **Fase 3** — Documentación actualizada: keys preferencias corregidas, errores API, ARCHITECTURE con RefreshToken y migraciones |
| 2026-07-11 | **Fase 4A** — Tailscale: CORS regex, uvicorn 0.0.0.0, WSL2 tailscale IP, login verificado |
| 2026-07-11 | **Fase 4B** — Docker: Dockerfiles, docker-compose.yml (postgres + backend + frontend), .dockerignore, seed en PostgreSQL |
| 2026-07-14 | **Fase 6 Quick Wins** — Fix multi-moneda en `/summary`, sanitización de errores, headers de seguridad, README raíz, edición de transacciones, cuentas destacadas, iconos de categorías, ruff + prettier |
| 2026-07-14 | **Fase 6 Responsive** — Dashboard, listados, formularios, modales y sidebar adaptados a móvil; estandarización de botones |

### Pendientes heredados de fases anteriores

- [ ] Acceder y verificar el flujo completo desde celular vía Tailscale (Fase 4A).
- [ ] Seed automático tras el primer startup en Docker (Fase 4B).
- [ ] Script `scripts/deploy.sh` (git pull → docker compose up --build -d) (Fase 4B).
- [ ] Decidir `AccountUpdate.currency` — el schema hereda el campo pero `accounts.py` lo ignora silenciosamente.
- [ ] Extraer custom hooks de queries (`useAccounts`, `useCategories`, `useTransactions`).
- [ ] Migrar JWT de `localStorage` a cookies httpOnly (sube de prioridad al salir de Tailscale).
- [ ] Crear capa `app/services/` y `app/core/exceptions.py`; partir `models.py` y `schemas.py` por dominio.
