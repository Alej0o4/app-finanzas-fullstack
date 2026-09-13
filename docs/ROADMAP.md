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

## Fase 11 — Dashboard de flujo mensual ✅ completa (2026-08-23)

**Objetivo:** el "aha moment" — que el usuario vea su dinero graficado lo antes posible.

> Implementación completa el 2026-08-23 — ver `docs/specs/fase_11_spec.md` para el desglose
> técnico y las decisiones de diseño numeradas. Incluye, más allá de lo que el ROADMAP nombraba
> explícitamente: propagación de `BudgetProgress.currency` hasta `BudgetRing` (Decisión 11.1.2),
> control inline de "fijar ingreso mensual" dentro de la card principal (Decisión 11.3.2) y la
> creación de `backend/tests/test_dashboard.py` + `test_accounts.py` (hallazgo 11 del spec).
> Verificación: pytest 91 passed, ruff/lint/build limpios.

> Reevaluada el 2026-08-23 (ver conversación de esa fecha): la redacción original proponía sacar
> Analítica y el editor de Categorías del sidebar ("detrás del menú"), asumiendo una fricción de
> navegación no validada con usuarios reales (el pivote a producto público es de un día antes, y
> el sidebar actual son 6 ítems, no un menú saturado). Una auditoría del código mostró que el
> objetivo real — que el dashboard no se sature de gráficos de analítica — ya estaba cumplido:
> `CashflowChart`, `ChartControlsPopover` y `CategoryDonutChart` viven únicamente en `/analytics`
> y nunca tocaron el dashboard. Se redujo el alcance de "podar" a lo que sí tiene justificación
> (categorías curadas sin editor en v1, ver Fase 8) y se aplica el mismo criterio que la Decisión
> 10.1.4 de Fase 10: no remover una ruta ya construida sin datos de uso que lo respalden.

- [x] **Corregir los 3 bugs multi-moneda restantes** — 1d *(2026-08-23)*
  - Se adelanta al inicio de la fase: es corrección pura, no depende de ninguna decisión de
    diseño pendiente y se puede enviar de forma independiente y segura.
  - `budgets-progress` suma gastos **sin filtrar por moneda** y los compara contra `Budget.currency`.
  - `cashflow-series` suma todas las monedas en una sola serie.
  - `category-distribution` mezcla monedas en los totales por categoría.
  - Mismo defecto que ya se corrigió en `/summary` en 2026-07-14.

- [x] **`actualizar_transaccion` no actualiza `currency`** — 2h *(2026-08-23)*
  - Mover una transacción de una cuenta COP a una USD la deja con `currency="COP"`.

- [x] **Reordenar la jerarquía de las summary cards del dashboard** — 4h *(2026-08-23)*
  - No es un reemplazo: el dashboard ya muestra `Balance Total`, `Ingresos del Mes` y `Gastos del
    Mes` como 3 cards lado a lado. Se agrega el cálculo de **balance del mes** (ingreso mensual −
    gastos del mes) y se le da prioridad visual; `Balance Total` (suma de saldos de cuentas) se
    **demueve, no se elimina** — pasa a la vista secundaria de cuentas (ver abajo).

- [x] **Desglose por categoría en barras horizontales**, ordenadas de mayor a menor — 1d *(2026-08-23)*
  - Aditivo, no reemplazo: el dashboard hoy no tiene ningún desglose por categoría (los Budget
    Rings son otra cosa). Reusa el endpoint `category-distribution` ya existente.
  - `CategoryDonutChart` se queda intacto en `/analytics` — dona y barras sirven audiencias
    distintas (exploración detallada vs. vistazo rápido); no hace falta que una reemplace a la otra.

- [x] **Vista secundaria de saldos de cuentas** — 4h *(2026-08-23)*
  - Decisión 2026-08-22: los saldos siguen accesibles, solo dejan de ser el dato principal.
  - La página `accounts/` ya cubre esto — la tarea real es mover ahí la card `Balance Total` que
    sale del dashboard, no construir nada nuevo.

- [x] **Ocultar solo los controles de creación/edición de categorías personalizadas** — 4h *(2026-08-23)*
  - Alcance reducido respecto a la versión original (que sacaba toda la ruta `categories/` del
    sidebar). Consistente con Fase 8 (categorías curadas, sin editor en v1): se ocultan los
    botones de crear/editar categoría, pero la ruta se queda en el sidebar y la lista sigue
    visible, para que el usuario pueda ver qué categorías existen.
  - El editor completo vuelve en el backlog post-MVP ("Editor de categorías personalizable" — el
    código ya existe, solo queda oculto).

