# Reglas de negocio

## Usuarios y autenticación

- El correo debe ser único.
- El nombre completo (`full_name`) es obligatorio al registrar un usuario.
- La contraseña se guarda hasheada con bcrypt.
- El JWT identifica al usuario mediante `sub`.
- El login usa `OAuth2PasswordRequestForm` y recibe el correo en el campo `username`.

### Sesión por cookies (Fase 26)

- La sesión de navegador vive en tres cookies (`access_token` HttpOnly — Path `/` — 15 min;
  `refresh_token` HttpOnly — Path `/api/v1/auth` — 30 días; `csrf_token` NO HttpOnly
  — 30 días — para el patrón double-submit). `SameSite=lax` en los tres; `Secure` según
  `COOKIE_SECURE`.
- `get_current_user` acepta el header `Authorization` como camino **primario** y el cookie
  `access_token` como fallback solo si no vino header: los clientes no-browser (curl, API
  keys) no pasan por ninguna rama nueva.
- Toda mutación autenticada **por cookie** debe mandar `X-CSRF-Token` con el valor del cookie
  `csrf_token`; sin cookie de sesión (API key / JWT por header) o en métodos seguros
  `GET`/`HEAD`/`OPTIONS` no se exige. Rechazo: `403 "Token CSRF inválido o ausente."`.
- `logout` y `DELETE /users/me` limpian los tres cookies de sesión en su propia respuesta —
  los cookies `httpOnly` no pueden borrarse desde JS, así que cada endpoint que termina una
  sesión es responsable de limpiarlos.

### API keys (Fase 16 §16.1)

- Una API key identifica exactamente a un usuario y **no tiene scopes en v1**: tiene los
  mismos permisos que el JWT de su dueño (la autorización real vive en cada router, filtrada
  por `user_id`).
- Es indistingible del JWT en el contrato: viaja en el mismo `Authorization: Bearer <key>`,
  con prefijo `oikos_pat_` que la distingue internamente.
- La key en texto plano se muestra **una sola vez**, en la respuesta de su creación; el
  backend solo guarda `key_hash` (sha256) y `key_prefix` (primeros 12 caracteres, no secreto).
- **Revocación inmediata**: `revoked_at` se valida en cada request — la siguiente petición con
  una key revocada falla con `401` (sin ventana de gracia, a diferencia del JWT).
- No hay expiración obligatoria en v1 (criterio de PAT) — decisión de producto revisada y
  mantenida en la revisión de seguridad de la Decisión 16.1.8 (ver `docs/TODO.md`), no un
  olvido; sigue como recomendación abierta para v2 si el caso de uso lo justifica.
- Rate limiting: las peticiones autenticadas con API key están sujetas al límite de
  `POST /transactions` (60/min) keyed por `user_id` (resuelto contra la DB) — todas las
  keys activas de un mismo usuario comparten un único balde, corregido en la revisión de
  seguridad post-16.1 (antes clavaba por la key, permitiendo multiplicar la cuota real
  creando más keys).
- `POST /api-keys/` (creación) lleva su propio rate limit (5/min por IP, mismo patrón que
  login/registro/reset) y un tope de 20 API keys activas por usuario — agregado en la
  misma revisión para que un JWT robado de corta vida no alcance para mintear un número
  arbitrario de credenciales de larga vida.
- Un reset de contraseña exitoso revoca también todas las API keys activas del usuario,
  igual que ya hacía con los refresh tokens (agregado en la misma revisión: antes una key
  minteada durante una ventana de compromiso sobrevivía sin cambios a esa acción).

## Cuentas

- Una cuenta pertenece a un único usuario.
- `balance` puede definirse al crear la cuenta, pero solo como saldo inicial.
- En edición, `balance` no debe ser modificable por el Frontend.
- `opening_balance` (Fase 16 §16.4) captura el saldo de apertura en la creación y es
  **inmutable** desde entonces. `balance` es el saldo actual, mutado por las operaciones de
  transacciones; la verificación de que ambos cuadran (`balance == opening_balance + neto de
  transacciones`) es el endpoint `POST /accounts/{id}/reconcile`.
- El saldo real se deriva de transacciones e impactos contables — el mecanismo verificable
  de esa afirmación es la reconciliación (§16.4).
