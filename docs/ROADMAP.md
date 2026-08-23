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

El MVP se redefine alrededor de **cinco componentes funcionales** (ver Fases 7–14).

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

- [x] **Adoptar Alembic** — reemplazar `create_all()` + los `_ensure_*_column()` ad-hoc de `main.py` — 1d *(2026-08-22, ver `docs/specs/fase_07_spec.md` §1.1)*
  - Generar migración inicial desde el esquema actual.
  - Retirar `_ensure_user_preference_columns()`, `_ensure_category_icon_column()`, `_ensure_account_highlighted_column()`.
  - Retirar la migración legacy de categorías `"Otro (Ingreso)"` de `seed_default_categories()` (corre en cada arranque).

- [x] **Bug latente: `preferred_theme` nunca se agrega en DB existentes** — 1h *(2026-08-22, resuelto por la migración baseline de Alembic)*
  - `_ensure_user_preference_columns()` agrega `preferred_currency` y `preferred_locale` pero no `preferred_theme`.
  - Se resuelve con la migración inicial de Alembic.

- [x] **Índices en `transactions`** — `user_id`, `account_id`, `category_id`, `date` — 2h *(2026-08-22)*
  - Todas las queries filtran por `user_id + date`; hoy hacen table scan.
  - Índice compuesto `(user_id, date)` como mínimo.

- [x] **Constraint `UNIQUE(user_id, category_id, month, year)` en `budgets`** — 1h *(2026-08-22)*
  - Hoy se valida solo en Python → dos requests concurrentes crean duplicados.

- [x] **`nullable=False` en FKs de `transactions`** (`user_id`, `account_id`, `category_id`) — 1h *(2026-08-22)*

### Ciclo de vida de cuenta

- [x] **Recuperación de contraseña** (token de un solo uso + expiración) — 1d *(2026-08-22, ver `docs/specs/fase_07_spec.md` §2.1)*
  - **Bloqueante absoluto.** Sin esto, un usuario que olvida su clave pierde la cuenta.
  - Requiere servicio de correo transaccional (ver Fase 13 — se puede adelantar aquí).

- [x] **Verificación de email en registro** — 1d *(2026-08-22, ver §2.2 — no bloquea el login)*
  - Evita cuentas basura y valida el canal de recuperación.

- [x] **Política de contraseñas** más allá de `min_length=8` — 2h *(2026-08-22, ver §2.3)*

- [x] **Rate limiting en registro y recuperación** (hoy solo hay en login) — 2h *(2026-08-22, ver §2.4)*

- [x] **Invalidación del access token en logout** — 4h *(2026-08-22, ver §2.5 — TTL bajado a 15 min)*
  - Hoy el JWT sigue válido hasta 60 min después de cerrar sesión.
  - Opción simple: bajar TTL a 15 min y apoyarse en el refresh token.

- [ ] **Rate limiting distribuido** — `slowapi` en memoria no funciona con múltiples workers — 4h
  - **Diferido a propósito** (2026-08-22, ver `docs/specs/fase_07_spec.md` §2.6.1): hoy el
    backend corre en un solo worker sin réplicas, así que el problema que esta tarea resuelve
    no existe todavía. Diseño listo (Redis + `storage_uri`), implementar cuando el despliegue
    pase a `--workers > 1` o más de una réplica.

### Operación y seguridad

- [x] **Script `scripts/backup.sh`** — `pg_dump` con rotación de 7 días — 1d *(2026-08-22)*
  - Con datos de terceros esto pasa de molesto a inaceptable.

- [x] **Secretos fuera de `docker-compose.yml`** — 4h *(2026-08-22)*
  - Hoy: `POSTGRES_PASSWORD: oikos_secret` hardcodeado y `SECRET_KEY:-changeme_in_production` como default silencioso.
  - El default silencioso debe fallar el arranque, no continuar.

- [x] **Retirar el regex CORS `100.x.x.x`** en despliegue público — 1h *(2026-08-22)*

- [x] **Logging estructurado** — sin esto no puedes diagnosticar el reporte de un usuario — 1d *(2026-08-22)*

### Versionado y pruebas