- [x] **Reagrupar visualmente el sidebar** (primario: Dashboard/Transacciones/Presupuestos —
      secundario: Analítica/Cuentas/Categorías, con separador) — 2h *(2026-08-23)*
  - Reemplaza la tarea original "Podar del flujo principal" (que sacaba Analítica del sidebar).
  - Ningún ítem se remueve del menú ni ninguna ruta se oculta — solo se reordena/agrupa para dar
    prioridad visual a los componentes del MVP sin esconder features ya construidas.
  - Revisar remoción real solo si hay datos de uso que la justifiquen — mismo criterio que la
    Decisión 10.1.4 de Fase 10 (no comprometerse con fricción no validada).

---

## Fase 12 — Pulido visual y omisiones estratégicas ✅ completa (2026-09-05)

**Objetivo:** cerrar lo que quedó de la auditoría de diseño después de que Fase 11 estabilice el
dashboard de flujo — visibilidad de estado en URL, jerarquía visual entre tarjetas, y los huecos
"de producto" (404, favicon, skip-link) que hoy delatan que el proyecto no se terminó de
rematar. Va antes de Fase 15 (onboarding) porque el onboarding es la primera impresión de un
usuario nuevo.

> Implementación completa el 2026-09-05 — ver `docs/specs/fase_12_spec.md` para el desglose
> técnico y las decisiones de diseño numeradas (12.1.1–12.10.2). Verificación: pytest backend
> 91 passed, `pnpm lint`/`pnpm format:check`/`pnpm build` limpios, backend revisado por
> `backend-engineer` (0 archivos backend tocados, contrato de API v1 intacto). Deuda anotada no
> bloqueante: la URL es frontera de entrada sin validación de valores inválidos
> (p. ej. `?category=abc` → 422), `usePersistedState.ts` quedó sin consumidores (deliberado,
> Decisión 12.1.2) y la semántica `preset` vs `start`/`end` divergente post-montaje queda
> documentada como intencional.

- [x] **URL-sync de filtros en Transacciones y Analítica** — 1d *(2026-09-05, ver `docs/specs/fase_12_spec.md` §12.1 — hook `useQueryParamState`, `router.replace`, `<Suspense>` en ambas páginas)*
  - Hoy los filtros de fecha/cuenta/categoría viven en `useState`/`localStorage`, no en query
    params: se pierden al recargar o al compartir el link.

- [x] **Diferenciar visualmente las tarjetas** (elevación solo donde comunica jerarquía) — 4h *(2026-09-05, ver §12.2 — prop `elevated` en `SummaryCard`, cierre del hueco en `CategoryBreakdownBars`, listas sin sombra a propósito)*
  - Hoy toda tarjeta usa el mismo patrón `border + shadow-sm + bg-surface` sin distinción entre
    la tarjeta de saldo destacado y una fila de lista.

- [x] **Tintar las sombras restantes con el color de fondo/acento** — 2h *(2026-09-05, ver §12.3 — `shadow-background/NN` en ~21 lugares)*
  - Ya hay 2 ejemplos correctos (`shadow-primary/10` en el link activo del sidebar y en el FAB) —
    extender al resto de tarjetas y modales.

- [x] **Unificar estados de carga** — 4h *(2026-09-05, ver §12.4 — los 7 archivos reales, no solo los 4 que nombra el ROADMAP)*
  - El dashboard usa `Skeleton` con la forma del contenido; Transacciones, Cuentas, Presupuestos
    y Categorías caen en un `Loader2` genérico.

- [x] **Favicon de marca + limpieza de assets de scaffold** — 2h *(2026-09-05, ver §12.5 — binario reemplazado, 5 SVGs borrados)*
  - `app/favicon.ico` sigue siendo el default de Next.js; `public/` todavía tiene `next.svg`,
    `vercel.svg`, `globe.svg`, `file.svg`, `window.svg` sin usar.

- [x] **Página 404 propia** (`app/not-found.tsx`) — 3h *(2026-09-05, ver §12.6 — solo raíz, sin 404 anidado en dashboard)*

- [x] **Skip-link para navegación por teclado** — 1h *(2026-09-05, ver §12.7 — solo en el shell autenticado)*

- [x] **Validación de formularios por campo**, con foco en el primer error al hacer submit — 1d *(2026-09-05, ver §12.8 — prop `error` de `Input`/`Select`, `noValidate`, migración del modal de edición de transacciones)*
  - Hoy los formularios solo tienen un banner de error genérico y validación nativa `required`.

- [x] **`tabular-nums` en cifras** (`SummaryCard`, `BudgetRing`, columnas de montos) — 2h *(2026-09-05, ver §12.9 — 9 sitios; tooltips Recharts fuera de alcance)*

- [x] **Enlaces legales (privacidad/términos)** en el shell autenticado — 4h *(2026-09-05, ver §12.10 — footer en `Sidebar.tsx`, páginas `/legal/*` públicas)*
  - No es solo diseño: el proyecto pivotó a producto público el 2026-08-22, esto ya no es opcional.