- **Límite honesto del backfill (§16.4.4):** la columna `opening_balance` se pobló en la
  migración con `balance_actual − neto(transacciones)`, de modo que en el momento de migrar
  toda cuenta cuadra con discrepancia `0.00`. Eso establece una línea de base limpia hacia
  adelante, pero **no detecta desviaciones que ya hayan ocurrido antes de la migración** — no
  existe un snapshot histórico del saldo para auditar el pasado.
- `highlighted` marca una cuenta como destacada para el dashboard. Si no hay cuentas destacadas,
  el dashboard muestra todas. Desde Fase 29 el filtro aplica **solo a los agregados de
  `GET /dashboard/summary`** (`balances`, `monthly_income_by_currency`,
  `monthly_expense_by_currency`); las barras de `category-distribution`, el `spent` de los
  presupuestos y los campos `first_transaction_month` / `expense_currencies` del summary usan
  todas las cuentas (ver la sección "Dashboard").

## Categorías

- Las categorías con `user_id = null` son categorías base del sistema.
- Las categorías personalizadas pertenecen a un usuario específico.
- Las categorías base no se pueden editar ni borrar desde la API.
- Al iniciar la aplicación se siembran categorías base y se corrigen nombres heredados de categorías base antiguas.
- **Ocultar una categoría ("oculta para mí", Fase 18):** el flag `is_hidden` de
  `GET /categories/` es una preferencia estrictamente **por usuario**, persistida en
  `hidden_categories` (una fila por par user-categoría), nunca en `Category` — ocultarla
  para mí no la oculta para ningún otro usuario y **no modifica ni borra** la categoría
  (ni las de sistema ni las propias). Ocultar solo afecta al selector de captura al crear
  una transacción nueva; **no esconde históricos ni analítica** (transacciones pasadas,
  filtros de `/transactions`, presupuestos y el dashboard siguen viendo la categoría). La
  resolución por nombre de Fase 16 §16.2 (`category` en `POST /transactions`) **no se ve
  afectada**: una categoría oculta sigue resolviéndose por nombre (Decisión Q7 — los
  atajos móviles existen para saltarse el selector visual). Los endpoints
  `POST`/`DELETE /categories/{id}/hide` aplican a categorías propias **y** de sistema,
  sin rama de ownership (Decisión 18.3.4).

## Transacciones

- Cada transacción debe pertenecer al usuario autenticado.
- La cuenta asociada debe pertenecer al mismo usuario.
- La categoría asociada debe ser propia del usuario o una categoría base.
- Resolución de categoría por nombre (Fase 16 §16.2): `category` y `category_id` son
  mutuamente excluyentes (exactamente uno de los dos). Al resolver por nombre:
  - el match es case y acento-insensible y se filtra por `type` (una categoría de gasto y
    otra de ingreso con el mismo nombre no se pisan);
  - **precedencia propia > sistema**: la categoría personal del usuario con ese nombre
    prevalece sobre la de sistema (asume que la personal reemplaza/oculta la de sistema);
  - `409` si el usuario tiene **más de una** categoría propia con el mismo nombre+tipo (error
    de datos real, posible por API cruda; no se adivina con dinero);
  - `404` si no matchea ninguna, listando las categorías válidas del tipo.
- `account_id` es opcional (Fase 16 §16.2): si se omite y el usuario tiene exactamente una
  cuenta, se usa esa; si tiene más de una → `400` (no se adivina cuál); si no tiene ninguna
  → `400`. No se resuelve `account` por nombre en v1.
- `income` suma al saldo de la cuenta.
- `expense` resta del saldo de la cuenta.
- Al borrar una transacción se revierte su impacto sobre la cuenta.
- Al editar una transacción se revierte el efecto anterior y se aplica el nuevo.
- Las consultas de listado permiten filtrar por cuenta, categoría y rango de fechas.
- Si el rango de fechas está invertido, la API responde con error de validación.

## Presupuestos

- Un usuario solo puede tener un presupuesto por categoría, mes, año **y moneda** (Fase 17
  §17.2.2: la unicidad es un índice único parcial sobre filas activas,
  `(user_id, category_id, month, year, currency)` — dos presupuestos de la misma categoría en
  el mismo período son válidos si están en monedas distintas).
- La categoría del presupuesto debe existir y estar disponible para el usuario.
- El progreso del presupuesto se calcula sobre los gastos del **período consultado**, no solo
  del mes actual (Fase 29): `GET /dashboard/budgets-progress` con `?year=&month=` devuelve los
  presupuestos de ese mes con su gasto real de ese mes. El `spent` suma transacciones de
  **todas** las cuentas del usuario en la moneda del presupuesto — no solo las destacadas — y
  sale del mismo cálculo que el motor de alertas, para que la vista y el aviso no divergan.
