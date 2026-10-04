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
- **El `401` de `POST /auth/refresh` también limpia los tres cookies de sesión, siempre**
  (Fase 31, Decisión B10, QA-021) — sin cookie ni body, con un token desconocido, o con uno
  recién revocado por una rotación legítima de otra pestaña (carrera rara y aceptada: en ese
  caso las dos pestañas pierden la sesión y hay que volver a iniciar sesión). Antes, ese `401`
  se lanzaba como una excepción de dominio genérica y el handler global armaba una respuesta
  nueva que perdía cualquier `Set-Cookie` — una cookie `csrf_token` huérfana (p. ej. tras
  resetear la contraseña desde otro dispositivo) dejaba `/login` recargándose en bucle sin
  poder iniciar sesión.

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

- **Validación de nombre (QA-028):** `name` debe tener 1–100 caracteres tras `strip` —
  `"   "` → `422`. El validador `nombre_sin_espacios` en `schemas/common.py` lo aplica en
  `AccountBase.name`. `AccountResponse` redeclara `name` sin el validador para tolerar filas
  heredadas con nombre en blanco (misma lección que QA-023/QA-025: response models no
  revalidan reglas de input).

- **Validación de moneda (QA-025):** `currency` en `AccountBase` debe cumplir `^[A-Z]{3}$`.
  `"zzzzzz"`, `""`, `"cop"`, `"XX"` → `422`. `AccountResponse` redeclara `currency` sin
  patrón para tolerar filas heredadas.

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

- **Validación de nombre (QA-028):** `name` debe tener 1–100 caracteres tras `strip` —
  `"   "` (solo espacios) → `422`. El validador `nombre_sin_espacios` en `schemas/common.py`
  lo aplica en `CategoryBase.name` y `AccountBase.name`. `CategoryResponse` y
  `AccountResponse` redeclaran `name` sin el validador para tolerar filas heredadas con
  nombre en blanco (misma lección que QA-023/QA-025: response models no revalidan reglas de
  input).

- **Unicidad por usuario y `type` (QA-028):** el nombre normalizado (NFKD → ascii → strip →
  lower) no puede repetirse entre las categorías **propias y activas** del mismo usuario
  **del mismo `type`**. `400` en `POST`/`PUT` si se detecta duplicado. Las categorías de
  sistema (`user_id IS NULL`) no bloquean (el resolver prioriza la propia del usuario).
  Soft-deleted no bloquean (crear → borrar → volver a crear con el mismo nombre = 201).
  Chequeo en la capa de API, sin restricción en DB (misma política que presupuesto).

- **Cambio de `type` bloqueado (QA-027):** si la categoría tiene transacciones o presupuestos
  asociados (solo activos, soft-deleted no cuentan), cambiar su `type` se rechaza con
  `ConflictError` 409 (`"No se puede cambiar la naturaleza de una categoría con
  transacciones/presupuestos asociados."`). Editar solo el `name` o mantener el `type` no
  se bloquea. Reembolsos con categoría cruzada creados antes del bloqueo siguen válidos.

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
- **Reembolsos (Fase 31, Q10):** una categoría acepta transacciones de los dos tipos —
  no hay validación cruzada tipo/categoría. Un `income` en una categoría de gasto (p.
  ej. un reembolso de "Restaurante") es un caso soportado, no un error de datos.
  Limitación actual: solo la dona de Analítica con `?neto=true` lo netea
  (`expense - income` de la categoría); la tarjeta del dashboard y los KPIs de
  Analítica lo cuentan como ingreso normal, y los presupuestos/alertas solo suman
  gastos (no lo restan). Netear los reembolsos en toda la app (tarjeta, KPIs,
  presupuestos, alertas, resumen semanal) es backlog, con su propio `/grilling` (Q15).
- Al borrar una transacción se revierte su impacto sobre la cuenta.
- Al editar una transacción se revierte el efecto anterior y se aplica el nuevo.
- Las consultas de listado permiten filtrar por cuenta, categoría y rango de fechas.
- Si el rango de fechas está invertido, la API responde con error de validación.
- **Rango de `amount` (Fase 31, Decisión B3):** 12 dígitos enteros y 2 decimales
  (el rango real de `Numeric(14,2)`), validado con `max_digits`/`decimal_places` en
  el schema — un valor fuera de rango es `422` con `detail` en lista, antes de llegar
  a la base. Mismo límite en `AccountCreate.balance`, `UserProfileUpdate.monthly_income`
  y `BudgetBase.amount_limit`: son los cuatro campos de entrada con dinero, y todos
  usan la misma constante (`app/schemas/common.py`).