- [ ] Opcional, no bloqueante: **evaluar reemplazar Lucide** por otra librería de iconos —
      cambio de ~20 archivos para un beneficio principalmente estético; dejar en backlog salvo
      que sobre tiempo.

---

## Fase 13 — Presupuestos con alertas + infraestructura de notificaciones ✅ completa (2026-09-06)

**Objetivo:** el primer diferenciador real frente a una hoja de cálculo.

> ⚠️ **Advertencia sobre push web.** En iOS, las notificaciones push solo funcionan si el
> usuario **instaló la PWA en su pantalla de inicio** (Safari 16.4+). Un usuario que solo
> visita la web en el navegador **no recibirá nada** — ni alertas de presupuesto ni resumen
> semanal. Como dos de los cinco componentes del MVP dependen de este canal, conviene
> prototiparlo temprano y considerar un **fallback in-app** (bandeja de avisos dentro de la app)
> o correo como respaldo.

- [x] **PWA instalable** (manifest + service worker + prompt de instalación) — 2d *(2026-09-06, ver `docs/specs/fase_13_spec.md` §13.1 — manifest manual + `sw.js` ~40 líneas, sin next-pwa; prompt con umbral de visitas + fallback iOS)*
  - Prerrequisito de push. Beneficio extra: cubre buena parte del caso "app móvil" sin código nativo.

- [x] **Infraestructura de push web** (VAPID, tabla de suscripciones, envío) — 3d *(2026-09-06, §13.2 — `pywebpush`, tabla `push_subscriptions` con upsert por `endpoint`, limpieza de suscripciones 410/404, par de claves VAPID generado para dev local)*

- [x] **Motor de evaluación de presupuestos** (umbrales 80% y 100%) — 2d *(2026-09-06, §13.3 — evaluación síncrona post-commit; idempotencia por `(budget_id, type)`; extracción de `spent` compartido con `dashboard.py`; fallos nunca revierten la transacción)*
  - Un aviso por umbral por periodo: no repetir en cada transacción.

- [x] **Indicador visual de progreso** que cambia de color al acercarse al límite — 1d *(2026-09-06, §13.4 — BudgetRing realineado a cortes 80/100 en `BudgetRing.tsx:40-41`)*
  - `BudgetRing` ya existe; adaptar al lenguaje visual del MVP.

- [x] **Bandeja de avisos in-app** como fallback — 1d *(2026-09-06, §13.5 — tabla `notifications`, campana en el sidebar con badge `refetchInterval` 60s, popover con listado y "marcar todas")*

*Más deuda de Fase 12 resuelta en el mismo hito: **13.6** validación read-time de query params (whitelist + fallback con tercer arg `validate` en `useQueryParamState`) — cierra la frontera de entrada donde un link `?category=abc` producía 422 y `?bar=foo` entraba con cast silencioso.*

- [x] **Eliminar/descartar notificaciones de la bandeja** — 4h *(2026-09-06, §13.7 — `DELETE /notifications/{id}` + `DELETE /notifications/read` (solo leídas), ícono `X` por fila y botón "Eliminar leídas" en el popover)*
  - Hasta este ítem no existía ninguna ruta `DELETE` en `notifications.py`: ni el usuario
    de prueba ni un usuario real podían vaciar la bandeja, que crecía para siempre.
  - Encontrado en pruebas manuales en vivo de Fase 13 (2026-09-06): repetir una prueba
    sobre el mismo presupuesto/período no genera un aviso nuevo (correcto, es la
    idempotencia de §13.3 funcionando) pero tampoco había forma de limpiar los avisos
    viejos para verificar de nuevo — la ausencia de borrado, no un bug del motor, es lo
    que hacía parecer roto el toast nuevo de la campana.

---

## Fase 14 — Resumen semanal automático ✅ completa (2026-09-06)

**Objetivo:** re-engagement pasivo. El usuario recibe valor sin abrir la app.

> El template es barato; **el canal de entrega no**. Hoy no existe scheduler ni servicio de envío.
> Presupuestar como infraestructura, no como detalle.

> Implementación completa el 2026-09-06 — ver `docs/specs/fase_14_spec.md` para el desglose
> técnico y las decisiones de diseño numeradas (§14.1–§14.7; evaluación arquitectónica previa del
> agente `software-architect`). Verificación: pytest backend 122 passed (9 nuevos en
> `test_weekly_summary.py`), ruff/eslint/`prettier --check`/`pnpm build` limpios, migración
> `418c35db8cbc` aplicada sobre la base de datos de dev (`docker compose up -d --build backend`,
> confirmado `alembic current` → head). Revisado archivo por archivo contra la spec: modelo de
> datos (`User.weekly_summary_enabled` opt-out, `Notification.period_key` + índice único parcial
> `uq_notifications_user_type_period_active`), refactor de `budget_alerts.py` a
> `app/core/notification_dispatch.py` (compartido con Fase 13, sin cambio de comportamiento),
> `app/core/weekly_summary.py` (semana lunes-domingo en `America/Bogota`, solo moneda preferida,
> se envía siempre incluso con $0, delta vs. semana anterior), `BackgroundScheduler` in-process
> con `CronTrigger` lunes 07:00 + hook de `shutdown` (antes inexistente en el proyecto), y la
> primera página de Ajustes del frontend (`/settings`, un solo control).