- La generación perezosa de las filas recurrentes (plantilla `is_recurring`) depende del
  caller: `budgets-progress` genera **solo para el mes actual**, y el motor de alertas
  (disparado por crear/actualizar un gasto, con el mes de la fecha de esa transacción) genera
  solo para el mes actual **o posterior** (Fase 29). Por eso un gasto cargado con fecha
  atrasada en un mes cerrado ya no crea presupuestos retroactivos ni dispara avisos de ese
  mes; los presupuestos que ya existían en ese mes siguen evaluándose. `GET /budgets/?month=&year=`
  sigue generando para cualquier período, incluidos los ya cerrados (fuera del guard de la
  Fase 29, registrado en `docs/TODO.md`).
- Los presupuestos se pueden listar por mes y año en `GET /budgets/` (filtros opcionales y
  combinables). Ese listado no calcula progreso: el gasto real por presupuesto solo lo entrega
  `GET /dashboard/budgets-progress`.

## Eliminaciones

- No se puede borrar una cuenta con transacciones.
- No se puede borrar una categoría con transacciones.
- No se puede borrar una categoría con presupuestos activos.
- No se pueden borrar categorías base del sistema.
- No se puede borrar una cuenta o categoría ajena al usuario autenticado.
- No se puede borrar ni editar una categoría base del sistema.

## Dashboard

- El resumen usa datos agregados del backend.
- El progreso de presupuestos ya sale calculado para uso directo del Frontend.
- El dashboard expone además serie temporal de flujo de caja y distribución por categoría.
- El período consultado (`?year=&month=`, ambos o ninguno) es un mes calendario **UTC**: sin
  parámetros es el mes actual. El mes en curso tiene techo "ahora" — una transacción con fecha
  futura del mismo mes no cuenta como gasto del mes — y un mes ya cerrado llega hasta el
  último día a las 23:59:59.
- `balances` es siempre el saldo **actual** (stock) de las cuentas, con independencia del mes
  consultado: no es un saldo histórico ni una foto del mes pedido.
- `monthly_flow_balance` tiene dos bases y `monthly_flow_basis` dice cuál: `"declared"` en el
  mes en curso (ingreso mensual declarado − gasto del mes, `null` si el usuario todavía no
  fijó `monthly_income`) y `"actual"` en un mes cerrado (ingresos reales registrados − gastos
  reales, nunca `null`). En las dos bases solo cuenta la moneda preferida: no hay conversión
  de moneda en ningún punto.
- El filtro de cuentas destacadas y el resto de las cuentas usan universos distintos **dentro
  del mismo dashboard** (ver la sección "Cuentas"). Es una inconsistencia conocida, no una
  decisión redondeada, y está registrada en `docs/TODO.md`.
- `first_transaction_month` (mes UTC de la transacción más antigua, sobre todas las cuentas) e
  `expense_currencies` (monedas con gasto en el mes, sobre todas las cuentas) existen para que
  el frontend navegue el mes y ofrezca el selector de moneda sin recalcular nada; ninguno de
  los dos está restringido a las cuentas destacadas.

## Notificaciones (Fase 13 §13.5 / Fase 14 §14.7)

- Hay dos tipos de aviso: **alertas de presupuesto** (`budget_threshold_80`,
  `budget_threshold_100`) y **resumen semanal** (`weekly_summary`).
- Un aviso se persiste primero en la bandeja in-app (`notifications`); el push es
  best-effort sobre la misma fila (el aviso nunca "existe" en push sin existir en la
  bandeja, ni al revés).
- Idempotencia — "un aviso por evento/periodo" — es una garantía de base de datos, no
  solo de aplicación, vía índices únicos parciales:
  - alertas de presupuesto: una por `(budget_id, type)` para filas con presupuesto
    (`uq_notifications_budget_type_active`);
  - resumen semanal: uno por `(user_id, type, period_key)` para filas con período ISO
    (`uq_notifications_user_type_period_active`).
- Un fallo del envío push nunca rompe la operación que lo originó (transacción o job);
  el aviso ya quedó en la bandeja. Sin VAPID configurado, el push se omite en silencio
  (con log) y solo queda la bandeja.
- El resumen semanal es opt-out (`User.weekly_summary_enabled`, default `true`); se
  calcula cada lunes en `America/Bogota` sobre la moneda preferida del usuario.