- [x] **Versionar la API bajo `/api/v1/`** — 2h *(2026-08-22)*
  - Barato ahora, carísimo después. Todas las fases siguientes construyen sobre las rutas versionadas.

- [x] **Tests del módulo contable y de autenticación** (pytest + httpx) — 2d *(2026-08-22)*
  - No cobertura completa: solo la lógica que mueve dinero y la que da acceso.
  - Es el código de mayor riesgo del proyecto y hoy no tiene ninguna prueba.

---

## Fase 8 — Modelo de datos del nuevo MVP ✅ completa (2026-08-23)

**Objetivo:** las columnas y entidades que los 5 componentes necesitan. Depende de Fase 7 (Alembic).

> Implementación completa y auditada el 2026-08-23 — ver `docs/specs/fase_08_spec.md` para el
> desglose técnico y las decisiones de diseño numeradas.

- [x] **`User.monthly_income`** (`Numeric(14,2)`, nullable) — 2h *(2026-08-23, ver `docs/specs/fase_08_spec.md` §1)*
  - Lo captura el onboarding; activa el balance de flujo del dashboard.

- [x] **`Transaction.payment_method`** (nullable: `cash` / `card` / `transfer`) — 3h *(2026-08-23, ver §2)*
  - Tag ligero, **no** un módulo de configuración de métodos de pago.
  - Distinto de `Account.type`: el método es de la transacción, no de la cuenta.

- [x] **Presupuestos recurrentes** — 1d *(2026-08-23, ver §3 — generación perezosa por período, Decisión 3.1)*
  - 🔴 **Bloqueador de retención.** Hoy `Budget` exige `month`+`year` fijos: el presupuesto de enero
    desaparece en febrero y el dashboard queda vacío, rompiendo el loop registro → feedback → ajuste.
  - Opción: `is_recurring` + resolución del periodo en consulta, o generación perezosa del mes actual.

- [x] **Categorías default ampliadas a 8–10** — 3h *(2026-08-23, ver §4 — quedaron 11, ver Decisión 4.1)*
  - Agregar: **Vivienda**, **Salud**, **Educación**.
  - Renombrar `Ocio` → `Entretenimiento`.
  - Revisar categorías de ingreso (hoy solo existe `Salario`).

- [x] **Cuenta por defecto al registrarse** — 3h *(2026-08-23, ver §5)*
  - 🔴 **Bloqueador de onboarding.** Un usuario nuevo tiene 0 cuentas, `account_id` es obligatorio
    y `QuickTransactionModal` hace `return` en silencio: el botón "Registrar" no hace nada,
    sin error ni aviso.
  - Auto-crear una cuenta "Efectivo" en el registro.

- [x] **`updated_at` + borrado lógico en todas las entidades** — 1d *(2026-08-23, ver §6)*
  - Trivial ahora; migración con datos reales después.
  - Habilita sincronización offline si algún día hay app nativa.

---

## Fase 9 — Accesibilidad y componentes base de UI ✅ completa (2026-08-23)

**Objetivo:** cerrar los defectos de accesibilidad y los hábitos repetidos en `Button`, `Input`,
`Select` y `ModalShell` antes de que Fase 10 (captura) y Fase 11 (dashboard) construyan las
pantallas nuevas del MVP sobre estos mismos componentes. Corregir la base ahora evita heredar
los mismos bugs en la UI nueva.

> Implementación completa el 2026-08-23 — ver `docs/specs/fase_09_spec.md` para el desglose
> técnico y las decisiones de diseño numeradas. Revisada por Claude Code el mismo día
> (build + lint limpios, diff verificado contra la spec ítem por ítem); queda un gap de alcance
> documentado en "Pendientes heredados de fases anteriores" más abajo.

> Hallazgos de la auditoría de diseño del 2026-08-23 (Web Interface Guidelines + revisión visual
> con la skill `redesign-existing-projects`). Detalle completo en la conversación de esa fecha.

- [x] **`focus-visible` en vez de `focus` en `Button`/`Input`/`Select`** — 2h *(2026-08-23, ver `docs/specs/fase_09_spec.md` §9.1)*
  - Hoy el anillo de foco se activa también al hacer click con mouse, no solo con teclado.