- [x] **Scheduler** (APScheduler in-process, ver spec §14.4) — 1d *(2026-09-06)*
- [x] **Cálculo del resumen semanal** — total gastado, categoría principal, comparación con la semana anterior — 1.5d *(2026-09-06, ver spec §14.3)*
- [x] **Preferencia de usuario para activar/desactivar** el resumen — 1.5d *(2026-09-06, incluye primera página de Ajustes del frontend, ver spec §14.6)*

---

## Fase 15 — Onboarding de 3 minutos ✅ completa (2026-09-06)

**Objetivo:** llevar al usuario a ver su primer gráfico lo más rápido posible.
Depende de Fases 8, 10 y 11.

> Implementación completa el 2026-09-06 — ver `docs/specs/fase_15_spec.md` para el desglose
> técnico y las decisiones de diseño numeradas (15.0.1–15.6). Fase **100% frontend**: los
> tres "minutos" se resuelven encadenando endpoints ya existentes (hallazgo central del spec,
> verificado contra el código); ningún archivo de `backend/` fue tocado. Verificación: pytest
> backend 122 passed intacto, `pnpm lint`/`format:check`/`build` limpios. Hallazgo del análisis
> de integración (Decisión 15.6): los `Decimal` del backend serializan a `string` en JSON
> (`model_dump(mode="json")`), lo que dejaba la card "Balance del mes" en fallback cuando un
> usuario fija su ingreso — corregido normalizando con `Number(...)` en `page.tsx:101`.

> **Correcciones post-lanzamiento (2026-09-06, mismo día, tras probar el onboarding real en
> vivo)** — cinco hallazgos que no aparecían en pruebas contra la API pero sí al recorrer el
> flujo completo en el navegador:
> 1. **Fechas naive interpretadas como UTC** en `(dashboard)/page.tsx` y `analytics/page.tsx`:
>    `formatISOForBackend` armaba `start_date`/`end_date` con la hora local del navegador sin
>    sufijo de zona horaria; con el servidor en `America/Bogota` (UTC-5) y Postgres en UTC, eso
>    excluía sistemáticamente las últimas ~5 horas de transacciones de "Gastos por Categoría" y
>    de toda Analítica — bug preexistente desde Fase 11/12, no introducido por Fase 15, pero
>    visible siempre en el onboarding porque el primer gasto se registra "ahora mismo". Reemplazado
>    por `date.toISOString()`.
> 2. **El ingreso declarado no aportaba plata real**: solo alimentaba `monthly_flow_balance`
>    (Fase 11 §11.3), así que "Ingresos del Mes" quedaba en $0 y la cuenta arrancaba en negativo
>    apenas se registraba el primer gasto. `OnboardingIncomeStep` ahora también siembra una
>    `Transaction` de tipo income (categoría de sistema "Salario", descripción "Ingreso mensual
>    declarado") — solo desde el onboarding, nunca desde la card inline del dashboard (Decisión
>    11.3.2 intacta).
> 3. Efecto colateral de (2): la transacción semilla pasa a ser la "primera" del usuario, así que
>    el trigger original del aha moment (`total === 1`) dejaba de dispararse. Reemplazado por el
>    query param `?onboarding=1` que ya usa `/capture` (Decisión 15.0.2) — `dashboard/page.tsx`
>    ahora también lee `useSearchParams()` (requirió envolverla en `<Suspense>`).
> 4. **Cuenta por defecto renombrada** de "Efectivo"/`cash` a "Cuenta principal"/`debit` — la
>    mayoría de usuarios nuevos no maneja plata en efectivo puro. Cambio de dos líneas en
>    `crear_usuario` (`type="debit"` ya era un valor soportado en el resto de la app).
> 5. **Desborde de íconos en el footer del sidebar** con nombre/correo largos (campana/tema/logout
>    empujados fuera del borde): al bloque avatar+nombre le faltaba `min-w-0`, así que no podía
>    encogerse para dejarle espacio al cluster de íconos de ancho fijo. Encontrado por el usuario
>    en captura de pantalla real, no relacionado con el bug de fechas.
>
> Verificado end-to-end con Playwright contra el stack real (Docker, no solo pytest): registro →
> paso de ingreso → gasto guiado → dashboard, con capturas de red antes/después de cada fix.
> pytest backend 122 passed, `pnpm lint`/`format:check` limpios.

