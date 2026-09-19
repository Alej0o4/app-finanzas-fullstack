# Changelog — Oikos

> Historial de fases completadas, más reciente primero (formato inspirado en
> [Keep a Changelog](https://keepachangelog.com)). Cada entrada es un resumen — el detalle
> técnico completo, las decisiones numeradas y las verificaciones de cada fase viven en
> `docs/specs/fase_NN_spec.md`.
>
> Para la visión de producto, lo que sigue abierto y el backlog, ver `docs/ROADMAP.md`.

---

## Fase 26 — JWT de `localStorage` a cookies `httpOnly` (2026-09-19)

Retomó el diseño que Fase 25 §25.5 dejó deliberadamente sin ejecutar (decisiones J1–J8):
`login`/`login_google`/`refresh` ahora setean tres cookies de sesión (`access_token` HttpOnly
15 min, `refresh_token` HttpOnly con Path acotado a `/api/v1/auth`, `csrf_token` NO HttpOnly)
además del body `TokenResponse` de siempre (compatibilidad con clientes no-browser sin
cambios); `get_current_user` gana un fallback de cookie detrás del header `Authorization`
(camino primario, sin cambios para API keys `oikos_pat_...`); CSRF vía double-submit cookie
(`app/core/csrf.py`, header `X-CSRF-Token` en toda mutación con cookie de sesión presente).
`frontend/lib/api.ts` deja de leer/escribir `localStorage` y pasa a `withCredentials: true`
(y 7 archivos más que también leían/escribían tokens — login, register, GoogleAuthButton,
Sidebar, settings, useRequireAuth, useUserPreferences, ThemeToggle).

**Decisión de despliegue tomada el mismo día:** producción se consolida en el dominio HTTPS
del Tailscale Funnel como único origen soportado para login por cookie (`COOKIE_SECURE=true`
por default) — el acceso por IP directa de Tailscale queda deprecado para sesión de navegador,
no para API keys (Decisiones B10/F6).

**Dos correcciones hechas en la revisión final, antes de mergear** (no estaban en el spec
original): el Path del cookie `refresh_token` era demasiado angosto
(`/api/v1/auth/refresh`) y nunca llegaba a `POST /auth/logout` — el logout por navegador no
revocaba nada server-side, corregido ampliando el Path a `/api/v1/auth`; y el interceptor de
refresh de `lib/api.ts` entraba en deadlock si el propio refresh devolvía 401 (sesión
realmente expirada) — la versión anterior usaba `axios` crudo para evitar justo esta
recursión, y el cambio a la instancia `api` (necesario para que viajen las cookies) la
reintrodujo sin darse cuenta; corregido con un guard explícito por URL. 251 tests backend
pasando, `tsc`/`eslint`/`prettier` limpios en frontend.

Spec: `docs/specs/fase_26_spec.md`.

---

## Fase 25 — Arquitectura: capa de servicios, tipos compartidos y deuda de tests (2026-09-18)

Pagó deuda de arquitectura señalada por la auditoría del 2026-09-15 (`CODE_REVIEW.md`):
`app/services/ledger.py` (primer módulo real de `app/services/`, extrae el delta contable
copy-pasteado en `crear_transaccion`/`eliminar_transaccion`/`actualizar_transaccion`);
`schemas.py` partido de 462 líneas/48 clases a 12 módulos por dominio bajo `app/schemas/`
(shim de re-exports, cero cambios en imports de routers); capa de excepciones de dominio
(`app/core/exceptions.py`) como piloto acotado en `transactions.py` (4 call sites, no reescritura
de los ~59 `raise HTTPException` restantes); hooks `useAccounts`/`useCategories`/`useTransactions`
en el frontend reemplazando 19 `useQuery` inline. 233 tests backend pasando.

**JWT en `localStorage` → cookies `httpOnly` quedó deliberadamente fuera** — diseño completo
(spec §25.5, decisiones J1–J8) pero diferido a un spec propio por su blast radius sobre todo el
tráfico autenticado y la ausencia total de protección CSRF hoy. Ver `docs/ROADMAP.md`.

Spec: `docs/specs/fase_25_spec.md`.

---

## Fase 24 — UX: fallos silenciosos del flujo principal (2026-09-18)

Cerró el patrón de "falla silenciosa" que la auditoría del 2026-09-15 encontró en el dashboard y
la captura: las 4 queries del dashboard exponen `isError`/`refetch` con botón "Reintentar" por
sección; el formulario inline de ingreso mensual ganó `noValidate` + error de campo + foco al
fallar; `PUT /api/v1/accounts/{id}` ahora sí aplica cambios de `currency` (antes se ignoraban en
silencio), bloqueando con `400` si la cuenta tiene transacciones activas; `category-distribution`
expone `category_icon` (antes solo `BudgetProgress` lo hacía). De paso corrigió un bug ya en
producción: cualquier `PUT` de cuenta que omitiera `highlighted` lo reseteaba a `false`. 228 tests
backend pasando.

Spec: `docs/specs/fase_24_spec.md`.

---

## Fase 23 — Cierre de vulnerabilidad crítica: account takeover vía Google OAuth (2026-09-18) 🔴

Cerró un account-takeover confirmado en la auditoría del 2026-09-15: `login_google` auto-linkeaba
una cuenta existente por email sin invalidar su `password_hash`, así que un atacante podía
pre-registrar el email de una víctima con su propia contraseña y, cuando la víctima hacía login
real con Google, esa contraseña plantada quedaba válida contra `/auth/login`. Fix: al auto-linkear,
`login_google()` anula el `password_hash` existente — pero solo si la cuenta **no estaba
verificada** en el momento del link; una cuenta ya verificada conserva su contraseña sin cambios.
También se agregó logging (no bloqueo) de reasignación cross-usuario en `POST /push/subscribe`.

Bloqueaba las Fases 24 y 25 hasta su cierre. Spec: `docs/specs/fase_23_spec.md`.

---

## Fase 22 — Onboarding moneda-primero, salario editable, claridad de cuentas Google (2026-09-13)

El onboarding pregunta la moneda (COP/USD/EUR, lista acotada en revisión pre-merge por límites del
selector de cuentas existente) **antes** del paso de ingreso mensual, con cascada a la cuenta por
defecto; el salario mensual pasó a editable desde `/settings` (antes solo se fijaba una vez en el
onboarding); `UserResponse` expone `has_password` para distinguir cuentas Google-only en la UI de
borrado de cuenta; "olvidé mi contraseña" en cuentas Google-only se deja funcionar como ya
funcionaba, solo con copy aclaratorio. La selección de categorías dentro del wizard se evaluó y se
descartó — reafirma la Decisión 18.2.1. 218 tests backend pasando.

Spec: `docs/specs/fase_22_spec.md`.

---

## Fase 21 — Configuración de cuenta: moneda principal y baja de cuenta (2026-09-13)

Selector de `preferred_currency` expuesto en `/settings` (el backend ya lo soportaba desde Fase 8).
Baja de cuenta de usuario self-service: `DELETE /api/v1/users/me` con reingreso de contraseña +
rate limit, más un script de management (`delete_user_by_email()`) para limpiar usuarios de prueba
sin exponer un rol admin — el proyecto no tiene concepto de roles y agregarlo solo para esto se
consideró desproporcionado. Cascada de borrado cubre 12 tablas. 200 tests backend pasando.

Spec: `docs/specs/fase_21_spec.md`.

---

## Fase 20 — Correos transaccionales con marca + login social (2026-09-13)

`render_email_html()` en `app/core/email.py` — plantilla con marca Oikos (header, botón, link de
respaldo en texto plano), compartida por verificación y reset de contraseña; antes eran un `<p>`
con un link pelado, indistinguible de phishing. Placeholders genéricos en formularios de auth
(reemplazan el nombre real del dueño del proyecto). Login con Google (`POST /api/v1/auth/google`,
Google Identity Services sin redirect/client-secret, `google-auth` lib) — auto-linkea una cuenta
con contraseña existente por email; `User.password_hash` pasa a `nullable=True` + columna
`google_id` (migración `5b79ad1d27e4`). El auto-link sin invalidar contraseña fue el vector cerrado
después en Fase 23. Apple sign-in evaluado y descartado (Developer Program pago, complejidad
desproporcionada para un proyecto web-only).

**Nota operativa que sigue vigente:** el botón de Google solo aparece con `GOOGLE_CLIENT_ID` /
`NEXT_PUBLIC_GOOGLE_CLIENT_ID` configurados por entorno — el plumbing de Docker se corrigió el
mismo día, pero las credenciales reales de Google Cloud Console para el despliegue siguen sin
generarse (ver `CLAUDE.md`).

Spec: `docs/specs/fase_20_spec.md`.

---

## Parada — Correcciones de UX post-Fase 19 (2026-09-12)

Cuatro fricciones de uso real desde celular sobre lo entregado en Fases 17–19: categorías ocultas
sin señal visual en `/categories` (ahora se filtran del grid con animación y se agrupan bajo
"Mostrar ocultas"); `/analytics` sin selector de cuenta (agregado, persistido en URL, con aviso
explícito de qué cuentas en otra moneda quedan excluidas de "Todas las cuentas"); FABs fijos
tapando contenido en móvil (se reserva el espacio en el layout en vez de mover los botones); inputs
de fecha desbordando su tarjeta en Safari/iOS (`appearance: none` + `box-sizing: border-box`).
190 tests backend pasando.

---

## Fase 19 — Fricción post-onboarding y analítica de ingreso (2026-09-12)

El login solo redirige a `/capture` para usuarios sin historial real (`has_transaction_history` en
`GET /users/me`, query `LIMIT 2`); antes redirigía siempre, generando la fricción que la Decisión
10.1.4 de Fase 10 ya anticipaba como riesgo. La card "Balance del mes" se fusionó con
Ingresos/Gastos en una sola `SummaryCard` con `secondaryStats` (antes eran 3 tarjetas con las
mismas 3 cifras). Nueva métrica "% del ingreso por categoría" en Analítica, complementaria a la
dona de gastos. 177 tests backend pasando.

Spec: `docs/specs/fase_19_spec.md`.

---

## Fase 18 — Categorías personalizables (2026-09-12)

Amplió el pool de categorías default (Mercado, Pareja, Regalos, Restaurantes, Gastos hormiga,
Uber, Carro, Transporte público) sin reemplazar las genéricas ya existentes. Selección de
categorías durante el registro con un set base pre-marcado. Concepto nuevo "ocultas para mí"
(`HiddenCategory`, por usuario, no afecta el catálogo compartido). Activó el editor de categorías
personalizadas ya presente en el backend desde antes de Fase 11 pero apagado en frontend
(`CUSTOM_CATEGORY_EDITING_ENABLED`).

---

## Fase 17 — Análisis por cuenta y presupuestos multi-moneda (2026-09-12)

`accounts/[id]` ganó los mismos componentes de gráficos del dashboard general
(`CategoryDonutChart`, `CategoryBreakdownBars`, `BudgetRing`), filtrados a esa cuenta — el
dashboard principal se mantiene agregando todas las cuentas, sin selector. Formulario de
presupuestos gana selector de moneda (antes `Budget.currency` nunca se exponía y todo presupuesto
se creaba en COP por default).

---

## Fase 16 — Automatizaciones y preparación móvil (post-MVP) (2026-09-06)

API keys personales revocables (`oikos_pat_...`) — habilitan Atajos de iOS sin el flujo OAuth2
password. Endpoint de captura rápida por nombre de categoría (`category: "Alimentación"` en vez de
`category_id`). Codegen de tipos TypeScript desde el schema OpenAPI. Reconciliación de saldos:
separación de `opening_balance` (inmutable) y `current_balance` (derivado), con operación de
recálculo. 154 tests backend pasando.

Spec: `docs/specs/fase_16_spec.md`.

---

## Parada — Correcciones de UX post-pivote (2026-09-06)

Cinco fricciones de uso real tras el pivote a producto público: método de pago derivado
automáticamente del tipo de cuenta en vez de un selector manual independiente; bug de filtros en
Transacciones que vaciaba la lista al aplicar cualquier preset de fecha (`useQueryParamsBatch`
nuevo, un solo `router.replace` por lote); selector de período único en Analítica (reemplaza dos
selectores independientes sin señal visual de su alcance distinto) más un bug de zona horaria en
los límites de mes/año; íconos de sidebar colapsada más grandes; botones "agregar" deduplicados
con el FAB global.

---

## Fase 15 — Onboarding de 3 minutos (2026-09-06)

Registro sin fricción (solo email) → pregunta de ingreso mensual → primer gasto guiado → "aha
moment" mostrando el impacto en el dashboard. Fase 100% frontend: encadena endpoints ya
existentes, ningún archivo de `backend/` tocado. Correcciones el mismo día tras probar el flujo
real en navegador: fechas naive interpretadas como UTC (bug preexistente desde Fase 11/12, visible
siempre en onboarding), el ingreso declarado ahora siembra una transacción de ingreso real (antes
solo alimentaba el cálculo, dejando "Ingresos del Mes" en $0), cuenta por defecto renombrada de
"Efectivo" a "Cuenta principal", desborde de íconos en el footer del sidebar con nombres largos.
122 tests backend pasando.

Spec: `docs/specs/fase_15_spec.md`.

---

## Fase 14 — Resumen semanal automático (2026-09-06)

`BackgroundScheduler` in-process (APScheduler) con `CronTrigger` lunes 07:00 `America/Bogota`.
Cálculo del resumen (total gastado, categoría principal, delta vs. semana anterior), enviado
siempre incluso con $0. Preferencia de usuario opt-out (`User.weekly_summary_enabled`) y primera
página de Ajustes (`/settings`) del frontend.

Spec: `docs/specs/fase_14_spec.md`.

---

## Fase 13 — Presupuestos con alertas + infraestructura de notificaciones (2026-09-06)

PWA instalable (manifest + `sw.js` manual, sin `next-pwa`) como prerrequisito de push. Push web
completo (VAPID, tabla `push_subscriptions`, `pywebpush`, limpieza de suscripciones muertas).
Motor de evaluación de presupuestos con umbrales 80%/100%, idempotente por `(budget_id, type)`.
`BudgetRing` realineado a esos mismos cortes. Bandeja de avisos in-app como fallback (campana con
badge, poll 60s) — más borrado de notificaciones (`DELETE /notifications/{id}` y `/read`),
encontrado como gap real en pruebas manuales el mismo día.

Spec: `docs/specs/fase_13_spec.md`.

---

## Fase 12 — Pulido visual y omisiones estratégicas (2026-09-05)

URL-sync de filtros (Transacciones/Analítica) vía `useQueryParamState`; jerarquía visual entre
tarjetas (prop `elevated`); sombras tintadas con el color de fondo/acento; loading unificado con
`Skeleton` en 7 archivos; favicon de marca + limpieza de assets de scaffold; página 404 propia;
skip-link; validación de formularios por campo con foco en el primer error (patrón reusado en
todas las fases siguientes); `tabular-nums` en cifras; enlaces legales en el shell autenticado.
91 tests backend pasando.

Spec: `docs/specs/fase_12_spec.md`.

---

## Fase 11 — Dashboard de flujo mensual (2026-08-23)

El "aha moment" central del pivote. Corrigió los 3 bugs multi-moneda restantes (presupuestos,
cashflow, distribución por categoría sumaban montos de distintas monedas sin filtrar). Reordenó la
jerarquía del dashboard: balance del mes (ingreso − gasto) pasa a titular, `Balance Total` de
cuentas se demueve a vista secundaria. Desglose por categoría en barras horizontales. Ocultó solo
los controles de creación/edición de categorías personalizadas (no la ruta completa). 91 tests
backend pasando.

Spec: `docs/specs/fase_11_spec.md`.

---

## Fase 10 — Captura en 3 toques (2026-08-23)

`/capture` como ruta principal post-login. Formulario rediseñado a 3 interacciones: monto (teclado
numérico) → categoría (íconos grandes) → guardar, con fecha/cuenta precargadas. Tag de método de
pago. Idempotencia real en `POST /transactions` (`Idempotency-Key`, tabla `idempotency_keys`,
`UNIQUE(user_id, key)`). Corrigió el fallo silencioso del submit (antes: `return` sin ningún aviso
si faltaba un campo). 75 tests backend pasando.

Spec: `docs/specs/fase_10_spec.md`.

---

## Fase 9 — Accesibilidad y componentes base de UI (2026-08-23)

`focus-visible` en vez de `focus`; `<label>` asociado a su control (`htmlFor`/`id`); `aria-label`
en ~21 botones icon-only; cierre por Escape + `overscroll-behavior: contain` en modales;
animaciones de entrada reparadas (keyframes propios, no `tailwindcss-animate`); `transition-all`
reemplazado por propiedades explícitas; `prefers-reduced-motion`; `autocomplete` en formularios de
auth; `aria-live="polite"` en mensajes de error/éxito; estado `active:` en botones y tarjetas.

Spec: `docs/specs/fase_09_spec.md`.

---

## Fase 8 — Modelo de datos del nuevo MVP (2026-08-23)

`User.monthly_income`; `Transaction.payment_method` (cash/card/transfer); presupuestos recurrentes
(generación perezosa por período — sin esto, el presupuesto de enero desaparecía en febrero);
categorías default ampliadas a 11; cuenta por defecto auto-creada al registrarse (antes el botón
de captura hacía `return` en silencio con 0 cuentas); `updated_at` + borrado lógico en todas las
entidades.

Spec: `docs/specs/fase_08_spec.md`.

---

## Fase 7 — Cimientos multi-usuario (2026-08-22, con un ítem diferido a propósito)

La fase bisagra del pivote a multi-usuario. Adoptó Alembic (retira `create_all()` y los
`_ensure_*_column()` ad-hoc); índices en `transactions`; constraint de unicidad en `budgets`;
recuperación de contraseña (token de un solo uso) y verificación de email; política de
contraseñas; rate limiting en registro/recuperación; JWT bajado a 15 min de TTL; script de backup
con rotación; secretos fuera de `docker-compose.yml` (sin default silencioso); logging
estructurado; API versionada bajo `/api/v1/`; primeros tests automatizados del módulo contable y
de autenticación.

Estas tres decisiones estaban marcadas "fuera de scope" bajo el supuesto de un solo usuario y se
revirtieron el mismo día del pivote: **Alembic**, **testing automatizado** y **versionado de
API** — las tres pasaron a ejecutarse en esta fase.

**Rate limiting distribuido quedó diferido a propósito** (no implementado): `slowapi` en memoria
no funciona con múltiples workers, pero el backend sigue corriendo en un solo worker sin réplicas
— el problema que resuelve no existe todavía. Diseño listo (Redis + `storage_uri`) para cuando el
despliegue pase a `--workers > 1`.

Spec: `docs/specs/fase_07_spec.md`.

---

## Historial previo (pre-Fase 7)

| Fecha | Item |
|-------|------|
| 2026-07-06 | **Fase 0** — Security wins: SECRET_KEY regenerada, EmailStr, email normalization, `model_dump()`, CORS en env var |
| 2026-07-06 | **Fase 1** — Factoría de formateo + AppConfigProvider: columnas `preferred_currency`/`locale`, endpoint preferences, formatters.ts, `useUserPreferences`, migración `formatCurrency`/`formatDate` |
| 2026-07-06 | **Fase 2** — Tokenización tema CSS: paleta light/dark con custom properties, ThemeToggle, hardcoded colors eliminados de gráficos |
| 2026-07-08 | **Fase 3** — Columna `currency` en DB: modelos Account/Transaction/Budget, schemas, types, UI selector + display multi-moneda |
| 2026-07-08 | Seed data: `backend/app/core/seed.py` con usuario test, 3 cuentas, 45 transacciones, 6 presupuestos |
| 2026-07-08 | Post-auditoría: migración `.dict()` → `model_dump()`, eliminación de hex hardcodeados, corrección de categories |
| 2026-07-09 | Feature Multi-Tema: `preferred_theme` en backend, ThemeToggle sincronizado, transiciones CSS, WCAG AA verificado |
| 2026-07-10 | Feature FAB + Transacción Rápida: `FloatingActionButton`, `FabManager`, `QuickTransactionModal`, integrado en dashboard layout |
| 2026-07-10 | **Fase 1** — Fixes inmediatos: CSS bug dashboard, `finanzas.db` excluido de git, rate limiting verificado y documentado |
| 2026-07-10 | **Fase 3** — Documentación actualizada: keys de preferencias corregidas, errores API, ARCHITECTURE con RefreshToken y migraciones |
| 2026-07-11 | **Fase 4A** — Tailscale: CORS regex, uvicorn `0.0.0.0`, WSL2 tailscale IP, login verificado |
| 2026-07-11 | **Fase 4B** — Docker: Dockerfiles, `docker-compose.yml` (postgres + backend + frontend), `.dockerignore`, seed en PostgreSQL |
| 2026-07-14 | **Fase 6 Quick Wins** — Fix multi-moneda en `/summary`, sanitización de errores, headers de seguridad, README raíz, edición de transacciones, cuentas destacadas, iconos de categorías, ruff + prettier |
| 2026-07-14 | **Fase 6 Responsive** — Dashboard, listados, formularios, modales y sidebar adaptados a móvil; estandarización de botones |

---

## Deuda de accesibilidad heredada, resuelta

- **Modal de edición manual de `transactions/page.tsx` sin `focus-visible`/`htmlFor`/`id`** (gap de
  Fase 9, quedó fuera de alcance a propósito porque el ROADMAP nombraba literalmente solo
  `Button`/`Input`/`Select`) — resuelto en Fase 12 §12.8.3 al migrar el modal a los componentes
  compartidos `Input`/`Select`.