- [x] **Asociar `<label>` con su control (`htmlFor`/`id`)** en `Input.tsx` y `Select.tsx` — 3h *(2026-08-23, ver §9.2)*
  - El label no es clickeable ni queda anunciado por un lector de pantalla al enfocar el campo.

- [x] **`aria-label` en todos los botones icon-only** — 1d *(2026-08-23, ver §9.3 — 21 ubicaciones en 9 archivos)*
  - Repetido en ~20 lugares: toggle del sidebar, logout, tema, FAB, cerrar modal, y las acciones
    de editar/eliminar/destacar en cuentas, categorías, presupuestos y transacciones.
  - `ChartControlsPopover.tsx:32` ya lo hace bien — usar como plantilla.

- [x] **Cierre por Escape + `overscroll-behavior: contain`** en `ModalShell` y `ConfirmDialog` — 3h *(2026-08-23, ver §9.4 — hook compartido `lib/hooks/useEscapeToClose.ts`, ambos componentes eran implementaciones independientes)*

- [x] **Arreglar la animación de entrada rota de `ModalShell`/`FloatingActionButton`** — 2h *(2026-08-23, ver §9.5 — `--animate-*` + `@keyframes` propios en `globals.css`, no se instaló `tailwindcss-animate` por ser incompatible con Tailwind v4)*
  - Usan clases `animate-in fade-in slide-in-from-bottom-2`, pero `tailwindcss-animate` no está
    instalado y no hay keyframes propios en `globals.css` — hoy no animan nada pese a que el
    código lo sugiere.

- [x] **Reemplazar `transition-all` por propiedades explícitas** — 3h *(2026-08-23, ver §9.6)*
  - Repetido en `Sidebar`, `Button`, `FloatingActionButton`, `(dashboard)/layout.tsx` y los
    formularios de edición manual.

- [x] **`prefers-reduced-motion`** — 4h *(2026-08-23, ver §9.7)*
  - No existe en ningún punto del proyecto pese a `animate-pulse`, `animate-spin`, `hover:scale`
    y la transición global en `*` de `globals.css`.

- [x] **`autocomplete` en los formularios de autenticación** — 2h *(2026-08-23, ver §9.8)*
  - Login, registro, forgot/reset password sin `autocomplete="email"|"current-password"|"new-password"`.

- [x] **`aria-live="polite"` en los mensajes de error/éxito** de los 4 formularios de auth — 2h *(2026-08-23, ver §9.9)*

- [x] **Estado `active:` (pressed) en botones y tarjetas clicables** — 3h *(2026-08-23, ver §9.10)*
  - Hay `hover:` en casi todo pero ningún feedback de "presionado" en toda la app.

---

## Fase 10 — Captura en 3 toques ✅ completa (2026-08-23)

**Objetivo:** que registrar un gasto tome menos de 8 segundos. Es el corazón del producto.

> Implementación completa el 2026-08-23 — ver `docs/specs/fase_10_spec.md` para el desglose
> técnico y las decisiones de diseño numeradas. Revisada por Claude Code el mismo día (pytest
> backend 75 passed/1 xfailed, `pnpm lint` y `pnpm build` limpios, diff verificado contra la spec
> ítem por ítem, incluyendo la migración Alembic y los docs cruzados de contrato de API).