- [x] **Minuto 0–1: registro sin fricción** — 1d *(2026-09-06, ver `docs/specs/fase_15_spec.md` §15.1/15.3 — auto-login post-registro con degradación explícita, Decisión 15.0.3)*
  - Solo email (decisión 2026-08-22). Sin formularios largos.
  - Una sola pregunta: *"¿Cuál es tu ingreso mensual aproximado?"* → `User.monthly_income`
    (paso `OnboardingIncomeStep` dentro de `/capture?onboarding=1`, condicionado a
    `monthly_income == null`, Decisión 15.3.2). Desde la corrección post-lanzamiento también
    siembra una transacción de ingreso real (ver arriba).

- [x] **Minuto 1–2: primer gasto guiado** — 1d *(2026-09-06, ver `docs/specs/fase_15_spec.md` §15.4 — wizard de 2 pasos activado por query param efímero `?onboarding=1`, Decisión 15.0.2)*
  - Redirección directa a la captura con instrucción explícita.
  - Requiere la cuenta por defecto de Fase 8 (renombrada a "Cuenta principal"/`debit` el mismo día).

- [x] **Minuto 2–3: el "aha moment"** — 1d *(2026-09-06, ver `docs/specs/fase_15_spec.md` §15.5 — banner disparado por `?onboarding=1` desde la corrección post-lanzamiento, antes `total === 1`; 2 variantes de mensaje, Decisión 15.0.1/15.5.1)*
  - Redirección al dashboard mostrando el impacto: *"Has gastado X de tu ingreso mensual."*

---

## Parada — Correcciones de UX post-pivote ✅ completa (2026-09-06)

**Objetivo:** cerrar cinco fricciones de UX encontradas en pruebas manuales en vivo del producto
ya pivotado, antes de seguir con Fase 16. No es una fase numerada del MVP — es una parada de
mantenimiento entre Fase 15 (onboarding) y Fase 16 (automatizaciones). Ninguno de los cinco
puntos toca contratos de API ni requiere migración — alcance 100% frontend.

> Implementado en la rama `worktree-ux-fixes-analitica-filtros` (pendiente merge a `main` al
> momento de escribir esto). Verificado en navegador con Playwright contra un backend/frontend
> aislados (SQLite local, seed real, sin tocar el stack de Docker en uso) — no solo contra el
> build. `pnpm lint`/`pnpm build` limpios.

- [x] **Método de pago heredado del tipo de cuenta** en la captura rápida — *(2026-09-06)*
  - El selector manual (efectivo/tarjeta/transferencia) era independiente del tipo de cuenta
    elegida, permitiendo combinaciones sin sentido (ej. cuenta crédito + efectivo). Ahora se
    deriva automáticamente (`cash→cash`, `debit`/`credit→card`) y se elimina el selector de
    `TransactionCaptureForm.tsx`. Verificado extremo a extremo contra la base de datos.

- [x] **Bug de filtros en Transacciones: la lista quedaba vacía** al aplicar cualquier preset de
  fecha o editar fechas a mano — *(2026-09-06)*
  - Causa raíz: `useQueryParamState` construía cada `URLSearchParams` a partir de un snapshot
    obsoleto de `searchParams`; un handler que llamaba a varios setters seguidos (`applyPreset`,
    `clearFilters`, edición manual de fecha) perdía todos los parámetros salvo el del último
    `router.replace`. Se agrega `useQueryParamsBatch` (mismo hook, un solo `router.replace` para
    varios parámetros a la vez) y se usa en los 4 puntos afectados de `transactions/page.tsx`.

- [x] **Selector de período único en Analítica** (Semana/Mes/Año/Personalizado) — *(2026-09-06)*
  - Reemplaza los dos selectores independientes que existían (uno en el gráfico de barras, que
    afectaba la tarjeta de KPIs de arriba; otro en la dona, que no afectaba nada más) sin ninguna
    señal visual de esa diferencia de alcance. Ahora un único rango de fechas alimenta KPIs,
    barras y dona a la vez, con rango personalizado (fecha inicio/fin) para los casos que no
    cubren los presets.
  - De paso se corrigió un bug de zona horaria en los límites de mes/año: se construían con
    getters locales del navegador (`new Date(y, m, 1)`) y luego `.toISOString()`, lo que los
    desplazaba por el offset horario y excluía transacciones del borde del período — mismo patrón
    de bug ya corregido antes para el dashboard (ver hallazgo #1 de las correcciones
    post-lanzamiento de Fase 15). Ahora se anclan en UTC con `Date.UTC(...)`.

