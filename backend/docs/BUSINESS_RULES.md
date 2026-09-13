# Reglas de negocio

## Usuarios y autenticación

- El correo debe ser único.
- El nombre completo (`full_name`) es obligatorio al registrar un usuario.
- La contraseña se guarda hasheada con bcrypt.
- El JWT identifica al usuario mediante `sub`.
- El login usa `OAuth2PasswordRequestForm` y recibe el correo en el campo `username`.

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
- `highlighted` marca una cuenta como destacada para el dashboard. Si no hay cuentas destacadas, el dashboard muestra todas.

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

- Un usuario solo puede tener un presupuesto por categoría, mes y año.
- La categoría del presupuesto debe existir y estar disponible para el usuario.
- El progreso del presupuesto se calcula sobre gastos del mes actual.
- Los presupuestos también pueden listarse por mes y año.

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