- [x] **Pantalla de captura como ruta principal** — 2d *(2026-08-23, ver `docs/specs/fase_10_spec.md` §10.1 — ruta nueva `/capture`, `/` sigue siendo el dashboard)*
  - Hoy la entrada es el dashboard y la captura es un modal encima.
  - El MVP invierte esto: captura primero, dashboard después de guardar.
  - ⚠️ Decisión 10.1.4 (documentada como riesgo, no como certeza): el login redirige a
    `/capture` en *todo* inicio de sesión, no solo el primero — un usuario recurrente que solo
    quiere consultar su saldo ve la pantalla de captura primero, con un toque extra ("Ver
    dashboard") para saltarla. Es la lectura literal del ROADMAP; validar con datos de uso reales
    una vez haya usuarios, y reconsiderar si genera fricción medible.

- [x] **Rediseño del formulario a 3 interacciones** — 2d *(2026-08-23, ver §10.2 — `TransactionCaptureForm` compartido entre `/capture` y `QuickTransactionModal`)*
  - Hoy `QuickTransactionModal` pide **6 campos** (tipo, valor, cuenta, categoría, fecha, descripción)
    con dos `<select>` nativos.
  - Objetivo: monto (teclado numérico) → categoría (íconos grandes, no dropdown) → guardar.
  - Fecha = hoy por defecto, sin mostrar. Descripción oculta tras "más opciones".
  - Cuenta preseleccionada; el selector solo aparece si el usuario tiene más de una.
  - Fecha eliminada del payload por completo (no solo oculta) — el backend la puebla vía
    `server_default`. Grid de categorías con `<input type="radio">` nativos ocultos, no ARIA
    manual — hereda foco/anuncio del navegador gratis.

- [x] **Tag de método de pago** en la captura — 4h *(2026-08-23, ver §10.3 — 100% frontend, el backend ya lo soportaba de punta a punta desde Fase 8)*

- [x] **Idempotencia (`Idempotency-Key`)** en `POST /transactions` — 1d *(2026-08-23, ver §10.4 — tabla `idempotency_keys`, migración `f2727c013363`)*
  - Un reintento por mala señal hoy crea una transacción duplicada y descuadra el saldo.
  - Replay con mismo payload devuelve la transacción original sin duplicar saldo; payload
    distinto con la misma clave → `409`. Carrera resuelta por `UNIQUE(user_id, key)` +
    `IntegrityError`. Sin TTL/limpieza (diferido a propósito, mismo criterio que el rate
    limiting distribuido de Fase 7 — no hay scheduler hasta Fase 14).

- [x] **Corregir el fallo silencioso del submit** — 2h *(2026-08-23, ver §10.5 — toast por campo faltante + foco al campo)*
  - `if (!effectiveAccountId || !categoryId || !amount) return;` no da ninguna señal al usuario.

---

## Fase 11 — Dashboard de flujo mensual

**Objetivo:** el "aha moment" — que el usuario vea su dinero graficado lo antes posible.

> Reevaluada el 2026-08-23 (ver conversación de esa fecha): la redacción original proponía sacar
> Analítica y el editor de Categorías del sidebar ("detrás del menú"), asumiendo una fricción de
> navegación no validada con usuarios reales (el pivote a producto público es de un día antes, y
> el sidebar actual son 6 ítems, no un menú saturado). Una auditoría del código mostró que el
> objetivo real — que el dashboard no se sature de gráficos de analítica — ya estaba cumplido:
> `CashflowChart`, `ChartControlsPopover` y `CategoryDonutChart` viven únicamente en `/analytics`
> y nunca tocaron el dashboard. Se redujo el alcance de "podar" a lo que sí tiene justificación
> (categorías curadas sin editor en v1, ver Fase 8) y se aplica el mismo criterio que la Decisión
> 10.1.4 de Fase 10: no remover una ruta ya construida sin datos de uso que lo respalden.

- [ ] **Corregir los 3 bugs multi-moneda restantes** — 1d
  - Se adelanta al inicio de la fase: es corrección pura, no depende de ninguna decisión de
    diseño pendiente y se puede enviar de forma independiente y segura.
  - `budgets-progress` suma gastos **sin filtrar por moneda** y los compara contra `Budget.currency`.
  - `cashflow-series` suma todas las monedas en una sola serie.
  - `category-distribution` mezcla monedas en los totales por categoría.
  - Mismo defecto que ya se corrigió en `/summary` en 2026-07-14.

- [ ] **`actualizar_transaccion` no actualiza `currency`** — 2h
  - Mover una transacción de una cuenta COP a una USD la deja con `currency="COP"`.

- [ ] **Reordenar la jerarquía de las summary cards del dashboard** — 4h
  - No es un reemplazo: el dashboard ya muestra `Balance Total`, `Ingresos del Mes` y `Gastos del
    Mes` como 3 cards lado a lado. Se agrega el cálculo de **balance del mes** (ingreso mensual −
    gastos del mes) y se le da prioridad visual; `Balance Total` (suma de saldos de cuentas) se
    **demueve, no se elimina** — pasa a la vista secundaria de cuentas (ver abajo).

- [ ] **Desglose por categoría en barras horizontales**, ordenadas de mayor a menor — 1d
  - Aditivo, no reemplazo: el dashboard hoy no tiene ningún desglose por categoría (los Budget
    Rings son otra cosa). Reusa el endpoint `category-distribution` ya existente.
  - `CategoryDonutChart` se queda intacto en `/analytics` — dona y barras sirven audiencias
    distintas (exploración detallada vs. vistazo rápido); no hace falta que una reemplace a la otra.

- [ ] **Vista secundaria de saldos de cuentas** — 4h
  - Decisión 2026-08-22: los saldos siguen accesibles, solo dejan de ser el dato principal.
  - La página `accounts/` ya cubre esto — la tarea real es mover ahí la card `Balance Total` que
    sale del dashboard, no construir nada nuevo.

- [ ] **Ocultar solo los controles de creación/edición de categorías personalizadas** — 4h
  - Alcance reducido respecto a la versión original (que sacaba toda la ruta `categories/` del
    sidebar). Consistente con Fase 8 (categorías curadas, sin editor en v1): se ocultan los
    botones de crear/editar categoría, pero la ruta se queda en el sidebar y la lista sigue
    visible, para que el usuario pueda ver qué categorías existen.
  - El editor completo vuelve en el backlog post-MVP ("Editor de categorías personalizable" — el
    código ya existe, solo queda oculto).

- [ ] **Reagrupar visualmente el sidebar** (primario: Dashboard/Transacciones/Presupuestos —
      secundario: Analítica/Cuentas/Categorías, con separador) — 2h
  - Reemplaza la tarea original "Podar del flujo principal" (que sacaba Analítica del sidebar).
  - Ningún ítem se remueve del menú ni ninguna ruta se oculta — solo se reordena/agrupa para dar
    prioridad visual a los componentes del MVP sin esconder features ya construidas.
  - Revisar remoción real solo si hay datos de uso que la justifiquen — mismo criterio que la
    Decisión 10.1.4 de Fase 10 (no comprometerse con fricción no validada).

---

## Fase 12 — Pulido visual y omisiones estratégicas

**Objetivo:** cerrar lo que quedó de la auditoría de diseño después de que Fase 11 estabilice el
dashboard de flujo — visibilidad de estado en URL, jerarquía visual entre tarjetas, y los huecos
"de producto" (404, favicon, skip-link) que hoy delatan que el proyecto no se terminó de
rematar. Va antes de Fase 15 (onboarding) porque el onboarding es la primera impresión de un
usuario nuevo.

- [ ] **URL-sync de filtros en Transacciones y Analítica** — 1d
  - Hoy los filtros de fecha/cuenta/categoría viven en `useState`/`localStorage`, no en query
    params: se pierden al recargar o al compartir el link.

- [ ] **Diferenciar visualmente las tarjetas** (elevación solo donde comunica jerarquía) — 4h
  - Hoy toda tarjeta usa el mismo patrón `border + shadow-sm + bg-surface` sin distinción entre
    la tarjeta de saldo destacado y una fila de lista.

- [ ] **Tintar las sombras restantes con el color de fondo/acento** — 2h
  - Ya hay 2 ejemplos correctos (`shadow-primary/10` en el link activo del sidebar y en el FAB) —
    extender al resto de tarjetas y modales.

- [ ] **Unificar estados de carga** — 4h
  - El dashboard usa `Skeleton` con la forma del contenido; Transacciones, Cuentas, Presupuestos
    y Categorías caen en un `Loader2` genérico.

- [ ] **Favicon de marca + limpieza de assets de scaffold** — 2h
  - `app/favicon.ico` sigue siendo el default de Next.js; `public/` todavía tiene `next.svg`,
    `vercel.svg`, `globe.svg`, `file.svg`, `window.svg` sin usar.

- [ ] **Página 404 propia** (`app/not-found.tsx`) — 3h

- [ ] **Skip-link para navegación por teclado** — 1h

- [ ] **Validación de formularios por campo**, con foco en el primer error al hacer submit — 1d
  - Hoy los formularios solo tienen un banner de error genérico y validación nativa `required`.

- [ ] **`tabular-nums` en cifras** (`SummaryCard`, `BudgetRing`, columnas de montos) — 2h

- [ ] **Enlaces legales (privacidad/términos)** en el shell autenticado — 4h
  - No es solo diseño: el proyecto pivotó a producto público el 2026-08-22, esto ya no es opcional.

- [ ] Opcional, no bloqueante: **evaluar reemplazar Lucide** por otra librería de iconos —
      cambio de ~20 archivos para un beneficio principalmente estético; dejar en backlog salvo
      que sobre tiempo.

---

## Fase 13 — Presupuestos con alertas + infraestructura de notificaciones

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

## Fase 14 — Resumen semanal automático

**Objetivo:** re-engagement pasivo. El usuario recibe valor sin abrir la app.

> El template es barato; **el canal de entrega no**. Hoy no existe scheduler ni servicio de envío.
> Presupuestar como infraestructura, no como detalle.

- [ ] **Scheduler** (APScheduler o cron externo) — 1d
- [ ] **Cálculo del resumen semanal** — total gastado, categoría principal, comparación con la semana anterior — 1d
- [ ] **Envío vía push** + entrada en la bandeja in-app — 1d
- [ ] **Preferencia de usuario para activar/desactivar** el resumen — 4h

---

## Fase 15 — Onboarding de 3 minutos

**Objetivo:** llevar al usuario a ver su primer gráfico lo más rápido posible.
Depende de Fases 8, 10 y 11.

- [ ] **Minuto 0–1: registro sin fricción** — 1d
  - Solo email (decisión 2026-08-22). Sin formularios largos.
  - Una sola pregunta: *"¿Cuál es tu ingreso mensual aproximado?"* → `User.monthly_income`.

- [ ] **Minuto 1–2: primer gasto guiado** — 1d
  - Redirección directa a la captura con instrucción explícita.
  - Requiere la cuenta por defecto de Fase 8.

- [ ] **Minuto 2–3: el "aha moment"** — 1d
  - Redirección al dashboard mostrando el impacto: *"Has gastado X de tu ingreso mensual."*

---

## Fase 16 — Automatizaciones y preparación móvil (post-MVP)

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
| Alta | **Automatización de ingresos/gastos recurrentes** | Feature de retención del mes 2, no de adquisición del día 1. Requiere scheduler (ya existirá tras Fase 14). |
| Alta | **Editor de categorías personalizable** | Segunda semana post-lanzamiento. El código ya existe, solo está oculto. |
| Alta | **Sinking funds** (gastos distribuidos en cuotas mensuales virtuales) | Diferenciador potencial para v1.1. Validado por YNAB. Feature de usuario avanzado. |
| Media | **Registro por nota de voz con IA** | v1.2. Feature de marketing / efecto "wow". Depende de la captura por nombre (Fase 16). |
| Media | **Google OAuth** | Aplazado en la decisión del 2026-08-22. |
| Media | **Filtros de fecha y categoría en dashboard** | Iteración 2, cuando haya datos de uso reales que lo justifiquen. |
| Media | **App nativa iOS/Android** | Solo si se necesitan widgets de pantalla de inicio, push nativas o Face ID. La PWA de Fase 13 cubre el resto. |
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
- [ ] **`focus-visible` y `htmlFor`/`id` en el modal de edición manual de `transactions/page.tsx`** (Fase 9).
  - El modal de editar transacción (líneas ~495-577) usa `<input>`/`<select>` crudos en vez de los
    componentes `Input`/`Select` ya corregidos en Fase 9 (§9.1/§9.2 de `docs/specs/fase_09_spec.md`):
    sus `<label>` siguen sin `htmlFor`, sus controles sin `id`, y el anillo de foco sigue activándose
    con click de mouse (`focus:` en vez de `focus-visible:`).
  - Quedó fuera de alcance a propósito en Fase 9 porque el ROADMAP nombraba literalmente solo
    `Button`/`Input`/`Select` — no un descuido de implementación, ver hallazgo en la revisión de
    código del 2026-08-23. Vale la pena resolverlo migrando ese modal a los componentes `Input`/
    `Select` compartidos (elimina la duplicación de markup a la vez que cierra el gap).