- [x] **Iconos de la sidebar colapsada** más grandes y centrados — *(2026-09-06)*
  - Se veían pequeños y "perdidos" porque el padding horizontal no se reducía al colapsar
    (`w-20` con `px-4 py-3` sin cambios). Ahora cada ítem se centra en una caja de `h-12 w-12` y
    el icono sube de `size 20` a `22`.

- [x] **Botones "agregar" estandarizados y deduplicados con el FAB** — *(2026-09-06)*
  - El botón "Nuevo movimiento" del dashboard y de transacciones abría el mismo `TransactionModal`
    que ya ofrece el FAB global ("Nueva transacción"), duplicando la misma acción en dos controles
    visualmente distintos. Se retiran ambos botones en línea; el FAB queda como única vía para
    crear transacciones en todo el dashboard. El botón de Presupuestos, que no tenía la variante
    de texto corto en móvil que ya usan Cuentas/Categorías, se actualiza para unificar el patrón
    (ícono `Plus` + texto completo en desktop + label corto en móvil).

---

## Fase 16 — Automatizaciones y preparación móvil (post-MVP) ✅ completa (2026-09-06)

**Objetivo:** habilitar atajos de iOS/Android. El backend ya es REST/JSON stateless con bearer
tokens, así que **no hay que rehacer nada** — solo agregar las piezas que faltan.

> Implementación completa el 2026-09-06 — ver `docs/specs/fase_16_spec.md` para el desglose
> técnico y las decisiones numeradas (16.1.1–16.4.3). Orden de implementación seguido:
> **16.1 → 16.2 → 16.4 → 16.3** (el del spec). Verificación: pytest backend 154 passed
> (32 nuevos entre `test_api_keys.py`, `test_transactions.py` y `test_accounts.py`),
> ruff check/format, eslint, `prettier --check` y `pnpm build` limpios; migraciones
> `6c9bbf3564cc` (api_keys) y `e460a42926d7` (opening_balance) aplicadas, `alembic current`
> → head. Desviaciones documentadas respecto del spec: (1) la desviación recomendada de
> `security-reviewer` para §16.1 (Decisión 16.1.8) queda **pendiente** — el agente no estaba
> disponible en el entorno; anotada en `docs/TODO.md`. (2) §16.2 descubrió en implementación
> que `Transaction` ya tiene una *relación* ORM llamada `category`, que colisionaba con el
> campo de texto nuevo → se resolvió con un `field_validator(mode="before")` en
> `TransactionResponse` (la respuesta siempre trae `category: null`; `category_id` es el dato).

- [x] **API keys personales revocables** — 2d *(2026-09-06)*
  - 🔑 **Es lo que habilita los atajos.** Un Shortcut de iOS no puede hacer el flujo OAuth2
    password ni refrescar un token cada 60 minutos.
  - La misma pieza sirve para la nota de voz con IA de v1.2.

- [x] **Endpoint de captura rápida por nombre** — 1d *(2026-09-06)*
  - Aceptar `category: "Alimentación"` en vez de `category_id: 3`.
  - Un Shortcut no puede resolver IDs cómodamente. También es la puerta de entrada natural
    para el parseo de lenguaje natural.

- [x] **Codegen de tipos desde OpenAPI** — 1d *(2026-09-06)*
  - FastAPI ya expone el schema. Elimina el drift manual entre Pydantic y TypeScript.
  - Con una app nativa serían tres copias de los tipos en vez de dos.

- [x] **Reconciliación de saldos** — 1d *(2026-09-06)*
  - Como las cuentas quedan visibles, hace falta una operación "recalcular saldo desde movimientos".
  - Hoy, si un saldo se desvía, no hay forma de detectarlo ni corregirlo.
  - Separar `opening_balance` (inmutable) de `current_balance` (derivado).

---

## Fase 17 — Análisis por cuenta y presupuestos multi-moneda

**Objetivo:** hoy el dashboard agrega todas las cuentas por diseño (Fase 11) y `accounts/[id]` no
tiene ningún gráfico — solo saldo, historial plano y el botón de recalcular saldo. Por separado,
`Budget` ya tiene su propia columna `currency` (Fase 3) pero el formulario nunca la expone ni la
envía, así que en la práctica todo presupuesto se crea en COP. Depende de Fase 8 (`Account.currency`,
`Budget.currency`) y Fase 11 (componentes de gráficos reutilizables).

> Decidido en sesión de grilling del 2026-09-12, a partir de una semana de uso real desde celular.
> No requiere ninguna migración de compatibilidad — el proyecto sigue sin usuarios reales.

- [x] **Analítica por cuenta en `accounts/[id]`** — reutilizar los mismos componentes de gráficos
      del dashboard general (`CategoryDonutChart`, `CategoryBreakdownBars`, `BudgetRing`),
      filtrados a esa cuenta.
  - El dashboard principal no cambia: sigue agregando todas las cuentas (decisión ya tomada en
    Fase 11, reafirmada aquí) — no se agrega un selector de cuenta ahí.
  - Incluye su propio "balance del mes" (ingreso − gasto de esa cuenta), con el mismo componente
    que rediseña Fase 19 más abajo.