- **Desborde de saldo (Fase 31, Decisión B4, QA-015):** si `POST`/`PUT`/`DELETE
  /transactions/{id}` dejarían el saldo de una cuenta fuera del rango de
  `Numeric(14,2)` (`NumericValueOutOfRange` en Postgres — SQLite no aplica `Numeric` y
  no lo reproduce), la API responde `422` con `detail` string y no toca el saldo.
- **Concurrencia sobre una misma transacción (Fase 31, Decisión B1, QA-003):** `PUT` y
  `DELETE /transactions/{id}` bloquean la fila (`SELECT ... FOR UPDATE`) como primera
  consulta y se serializan entre sí — dos peticiones simultáneas sobre la misma
  transacción se aplican una después de la otra, nunca a la vez. `DELETE` además
  marca `deleted_at` con un `UPDATE` condicional (`WHERE deleted_at IS NULL`): si
  pierde la carrera, no afecta filas, responde `404` y no revierte el saldo una
  segunda vez. Editar o borrar una transacción que otra petición ya borró también es
  `404`. Protección real solo en Postgres — SQLite no soporta `FOR UPDATE`.
- **`aplicar_edicion` y el orden de cuentas (Fase 31, Decisión B2):** cuando un `PUT`
  mueve una transacción de una cuenta a otra, los dos `UPDATE` de saldo se ejecutan en
  orden de `account_id` ascendente (los deltas conmutan, el resultado es el mismo) —
  evita un `DeadlockDetected` de Postgres cuando dos `PUT` concurrentes mueven
  transacciones distintas en sentidos opuestos entre las mismas dos cuentas.
- **`total` de `GET /transactions` (Fase 31, Decisión B5, QA-006):** excluye las
  transacciones borradas — antes, el conteo (`with_entities(func.count())`, el único
  agregado del backend que el filtro global de borrado lógico no alcanza) contaba las
  borradas aunque la página de resultados ya las excluyera, y "Cargar más" del
  frontend quedaba disponible para siempre.
- **`Idempotency-Key` reusada con otro payload en carrera (Fase 31, Decisión B7,
  QA-020):** también responde `409` cuando la comparación de hashes ocurre en la rama
  que perdió una carrera de inserción (`IntegrityError`) contra otra petición con la
  misma clave — antes esa rama devolvía la transacción ganadora sin comparar el hash,
  y si la original ya estaba borrada devolvía un `500` de validación de respuesta en
  vez de un `409` de dominio.

- **Actualización parcial en `PUT /transactions` (QA-026):** se usa `model_fields_set`
  para distinguir "ausente" de `null` explícito — ausente conserva, `null` limpia.
  Aplica a `description` y `payment_method` (la web siempre manda `description`;
  `payment_method` ausente conserva, `null` limpia). `date` no acepta `null` explícito
  (el response exige `datetime` no opcional).

- **Guarda defensiva en `PUT /transactions` con cuenta anterior borrada (QA-031):**
  eliminada la query redundante de `cuenta_vieja`; se pasa `transaccion_db.account_id`
  directamente. `ledger.aplicar_delta` ya no-opera sobre cuentas soft-deleted
  (`deleted_at IS NULL`, Decisión 6.1), así que la semántica no cambia — la cuenta
  desaparecida conserva su saldo obsoleto, invisible en cualquier lista.

- **Validación de paginación (QA-025):** `skip` ≥ 0, `limit` 1–1000 en `GET /transactions`;
  `skip` ≥ 0, `limit` 1–200 en `GET /accounts`; `skip` ≥ 0, `limit` 1–1000 en
  `GET /notifications`. Valores fuera de rango → `422`.

- **Validación de moneda (QA-025):** `currency` en schemas de request (`AccountBase`,
  `TransactionBase`, `BudgetBase`, `PreferencesUpdate`) debe cumplir `^[A-Z]{3}$`.
  `"zzzzzz"`, `""`, `"cop"`, `"XX"` → `422`. Minúsculas → `422` (no se normalizan).
  Response models (`AccountResponse`, `TransactionResponse`, `BudgetResponse`,
  `UserResponse`) redeclaran `currency` sin patrón para tolerar filas heredadas
  (misma lección que QA-023/QA-028: response models no revalidan reglas de input).

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
  sale del mismo cálculo que el motor de alertas, para que la vista y el aviso no diverjan.
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