- [x] **Selector de moneda en el formulario de presupuestos** — hoy `budgets/page.tsx` no tiene
      campo de moneda ni lo envía en el payload; `Budget.currency` (default `"COP"`) nunca se
      toca desde la UI.
  - Opciones derivadas de las monedas presentes en las cuentas del usuario — no se agrega
    `account_id` a `Budget`; se mantiene el filtrado estricto por moneda que ya existe en el
    cálculo de progreso (`dashboard.py`).
  - En la vista por cuenta del ítem anterior, los presupuestos se filtran por la moneda de esa cuenta.

---

## Fase 18 — Categorías personalizables

**Objetivo:** ampliar el catálogo curado de categorías (hoy 11, ver Fase 8 "Categorías default
ampliadas a 8–10"), dejar que cada usuario decida su propio nivel de detalle, y activar el editor
de categorías personalizado que ya existe en el código — backend con CRUD completo para
categorías `user_id` no nulo, frontend apagado desde Fase 11 detrás de un flag.

> Decidido en sesión de grilling del 2026-09-12. Sin usuarios reales todavía, no hace falta
> ninguna ruta de migración con compatibilidad — se puede re-sembrar directamente.

- [x] **Ampliar el pool de categorías default** — agregar Mercado, Pareja, Regalos, Restaurantes,
      Gastos hormiga, Uber, Carro, Transporte público (lista final a cerrar en la spec).
  - No reemplaza "Transporte" genérica — conviven ambos niveles de detalle, cada usuario elige
    el suyo.
- [x] **Selección de categorías en el registro** — un set base razonable viene pre-marcado (ej.
      Mercado, Transporte, Vivienda, Salud, Entretenimiento, Otro); el resto queda visible para
      agregar cuando el usuario quiera.
- [x] **Concepto nuevo: categorías "ocultas para mí"** — por usuario, no modifica ni borra
      categorías del sistema (siguen siendo compartidas e inmutables vía API, sin cambios).
      Ocultar solo afecta el selector al crear una transacción nueva; no esconde transacciones
      históricas ni datos de analíticas.
- [x] **Activar el editor de categorías personalizadas** — quitar
      `CUSTOM_CATEGORY_EDITING_ENABLED = false` en `categories/page.tsx:24`; el backend ya
      soporta CRUD completo de categorías user-owned desde antes de Fase 11.
  - Se retira del backlog priorizado (ver tabla abajo) — pasa a programado aquí.

---

## Fase 19 — Fricción post-onboarding y analítica de ingreso ✅ completa (2026-09-12)

**Objetivo:** cerrar tres fricciones encontradas en una semana de uso real desde celular.

> Decidido en sesión de grilling del 2026-09-12. Implementación completa el mismo día — ver
> `docs/specs/fase_19_spec.md` para el desglose técnico y las decisiones de diseño numeradas
> (19.1.1–19.3.5). Verificación: pytest backend 177 passed (5 nuevos en `test_users.py` y
> `test_dashboard.py`), `ruff check`/`format` limpios, `pnpm lint`/`format:check`/`build` limpios.
> Los tres ítems son independientes (no comparten archivos) y se implementaron en paralelo con
> agentes `backend-engineer`/`frontend-engineer`.

- [x] **Redirección de login condicionada al uso real, no solo al onboarding** — *2026-09-12* —
      hoy `login/page.tsx:58` redirige siempre a `/capture`, sin condición. Se agregó
      `has_transaction_history` a `GET /users/me` (no al login, ver Decisión 19.1.1); el campo se
      calcula con una query `LIMIT 2` (Decisión 19.1.2, sin `COUNT(*)`); con 2 o más
      transacciones, el login redirige directo a `/dashboard`.
  - Esto resuelve la **Decisión 10.1.4** de Fase 10, documentada ahí mismo como riesgo a validar
    con datos de uso reales una vez hubiera usuarios recurrentes — ya se validó: genera
    exactamente la fricción medible que esa decisión anticipaba. El frontend primea el cache de
    TanStack Query con la respuesta de `users/me` y usa `/capture` como fallback si el fetch
    falla (Decisiones 19.1.4/19.1.5). El flujo de registro (`register/page.tsx`) no cambia —
    `?onboarding=1` sigue siendo el destino de un usuario recién creado.
- [x] **Rediseño de la card "Balance del mes"** — *2026-09-12* — hoy es redundante junto a
      "Ingresos del Mes" / "Gastos del Mes" (ver Fase 11, "Reordenar la jerarquía de las summary
      cards del dashboard"): las mismas 3 cifras en 3 tarjetas separadas. Se fusionó en una sola
      `SummaryCard` con la prop nueva `secondaryStats` (una fila compacta Ingresos/Gastos debajo
      de la cifra principal, Decisión 19.2.1/19.2.2), sin eliminar el dato — sigue siendo el
      titular del pivote a flujo (Cambio de enfoque, 2026-08-22). De paso se cerró el Hallazgo 7
      del spec: `AccountMonthlyBalanceCard` (Fase 17) dejó de restar `income - expense` en el
      cliente y lee `monthly_flow_balance` directo del backend (Decisión 19.2.3).
- [x] **Nueva métrica "% del ingreso por categoría" en Analítica** — *2026-09-12* — complementaria
      a la dona existente (que reparte el 100% de los *gastos*, no del ingreso). Se implementó
      como grupo "Referencia" (`Mis gastos | Mi ingreso total`) dentro del popover de la dona,
      con copy explícitamente distinto del selector "Tipo" para no confundir ambos ejes (Decisión
      19.3.1), deshabilitado en las combinaciones sin significado de producto (Tipo=Ingresos,
      Modo=Neto, Decisiones 19.3.2/19.3.3) y con el denominador reutilizando `totals.totalIncome`
      ya sumado en cliente, sin endpoint nuevo (Decisión 19.3.4). La igualdad que eso presupone
      quedó probada por el test de equivalencia `category-distribution`/`cashflow-series`
      (Decisión 19.3.5).

---

## Backlog priorizado (después del MVP)

| Prioridad | Feature | Nota |
|---|---|---|
| Alta | **Automatización de ingresos/gastos recurrentes** | Feature de retención del mes 2, no de adquisición del día 1. Requiere scheduler (ya existirá tras Fase 14). |
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
| 2026-09-05 | **Fase 12** — Pulido visual: URL-sync (hook `useQueryParamState`), elevación selectiva de tarjetas, sombras tintadas `shadow-background/NN`, loading unificado con Skeleton (7 archivos), favicon de marca + limpieza de assets, 404 propio, skip-link, validación por campo con `noValidate`, `tabular-nums`, enlaces legales. Fase 100% frontend |
| 2026-09-06 | **Fase 13** — Presupuestos con alertas + notificaciones: tabla `notifications` + motor de umbrales 80/100 (síncrono post-commit, idempotente por `(budget_id, type)`, `spent` compartido con dashboard), campana in-app con badge (poll 60s, "marcar todas"), PWA instalable (manifest + `sw.js` manual, íconos 192/512, prompt con fallback iOS), push web (`pywebpush`, VAPID dev, upsert por endpoint, limpieza 410), BudgetRing alineado a 80/100. Más 13.6: validación read-time de query params (deuda de Fase 12) y 13.7: borrado de notificaciones (`DELETE /notifications/{id}` y `/read`), encontrado en pruebas manuales en vivo el mismo día. 22 tests nuevos |

### Pendientes heredados de fases anteriores

- [ ] Acceder y verificar el flujo completo desde celular vía Tailscale (Fase 4A).
- [ ] Seed automático tras el primer startup en Docker (Fase 4B).
- [ ] Script `scripts/deploy.sh` (git pull → docker compose up --build -d) (Fase 4B).
- [ ] Decidir `AccountUpdate.currency` — el schema hereda el campo pero `accounts.py` lo ignora silenciosamente.
- [ ] Extraer custom hooks de queries (`useAccounts`, `useCategories`, `useTransactions`).
- [ ] Migrar JWT de `localStorage` a cookies httpOnly (sube de prioridad al salir de Tailscale).
- [ ] Crear capa `app/services/` y `app/core/exceptions.py`; partir `models.py` y `schemas.py` por dominio.
- [x] **`focus-visible` y `htmlFor`/`id` en el modal de edición manual de `transactions/page.tsx`** (Fase 9). Resuelto en Fase 12 §12.8.3: el modal migró a los componentes `Input`/`Select` compartidos (con validación por campo y foco en el primer error).
  - El modal de editar transacción (líneas ~495-577) usa `<input>`/`<select>` crudos en vez de los
    componentes `Input`/`Select` ya corregidos en Fase 9 (§9.1/§9.2 de `docs/specs/fase_09_spec.md`):
    sus `<label>` siguen sin `htmlFor`, sus controles sin `id`, y el anillo de foco sigue activándose
    con click de mouse (`focus:` en vez de `focus-visible:`).
  - Quedó fuera de alcance a propósito en Fase 9 porque el ROADMAP nombraba literalmente solo
    `Button`/`Input`/`Select` — no un descuido de implementación, ver hallazgo en la revisión de
    código del 2026-08-23. Vale la pena resolverlo migrando ese modal a los componentes `Input`/
    `Select` compartidos (elimina la duplicación de markup a la vez que cierra el gap).