- **Validación de período (QA-023):** `GET /budgets/?month=&year=` valida `month` 1–12 y
  `year` 2020–2100 en el endpoint (`Query(ge/le)`). `ensure_recurring_budgets_for_period`
  tiene guarda de rango (defensa en profundidad) para sus 3 callers (`budgets.py`,
  `dashboard.py`, `budget_alerts.py`). Períodos fuera de rango → `422`.
- **Response model tolerante (QA-023):** `BudgetResponse` no revalida `month`/`year`/`currency`
  con los rangos/patrones de entrada — filas heredadas con valores fuera de rango se
  serializan sin 500. La limpieza SQL recomendada:
  `DELETE FROM budgets WHERE month NOT BETWEEN 1 AND 12 OR year NOT BETWEEN 2020 AND 2100`.
- **Validación de moneda (QA-025):** `currency` en `BudgetBase` debe cumplir `^[A-Z]{3}$`.
  `"zzzzzz"`, `""`, `"cop"`, `"XX"` → `422`. `BudgetResponse` redeclara `currency` sin
  patrón para tolerar filas heredadas.
- **Lápida del soft-delete (QA-024):** borrar un presupuesto recurrente (lógico) sirve de
  "lápida" para su período — `ensure_recurring_budgets_for_period` cuenta también las filas
  soft-deleted en el chequeo "ya hay fila para este período". Borrar = saltar ese mes; la
  recurrencia sigue en los meses siguientes (la fila borrada ya no es plantilla). Semántica
  explicada en el copy del confirm del frontend: "Se borra solo el de este mes; los meses
  siguientes se siguen generando."
- **Serie y corte de la recurrencia (flujo corto 2026-10-03):** una serie es el conjunto de
  presupuestos de un usuario con la misma categoría **y moneda**. La generación perezosa clona
  la fila activa más reciente de la serie en un período **estrictamente anterior** al pedido,
  y **solo si es recurrente**: la fila más reciente decide. Desmarcar `is_recurring` en un
  `PUT` (transición `True → False`) pone en `False`, en la misma transacción, las filas activas
  posteriores de la serie resultante (montos intactos, lápidas intactas); los meses anteriores
  no cambian. Volver a marcar (`PUT`) o crear una fila recurrente (`POST`) reinicia la serie.
  Consecuencia aceptada: un presupuesto manual no recurrente en un mes posterior también
  termina la serie desde ahí. Pedir un mes anterior al inicio de la serie no genera filas.
- **Validación de período en `PUT` (QA-023):** `month` 1–12, `year` 2020–2100, `currency`
  `^[A-Z]{3}$` — valores fuera de rango/patrón → `422`.

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
  parámetros es el mes actual. El rango es semiabierto `[día 1 00:00, fin)` — el mes en curso
  tiene techo "ahora" (una transacción con fecha futura del mismo mes no cuenta como gasto del
  mes) y un mes ya cerrado tiene como techo el primer instante del mes siguiente, **exclusivo**
  (Fase 31, Decisión B6 — antes era "hasta el último día a las 23:59:59", y un `<=` contra ese
  valor perdía cualquier instante con fracción de segundo después de esa marca, QA-019).
- `balances` es siempre el saldo **actual** (stock) de las cuentas, con independencia del mes
  consultado: no es un saldo histórico ni una foto del mes pedido.
- `monthly_flow_balance` es siempre ingreso real − gasto real en la moneda preferida, en
  cualquier mes — igual en el mes en curso que en un mes cerrado (Fase 31, Decisión B9, Q9).
  Nunca `null`: sin filas vale `0.00`, y puede ser negativo (a principio de mes, antes de
  cobrar — es un dato, no un error). `monthly_income` (el ingreso declarado por el usuario)
  **no participa de este cálculo**: es una referencia visual del frontend, sin ningún cómputo
  detrás. `monthly_flow_basis` se conserva en el contrato pero queda `deprecated` — siempre
  vale `"actual"` desde esta fase (antes tenía dos bases, `"declared"` en el mes en curso y
  `"actual"` en uno cerrado). En cualquier caso solo cuenta la moneda preferida: no hay
  conversión de moneda en ningún punto.
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

- **Validación de paginación (QA-025):** `GET /notifications` valida `skip` ≥ 0 y `limit`
  1–1000 (default 50). `limit=0`, negativo o `>1000` → `422`.