# Spec — Fase 25: Arquitectura — capa de servicios, tipos compartidos y deuda de tests

> Plan de implementación detallado para los 7 ítems (checkboxes) de Fase 25 del
> [ROADMAP](../ROADMAP.md) (sección "Fase 25 — Arquitectura: capa de servicios, tipos
> compartidos y deuda de tests", líneas 1017–1055 al momento de escribir esto — fusiona y
> retira de "Pendientes heredados de fases anteriores", líneas 1113 en adelante, los ítems que
> ambas secciones venían señalando por separado desde la auditoría del 2026-09-15,
> `CODE_REVIEW.md` raíz). Este documento no cambia el alcance ahí definido — lo desglosa en
> tareas ejecutables, con archivos concretos, snippets de código reales y decisiones de
> arquitectura numeradas, separadas explícitamente en Backend/Frontend por ítem, para que
> agentes `backend-engineer`/`frontend-engineer` distintos puedan tomar cada mitad en paralelo.
>
> **No implementa nada.** Ningún archivo del repositorio fuera de `docs/specs/fase_25_spec.md`
> fue modificado al producir este documento. Los hallazgos fueron verificados directamente
> contra el código el 2026-09-18: lectura completa de `backend/app/api/transactions.py`,
> `backend/app/core/budget_alerts.py`, `backend/app/core/notification_dispatch.py`,
> `backend/app/core/budget_recurrence.py`, `backend/app/schemas/schemas.py`,
> `backend/app/models/models.py`, `backend/app/api/budgets.py`, `backend/app/main.py`,
> `backend/app/core/security.py`, `backend/app/api/auth.py`, `backend/tests/conftest.py`,
> `backend/tests/test_transactions.py`, `backend/tests/test_accounts.py`,
> `backend/tests/test_budgets.py`, `frontend/lib/api.ts`, `frontend/lib/queryKeys.ts`,
> `frontend/docs/STATE_AND_FETCHING.md`, `frontend/lib/hooks/*.ts`, `frontend/hooks/*.ts`,
> `frontend/lib/utils.ts`, y un `grep` de blast radius sobre `from app.schemas import schemas`,
> `raise HTTPException`, `useQuery`/`queryKey` — no inferidos del texto del ROADMAP en
> aislado, ni de `docs/TODO.md` (que resume los mismos hallazgos de la auditoría, pero sin el
> detalle de línea que esta spec verifica de nuevo contra el código real).

Estado del repo al momento de escribir esto (2026-09-18): Fases 7–23 completas (Fase 24 —
correcciones de UX post-auditoría — está planeada pero no spec'd/implementada). Fase 25 es
puramente de arquitectura/mantenibilidad: no hay ningún cambio de producto ni de contrato de
API observable salvo lo que cada ítem declara explícitamente.

---

## Hallazgos de exploración que corrigen/precisan el ROADMAP

1. **Las líneas citadas por el ROADMAP para el delta contable son exactas.**
   `backend/app/api/transactions.py:186` (`crear_transaccion`), `:312`
   (`eliminar_transaccion`), `:393-395` (`actualizar_transaccion`) — verificado carácter por
   carácter contra el archivo real. El patrón es idéntico en las tres funciones: calcular
   `delta = monto si income, -monto si expense` y aplicarlo con un `UPDATE` SQL directo
   (`db.execute(update(models.Account)...)`), nunca un `cuenta.balance += delta` en el objeto
   ORM — ya usa el patrón atómico correcto, solo está copy-pasteado.

2. **`app/core/budget_alerts.py` sigue siendo la plantilla correcta para el ESTILO de
   servicio, pero el push real no vive ahí — mismo matiz que ya dejó `fase_23_spec.md`
   Hallazgo 4.** `budget_alerts.py` (funciones puras que reciben `db: Session` + primitivos —
   `user_id`, `category_id`, `month`, `year` — sin clase, sin estado propio) es exactamente el
   patrón a imitar para `app/services/ledger.py`. El envío de push/persistencia de avisos vive
   en `app/core/notification_dispatch.py` (extraído en Fase 14 §14.2), que `budget_alerts.py`
   importa. Para el propósito de esta fase (delta contable, no notificaciones) el archivo
   correcto a imitar sigue siendo `budget_alerts.py` — se anota el matiz solo para no repetir
   la confusión de nombres que Fase 23 ya corrigió una vez.

3. **`schemas.py` tiene 48 clases, no 49 — el ROADMAP se equivocó por una.**
   `grep -c "^class " backend/app/schemas/schemas.py` → 48. 462 líneas, confirmado exacto. No
   cambia ninguna decisión de esta spec (el plan de split de abajo cubre las 48 reales), se deja
   anotado por precisión.

4. **`models.py` tiene 13 clases, no 14** (`User, Account, Category, Transaction, Budget,
   HiddenCategory, RefreshToken, PasswordResetToken, EmailVerificationToken, IdempotencyKey,
   Notification, PushSubscription, ApiKey`). Mismo tipo de imprecisión menor que el Hallazgo 3,
   sin efecto: el ROADMAP ya marca el split de `models.py` como "no urgente" y esta spec no le
   asigna ninguna tarea (ver Out of scope).

5. **Blast radius real de partir `schemas.py`: exactamente 11 archivos, todos routers, cero
   tests.** `grep -rln "from app.schemas import schemas" backend/` devuelve
   `accounts.py, api_keys.py, auth.py, budgets.py, categories.py, dashboard.py,
   notifications.py, preferences.py, push.py, transactions.py, users.py` — los 11 routers de
   `backend/app/api/`, cada uno con exactamente esa forma de import (`from app.schemas import
   schemas`, después `schemas.Foo`). Ningún archivo de `backend/tests/` referencia `schemas.`
   directamente (los tests hablan HTTP contra `client`, nunca instancian un schema Pydantic a
   mano) — confirma que el split puede resolverse sin tocar ni un test.

6. **No hay ninguna dependencia cruzada entre las 48 clases de dominios distintos** — verificado
   leyendo el archivo completo. Ninguna clase de un dominio (ej. `TransactionResponse`) declara
   un campo tipado como una clase de otro dominio (ej. `AccountResponse`); todos los campos son
   primitivos, `Decimal`, `datetime`, o un `Enum` declarado en el mismo bloque. El único
   elemento verdaderamente compartido entre dominios es `_validate_password_strength` /
   `_COMMON_PASSWORDS` (usado por `UserCreate`, dominio "usuarios", y por
   `PasswordResetConfirm`, dominio "auth") y el genérico `PaginatedResponse[T]`. Esto significa
   que el split es un movimiento mecánico de bloques de texto, sin ningún reordenamiento ni
   riesgo de import circular entre los módulos nuevos.

7. **63 `raise HTTPException` en los routers, y dos de ellos son literalmente el mismo string
   duplicado dentro del mismo archivo que ya toca el ítem 25.1** — `grep -rc "raise
   HTTPException" backend/app/api/*.py` suma 63 (`transactions.py` solo: 18). Dentro de
   `transactions.py`, `"La cuenta especificada no existe o no te pertenece."` aparece dos veces
   idéntico (líneas 83 y 165) y `"La categoría especificada no existe o no tienes permisos para
   usarla."` aparece dos veces idéntico (líneas 178 y 390) — target concreto y de bajo riesgo
   para el "camino de adopción incremental" que pide el ROADMAP para la capa de excepciones,
   sin tocar los otros 45 `raise HTTPException` de los demás 10 routers.

8. **Existen DOS carpetas de hooks de frontend, con una convención ya establecida (no escrita
   en ningún doc) de qué va en cada una.** `frontend/hooks/` (`useNotifications.ts`,
   `usePersistedState.ts`, `useQueryParamState.ts`) — hooks genéricos de UI/estado local, sin
   `useQuery` de dominio salvo `useNotifications`. `frontend/lib/hooks/` (`useApiKeys.ts`,
   `useCurrentUser.ts`, `useEscapeToClose.ts`, `useRequireAuth.ts`, `useSetMonthlyIncome.ts`,
   `useUserPreferences.ts`) — hooks de datos de servidor por dominio, ya con
   `useQuery`/`useMutation` + `queryKeys` + invalidación, exactamente el shape que piden
   `useAccounts`/`useCategories`/`useTransactions`. Los hooks nuevos van en `lib/hooks/`.

9. **El patrón duplicado es real y más extendido de lo que sugiere la lista de 3 hooks del
   ROADMAP.** `grep -rln "queryKeys.accounts.all()"` devuelve 11 archivos (`accounts/page.tsx`,
   `accounts/[id]/page.tsx`, `transactions/page.tsx`, `budgets/page.tsx`, `settings/page.tsx`,
   `analytics/page.tsx`, `categories/[id]/page.tsx`, `TransactionCaptureForm.tsx`,
   `TransactionModal.tsx`, `OnboardingIncomeStep.tsx`) con el mismo bloque literal
   `useQuery({ queryKey: queryKeys.accounts.all(), queryFn: async () => (await
   api.get('accounts/')).data })`. `queryKeys.categories.all()` se repite en 8 archivos con el
   mismo patrón. `useTransactions` es el caso más complejo: `transactions/page.tsx` es el único
   consumidor real de la lista paginada con filtros — no hay 11 copias de ese, solo 1, así que
   el hook de transacciones vale menos por deduplicación y más por consistencia con los otros
   dos.

10. **La migración de JWT a cookies `httpOnly` no es un cambio aislado de `lib/api.ts` — toca
    el único mecanismo de auth por header que hoy conviven dos formas de credencial.**
    `backend/app/core/security.py:108-130` (`get_current_user`) ya bifurca: si el token
    empieza con `oikos_pat_` es una API key (Fase 16, usada por Shortcuts de iOS y otras
    automatizaciones — nunca pasa por el navegador ni por `lib/api.ts`), si no, se decodifica
    como JWT del header `Authorization: Bearer`. Una migración a cookies para el JWT del
    navegador **no puede tocar el camino de API key** — tiene que seguir aceptando
    `Authorization: Bearer oikos_pat_...` exactamente igual. Además, no existe ningún mecanismo
    de CSRF en el repo hoy (`grep` sobre `csrf`/`CSRF`/`X-CSRF` en `backend/` y `frontend/` no
    devuelve nada) — pasar de "el JS arma el header" a "el navegador manda la cookie sola en
    cada request al dominio" abre una superficie nueva que hoy no existe y que ningún ítem
    anterior del proyecto diseñó.

11. **`frontend`/`backend` corren en orígenes distintos en el despliegue real — confirmado
    contra `docker-compose.yml`, no asumido.** Backend expone `8000:8000`, frontend
    `3000:3000`, `NEXT_PUBLIC_API_URL` default `http://100.76.235.30:8000` (Tailscale IP) y
    `ALLOWED_ORIGINS` default `http://localhost:3000,http://100.76.235.30:3000` — incluso bajo
    el mismo host, son orígenes distintos por puerto. `backend/app/main.py:140-146` ya tiene
    `allow_credentials=True` en `CORSMiddleware` (necesario hoy solo porque `allow_origins` es
    una lista explícita, no `"*"`) — la pieza de CORS que cookies cross-port necesitan
    (`Access-Control-Allow-Credentials`, origen explícito, no wildcard) ya está, lo que falta es
    todo lo demás (ver Decisión J en la sección de abajo).

12. **`test_budgets.py::TestRecurringBudgets` (líneas 152-271) cubre bastante más de lo que
    sugiere la frase del ROADMAP — la brecha real es más angosta y distinta.** El ROADMAP dice
    "`test_budgets.py` solo verifica que el flag `is_recurring` sobreviva el round-trip; nunca
    ejercita la función de generación de períodos directamente" — la primera mitad es
    imprecisa: los 6 tests de esa clase SÍ ejercitan generación de períodos end-to-end vía HTTP
    (rollover mes a mes, no-regeneración de plantillas no-recurrentes, "la plantilla más
    reciente se usa para clonar", no-duplicado en pedidos repetidos). La segunda mitad es
    exacta y es la brecha real: **ningún test llama `ensure_recurring_budgets_for_period`
    directamente** (todos pasan por `GET /budgets/` o `GET /dashboard/budgets-progress`, que la
    invocan como side-effect) — y dos escenarios concretos de la función nunca se ejercitan ni
    siquiera indirectamente: **salto de año** (`budget_recurrence.py` no tiene ningún caso
    especial diciembre→enero, pero tampoco hay ningún test que lo confirme) y **la rama de
    `IntegrityError`/rollback bajo carrera** (`budget_recurrence.py:66-73`, nunca ejercitada).

---

## Decisiones de arquitectura (evaluadas por `software-architect` el 2026-09-18)

### 25.1 — Extracción del delta contable a `app/services/ledger.py` (L1–L6)

**L1 — `app/services/` nace con un único módulo, `ledger.py`, cuatro funciones puras (`db:
Session` + primitivos, nunca ORM completo ni clases) — mismo estilo que `budget_alerts.py`
(Hallazgo 2), primer módulo real de la carpeta que el ROADMAP pide poblar con el código de
mayor riesgo primero.**

```python
# backend/app/services/ledger.py
"""Delta contable compartido entre crear/actualizar/eliminar transacción (Fase 25 §25.1).

Antes de esta extracción, el signo del delta (income → +monto, expense → -monto) y el
UPDATE atómico de Account.balance estaban copy-pasteados tres veces en
app/api/transactions.py (líneas 186, 312, 393-395). Mismo criterio de "función pura +
db: Session + primitivos, sin estado propio" que ya usa app/core/budget_alerts.py — el
patrón de servicio ad-hoc de este repo, no una capa nueva inventada desde cero.

Los routers siguen siendo dueños de la transacción SQL (dónde arranca el try/except,
cuándo se hace db.commit()) — estas funciones solo ejecutan los UPDATEs, nunca comitean
ni hacen rollback por su cuenta (Decisión L2).
"""

from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import models


def delta_para(tipo: str, monto: Decimal) -> Decimal:
    """Signo del impacto contable: `income` suma, `expense` resta."""
    return monto if tipo == "income" else -monto


def aplicar_delta(db: Session, account_id: int, delta: Decimal) -> None:
    """UPDATE atómico de Account.balance, SQL puro (no read-modify-write ORM) — mismo
    filtro deleted_at IS NULL que las tres funciones originales ya usaban para no mutar
    el saldo de una cuenta soft-deleted (Decisión 6.1)."""
    db.execute(
        update(models.Account)
        .where(models.Account.id == account_id, models.Account.deleted_at.is_(None))
        .values(balance=models.Account.balance + delta)
    )


def registrar_impacto(db: Session, account_id: int, tipo: str, monto: Decimal) -> None:
    """Aplica el impacto de una transacción NUEVA (crear_transaccion)."""
    aplicar_delta(db, account_id, delta_para(tipo, monto))


def revertir_impacto(db: Session, account_id: int, tipo: str, monto: Decimal) -> None:
    """Revierte el impacto de una transacción borrada (eliminar_transaccion) — inverso
    exacto de registrar_impacto sobre el mismo (tipo, monto)."""
    aplicar_delta(db, account_id, -delta_para(tipo, monto))


def aplicar_edicion(
    db: Session,
    *,
    cuenta_vieja_id: int,
    cuenta_nueva_id: int,
    tipo_viejo: str,
    monto_viejo: Decimal,
    tipo_nuevo: str,
    monto_nuevo: Decimal,
) -> None:
    """Recalcula el impacto de una transacción editada (actualizar_transaccion).

    Misma cuenta: un solo UPDATE con el delta neto (evita dos escrituras que se pisan).
    Cuenta distinta (el usuario movió el gasto/ingreso a otra cuenta): revierte el
    impacto viejo en la cuenta origen y aplica el nuevo en la cuenta destino — mismo
    comportamiento ya verificado por
    test_update_moving_to_different_currency_account_updates_currency
    (backend/tests/test_transactions.py:401-433, Fase 11 §11.2)."""
    old_delta = delta_para(tipo_viejo, monto_viejo)
    new_delta = delta_para(tipo_nuevo, monto_nuevo)
    if cuenta_vieja_id == cuenta_nueva_id:
        aplicar_delta(db, cuenta_vieja_id, new_delta - old_delta)
    else:
        aplicar_delta(db, cuenta_vieja_id, -old_delta)
        aplicar_delta(db, cuenta_nueva_id, new_delta)
```

**L2 — El commit/try-except sigue viviendo en el router, sin cambios de atomicidad.** La
extracción es deliberadamente angosta: solo el cálculo del delta y el `UPDATE` — no el
`try/except` + `db.commit()`/`db.rollback()` que hoy envuelve cada bloque (en `crear_
transaccion` ese `try` también cubre el flujo de idempotencia, que no es responsabilidad del
ledger). Mover el manejo de errores al servicio mezclaría dos preocupaciones (contabilidad +
idempotencia HTTP) que hoy están deliberadamente juntas por una razón (Decisión 10.4.4 de Fase
10: "Transaction + saldo + bitácora comparten UN solo commit"). El único cambio de
`transactions.py` es reemplazar las líneas de `update(...)`/delta por una llamada a la función
de `ledger.py` correspondiente, dentro del mismo bloque `try` que ya existe.

- *Alternativa descartada:* que `ledger.py` haga su propio `db.commit()`. Rompería la
  atomicidad de Fase 10 (idempotencia + saldo en un solo commit) y obligaría a los tres
  callers a coordinar dos transacciones separadas — exactamente el tipo de problema que la
  Decisión A5 de Fase 22 ya evitó a propósito para otro caso.

**L3 — `currency` NO se mueve a `ledger.py`.** El ROADMAP pide extraer "el delta contable", no
toda la lógica de mutación de una transacción. La asignación `nueva_transaccion.currency =
cuenta.currency` / `transaccion_db.currency = cuenta_nueva.currency` (el fix de Fase 11 §11.2
que corrigió el bug de moneda al mover una transacción entre cuentas) es un campo derivado, no
un cálculo de saldo — se queda en el router, sin cambios, justo al lado de donde ya está.

**L4 — `crear_transaccion` llama `ledger.registrar_impacto(db, cuenta.id, transaccion.type,
transaccion.amount)` en el lugar exacto donde hoy calcula `delta` y ejecuta el `update()`
(línea 186-201).** `eliminar_transaccion` llama `ledger.revertir_impacto(db, transaccion.
account_id, transaccion.type, transaccion.amount)` en el lugar de las líneas 311-320.
`actualizar_transaccion` llama `ledger.aplicar_edicion(db, cuenta_vieja_id=cuenta_vieja.id,
cuenta_nueva_id=cuenta_nueva.id, tipo_viejo=transaccion_db.type, monto_viejo=transaccion_db.
amount, tipo_nuevo=transaccion_actualizada.type, monto_nuevo=transaccion_actualizada.amount)`
en el lugar de las líneas 393-425 (reemplaza el `if cuenta_vieja.id == cuenta_nueva.id: ... else:
...` completo).

```python
# backend/app/api/transactions.py — crear_transaccion, reemplaza líneas 185-201
    # 🧮 3. Lógica Contable: Actualizar saldo de forma atómica en SQL (Fase 25 §25.1 —
    # antes duplicada acá y en eliminar_transaccion/actualizar_transaccion).
    try:
        db.add(nueva_transaccion)
        ledger.registrar_impacto(db, transaccion.account_id, transaccion.type, transaccion.amount)
        # ...resto del try (idempotency_key, db.commit(), db.refresh()) sin cambios...
```

```python
# backend/app/api/transactions.py — eliminar_transaccion, reemplaza líneas 309-320
    # 🧮 2. Lógica Contable Inversa: Revertir el impacto de forma atómica (Fase 25 §25.1)
    if cuenta:
        ledger.revertir_impacto(db, transaccion.account_id, transaccion.type, transaccion.amount)
```

```python
# backend/app/api/transactions.py — actualizar_transaccion, reemplaza líneas 393-425
    try:
        ledger.aplicar_edicion(
            db,
            cuenta_vieja_id=cuenta_vieja.id,
            cuenta_nueva_id=cuenta_nueva.id,
            tipo_viejo=transaccion_db.type,
            monto_viejo=transaccion_db.amount,
            tipo_nuevo=transaccion_actualizada.type,
            monto_nuevo=transaccion_actualizada.amount,
        )

        transaccion_db.amount = transaccion_actualizada.amount
        # ...resto sin cambios (type, description, account_id, category_id, currency,
        # payment_method, date, db.commit(), db.refresh())...
```

Import nuevo en `transactions.py`: `from app.services import ledger`.

**L5 — Hallazgo colateral, anotado pero fuera de alcance de este ítem: `aplicar_delta` no
verifica `rowcount`.** El `UPDATE ... WHERE id = :id AND deleted_at IS NULL` puede afectar 0
filas (si la cuenta fue soft-deleted entre el `SELECT` de verificación de pertenencia y este
`UPDATE`) sin que nada lo note — el comportamiento es idéntico al código actual (esta spec
extrae el código tal cual está, no lo corrige) y la ventana de carrera es la misma que ya existe
hoy. Se deja documentado para una futura fase de integridad de datos, no como tarea de Fase 25
(el ROADMAP pide extraer, no corregir un bug no reportado y de blast radius desconocido).

**L6 — Testing: un archivo nuevo, `backend/tests/test_ledger.py`, unit-level contra las
funciones de `ledger.py` directamente (sin pasar por HTTP), más los tests HTTP existentes que
ya cubren el mismo comportamiento como regresión de caja negra.** Los tests HTTP no cambian ni
una línea — si el refactor es correcto, siguen pasando exactamente igual:
- `backend/tests/test_transactions.py::TestCreateTransactionAdjustsBalance` (líneas 31-108),
  `TestDeleteTransactionRevertsBalance` (110+), `TestUpdateTransactionAdjustsBalance` (173+),
  `test_update_moving_to_different_currency_account_updates_currency` (401-433).
- `backend/tests/test_accounts.py::TestOpeningBalance`, `test_groups_balances_by_currency`,
  `test_flow_balance_equals_income_minus_expense_in_account_currency`.

`test_ledger.py` nuevo, contra `db_session` directo (inserta `models.Account` a mano, sin pasar
por el endpoint — más rápido, aísla el cálculo puro):
- `registrar_impacto` con `tipo="income"` incrementa el balance en exactamente `monto`.
- `registrar_impacto` con `tipo="expense"` lo decrementa.
- `revertir_impacto` es el inverso exacto de `registrar_impacto` (aplicar y revertir el mismo
  `(tipo, monto)` deja el balance sin cambios).
- `aplicar_edicion` con `cuenta_vieja_id == cuenta_nueva_id` aplica solo el delta neto (un
  `UPDATE`, no dos).
- `aplicar_edicion` con cuentas distintas resta el `old_delta` de la vieja y suma el `new_delta`
  a la nueva (dos `UPDATE`s independientes).
- `aplicar_delta` sobre una cuenta con `deleted_at` no nulo no cambia su balance (mismo filtro
  que ya protegía el código original).

---

### 25.2 — Split de `schemas.py` por dominio (S1–S5)

**S1 — Diez módulos de dominio + un `common.py`, calcado del split ya existente de
`backend/app/api/` (un router por dominio).** Mapeo completo de las 48 clases (Hallazgo 3),
verificado contra el archivo real línea por línea:

| Archivo nuevo | Clases |
|---|---|
| `common.py` | `PaginatedResponse[T]`, `_COMMON_PASSWORDS`, `_validate_password_strength` (compartido entre `users.py` y `auth.py` de este mismo split) |
| `users.py` | `UserBase`, `UserCreate`, `UserResponse`, `PreferencesUpdate`, `UserProfileUpdate`, `UserDeleteRequest` |
| `transactions.py` | `TransactionType`, `PaymentMethod`, `TransactionBase`, `TransactionCreate`, `TransactionResponse` |
| `accounts.py` | `AccountType`, `AccountBase`, `AccountCreate`, `AccountUpdate`, `AccountResponse`, `AccountReconcileResponse`, `AccountMonthlySummary` |
| `categories.py` | `CategoryType`, `CategoryBase`, `CategoryCreate`, `CategoryResponse` |
| `budgets.py` | `BudgetBase`, `BudgetCreate`, `BudgetResponse` |
| `dashboard.py` | `BalanceByCurrency`, `DashboardSummary`, `BudgetProgress`, `CashflowData`, `CategoryDistributionData` |
| `auth.py` | `TokenResponse`, `RefreshRequest`, `LogoutRequest`, `PasswordResetRequest`, `ResendVerificationRequest`, `GoogleLoginRequest`, `PasswordResetConfirm` |
| `notifications.py` | `NotificationType`, `NotificationResponse`, `UnreadCountResponse` |
| `push.py` | `PushSubscriptionKeys`, `PushSubscriptionCreate`, `PushSubscriptionDelete`, `PushSubscriptionResponse` |
| `api_keys.py` | `ApiKeyCreate`, `ApiKeyCreateResponse`, `ApiKeyResponse` |

11 archivos de dominio (mismo nombre que su router equivalente en `app/api/`, salvo `common.py`
que no tiene contraparte) + `common.py` = 12 archivos nuevos bajo `backend/app/schemas/`.

**S2 — `backend/app/schemas/__init__.py` nuevo (vacío), mismo patrón que `app/api/__init__.py`
y `app/core/__init__.py` (ambos vacíos).** Hoy `backend/app/schemas/` NO tiene `__init__.py` —
funciona como paquete de namespace implícito de Python 3 (verificado: `ls -la` no lo muestra).
Es una inconsistencia preexistente frente a `api/`/`core/` (que sí lo tienen, vacío) — se
resuelve de paso al crear el paquete real, sin que sea el motivo del cambio.

**S3 — `backend/app/schemas/schemas.py` se queda como shim de compatibilidad, no se borra.**
Los 11 routers (Hallazgo 5) siguen haciendo `from app.schemas import schemas` seguido de
`schemas.Foo` — cero de esos 11 archivos cambia en este ítem. `schemas.py` pasa de contener las
48 clases a solo re-exportarlas desde los módulos de dominio nuevos:

```python
# backend/app/schemas/schemas.py — Fase 25 §25.2: shim de compatibilidad.
# Las 48 clases que antes vivían acá ahora están partidas por dominio (ver
# backend/app/schemas/{common,users,transactions,accounts,categories,budgets,
# dashboard,auth,notifications,push,api_keys}.py). Este archivo re-exporta todo bajo
# el mismo namespace `schemas.Foo` que los 11 routers de app/api/ ya usan
# (`from app.schemas import schemas`) — evita tocar esos 11 archivos en este ítem.
# Migrar los routers a importar directo del módulo de dominio (`from app.schemas.auth
# import TokenResponse`) queda como mejora oportunista futura, no parte de esta fase.
from app.schemas.common import PaginatedResponse
from app.schemas.users import (
    UserBase,
    UserCreate,
    UserResponse,
    PreferencesUpdate,
    UserProfileUpdate,
    UserDeleteRequest,
)
from app.schemas.transactions import (
    TransactionType,
    PaymentMethod,
    TransactionBase,
    TransactionCreate,
    TransactionResponse,
)
from app.schemas.accounts import (
    AccountType,
    AccountBase,
    AccountCreate,
    AccountUpdate,
    AccountResponse,
    AccountReconcileResponse,
    AccountMonthlySummary,
)
from app.schemas.categories import CategoryType, CategoryBase, CategoryCreate, CategoryResponse
from app.schemas.budgets import BudgetBase, BudgetCreate, BudgetResponse
from app.schemas.dashboard import (
    BalanceByCurrency,
    DashboardSummary,
    BudgetProgress,
    CashflowData,
    CategoryDistributionData,
)
from app.schemas.auth import (
    TokenResponse,
    RefreshRequest,
    LogoutRequest,
    PasswordResetRequest,
    ResendVerificationRequest,
    GoogleLoginRequest,
    PasswordResetConfirm,
)
from app.schemas.notifications import NotificationType, NotificationResponse, UnreadCountResponse
from app.schemas.push import (
    PushSubscriptionKeys,
    PushSubscriptionCreate,
    PushSubscriptionDelete,
    PushSubscriptionResponse,
)
from app.schemas.api_keys import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyResponse

__all__ = [
    "PaginatedResponse",
    "UserBase", "UserCreate", "UserResponse", "PreferencesUpdate", "UserProfileUpdate",
    "UserDeleteRequest",
    "TransactionType", "PaymentMethod", "TransactionBase", "TransactionCreate",
    "TransactionResponse",
    "AccountType", "AccountBase", "AccountCreate", "AccountUpdate", "AccountResponse",
    "AccountReconcileResponse", "AccountMonthlySummary",
    "CategoryType", "CategoryBase", "CategoryCreate", "CategoryResponse",
    "BudgetBase", "BudgetCreate", "BudgetResponse",
    "BalanceByCurrency", "DashboardSummary", "BudgetProgress", "CashflowData",
    "CategoryDistributionData",
    "TokenResponse", "RefreshRequest", "LogoutRequest", "PasswordResetRequest",
    "ResendVerificationRequest", "GoogleLoginRequest", "PasswordResetConfirm",
    "NotificationType", "NotificationResponse", "UnreadCountResponse",
    "PushSubscriptionKeys", "PushSubscriptionCreate", "PushSubscriptionDelete",
    "PushSubscriptionResponse",
    "ApiKeyCreate", "ApiKeyCreateResponse", "ApiKeyResponse",
]
```

`schemas.PaginatedResponse[schemas.TransactionResponse]` (usado en
`transactions.py::obtener_transacciones`) sigue funcionando idéntico: `PaginatedResponse` sigue
siendo el mismo objeto genérico, solo importado transitivamente.

- *Alternativa descartada:* migrar los 11 routers a importar directo de cada módulo de dominio
  (`from app.schemas.transactions import TransactionResponse`) en el mismo ítem. Es más
  "limpio" en el sentido de que elimina el shim, pero convierte un cambio de 1-2 días,
  mecánico y de riesgo cero, en un cambio que toca 11 archivos de rutas HTTP en producción —
  desproporcionado para lo que pide el ROADMAP. Queda anotado como mejora futura oportunista
  (Out of scope).

**S4 — `common.py` resuelve la única dependencia cruzada real (Hallazgo 6): `users.py` y
`auth.py` importan `_validate_password_strength`/`_COMMON_PASSWORDS` desde `common.py`, en vez
de duplicar la lista de 40 contraseñas comunes.**

```python
# backend/app/schemas/users.py (fragmento)
from app.schemas.common import _validate_password_strength

class UserCreate(UserBase):
    password: str = Field(..., min_length=10, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)
```

```python
# backend/app/schemas/auth.py (fragmento)
from app.schemas.common import _validate_password_strength

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)
```

**S5 — Sin migración de Alembic, sin cambio de contrato de API.** Es un movimiento de código
Python puro — ningún JSON de request/response cambia de forma, ninguna tabla cambia.

---

### 25.3 — Capa de excepciones de dominio, piloto acotado a `transactions.py` (X1–X4)

**X1 — El ROADMAP pide 1-2 semanas para "desacoplar `raise HTTPException` de las reglas de
negocio en los routers" — leído al pie de la letra, eso es reescribir los 63 `raise
HTTPException` de los 11 routers (Hallazgo 7). Esta spec NO hace eso: recomienda un piloto de
horas, acotado al mismo archivo que ya toca 25.1 (`transactions.py`), y deja el resto como
trabajo incremental futuro, ítem por ítem, fuera de esta fase.** Es la lectura literal de "un
camino de adopción incremental" que pide el enunciado de esta tarea — arrancar por el módulo de
mayor riesgo (mismo criterio que ya fijó el ROADMAP para 25.1), no por un rediseño total.

**X2 — `app/core/exceptions.py` nuevo: una excepción base `DomainError` + dos subclases para
los dos strings duplicados del Hallazgo 7.**

```python
# backend/app/core/exceptions.py
"""Excepciones de dominio, desacopladas de HTTPException (Fase 25 §25.3 — piloto).

Un router captura una condición de negocio (`la cuenta no existe o no es tuya`) sin
tener que saber en el mismo lugar que eso es un 404 HTTP — el mapeo status/detail vive
acá, una sola vez, y un único exception handler en main.py lo traduce a respuesta HTTP.
Piloto acotado a transactions.py (Decisión X1): no reemplaza los 61 `raise
HTTPException` restantes de los otros 10 routers en esta fase.
"""


class DomainError(Exception):
    """Base de cualquier error de reglas de negocio. Nunca se instancia directo."""

    status_code = 400
    detail = "Error de dominio."

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.detail
        super().__init__(self.detail)


class AccountNotFoundError(DomainError):
    status_code = 404
    detail = "La cuenta especificada no existe o no te pertenece."


class CategoryNotFoundError(DomainError):
    status_code = 404
    detail = "La categoría especificada no existe o no tienes permisos para usarla."
```

**X3 — Un único `exception_handler` en `main.py`, mismo patrón que el de `RateLimitExceeded`
que ya existe (línea 159), responde con el mismo shape `{"detail": "..."}` que ya produce
`HTTPException` — cero cambio observable para el frontend.** `frontend/lib/utils.ts::
getApiError` lee `error.response.data.detail` como string (verificado) — el handler nuevo debe
producir exactamente esa forma para no romper ningún toast de error existente.

```python
# backend/app/main.py
from starlette.responses import JSONResponse  # 🆕 (Response ya estaba importado)
from app.core.exceptions import DomainError  # 🆕

# ...

def _domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_exception_handler(DomainError, _domain_error_handler)  # 🆕 Fase 25 §25.3
```

**X4 — En `transactions.py`, los 4 sitios que hoy hacen `raise HTTPException(status_code=404,
detail="La cuenta...")`/`"La categoría..."` (líneas 83, 165, 178, 390) pasan a `raise
AccountNotFoundError()`/`raise CategoryNotFoundError()`.** Las otras dos ocurrencias del
archivo con texto distinto (`"La transacción no existe o no tienes permisos."` línea 304,
`"La nueva cuenta asignada no existe o no te pertenece."` línea 377) se dejan como
`HTTPException` sin cambios — no son duplicados, y este ítem es un piloto acotado (Decisión
X1), no una limpieza total del archivo.

```python
# backend/app/api/transactions.py — ejemplo en _resolver_cuenta (antes HTTPException)
from app.core.exceptions import AccountNotFoundError, CategoryNotFoundError  # 🆕

def _resolver_cuenta(db: Session, user_id: int, account_id: int | None) -> models.Account:
    if account_id is not None:
        cuenta = (
            db.query(models.Account).filter(models.Account.id == account_id, models.Account.user_id == user_id).first()
        )
        if not cuenta:
            raise AccountNotFoundError()  # 🔁 antes: raise HTTPException(404, "...")
        return cuenta
    # ...resto sin cambios...
```

- *Alternativa descartada:* aplicar la capa de excepciones a los 63 sitios de los 11 routers en
  esta misma fase. Es literalmente lo que el ROADMAP estima en 1-2 semanas — desproporcionado
  frente a los demás ítems de Fase 25 (todos de horas a 1-2 días) y sin ningún router bloqueado
  esperando por eso. Se deja como backlog incremental, un router a la vez, cuando ese router se
  toque por otra razón (mismo criterio de "no migrar oportunista" que ya usa Fase 16 §16.3 para
  los tipos generados de OpenAPI).

---

### 25.4 — Custom hooks de queries: `useAccounts`, `useCategories`, `useTransactions` (Q1–Q4)

**Q1 — Los tres hooks nuevos viven en `frontend/lib/hooks/` (Hallazgo 8), mismo shape que
`useApiKeys.ts`/`useCurrentUser.ts`: `useQuery`/`useMutation` envueltos, sin lógica de
componente.**

```ts
// frontend/lib/hooks/useAccounts.ts
'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { Account } from '@/types/api';

/** Lista de cuentas del usuario (`GET /accounts/`) — reemplaza el useQuery inline
 *  duplicado en 11 páginas/componentes (Fase 25 §25.4). */
export function useAccounts() {
  return useQuery({
    queryKey: queryKeys.accounts.all(),
    queryFn: async () => {
      const response = await api.get('accounts/');
      return response.data as Account[];
    },
  });
}
```

```ts
// frontend/lib/hooks/useCategories.ts
'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { Category } from '@/types/api';

/** Lista de categorías del usuario, incluye is_hidden (Fase 18) — GET /categories/. */
export function useCategories() {
  return useQuery({
    queryKey: queryKeys.categories.all(),
    queryFn: async () => {
      const response = await api.get('categories/');
      return response.data as Category[];
    },
  });
}
```

**Q2 — `useTransactions(filters)` recibe el mismo objeto `params` que hoy arma
`transactions/page.tsx` a mano, y lo pasa tal cual a `queryKeys.transactions.filtered(params)`
— no reinventa el shape de filtros, solo mueve el `useQuery` fuera del componente.**

```ts
// frontend/lib/hooks/useTransactions.ts
'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { PaginatedResponse, Transaction } from '@/types/api';

/** Feed paginado y filtrado de transacciones (`GET /transactions/`). `params` es el
 *  mismo objeto de query params que ya arma transactions/page.tsx (skip, limit,
 *  account_id, category_id, start_date, end_date) — Fase 25 §25.4. */
export function useTransactions(params: Record<string, unknown>) {
  return useQuery({
    queryKey: queryKeys.transactions.filtered(params),
    queryFn: async () => {
      const response = await api.get('transactions/', { params });
      return response.data as PaginatedResponse<Transaction>;
    },
  });
}
```

**Q3 — Solo se extraen las lecturas (`useQuery`), no las mutaciones (`useMutation` de
crear/editar/borrar cuenta/categoría/transacción).** Las mutaciones de cada página tienen
listas de invalidación distintas entre sí (ej. `accounts/page.tsx` invalida `accounts.
summary()` además de `accounts.all()`; `transactions/page.tsx` invalida 7 keys distintas
incluyendo `analytics-cashflow`/`analytics-categories`) — no son la misma duplicación
mecánica que las lecturas, y forzarlas a un hook compartido reabriría exactamente el tipo de
decisión de invalidación por página que `STATE_AND_FETCHING.md` ya documenta caso por caso.
Fuera de alcance de este ítem (el ROADMAP solo pide los tres hooks de lectura nombrados).

**Q4 — Migración de call sites: los 11 archivos que usan `queryKeys.accounts.all()` inline
pasan a `useAccounts()`; los 8 que usan `categories.all()` pasan a `useCategories()`; solo
`transactions/page.tsx` pasa a `useTransactions(params)`.** Cambio mecánico por archivo — cada
call site reemplaza su bloque `useQuery({ queryKey: ..., queryFn: ... })` por la llamada al
hook, sin tocar el resto de la lógica de la página. `TransactionModal.tsx` tiene una variante
con `enabled: isOpen` (línea 43-46) que el hook base no cubre — se le agrega un segundo
parámetro opcional `useAccounts({ enabled })` en ese caso puntual, o se deja ese único call site
sin migrar si no vale la pena la rama condicional por un solo consumidor (decisión de detalle
para el `frontend-engineer` que lo implemente, sin impacto arquitectónico).

**Archivos a modificar (Backend: ninguno):**
- `frontend/lib/hooks/useAccounts.ts` (nuevo), `useCategories.ts` (nuevo), `useTransactions.ts`
  (nuevo).
- Los 11 call sites de `accounts.all()`, los 8 de `categories.all()`, y `transactions/page.tsx`
  (ver Hallazgo 9 para la lista completa de archivos).

**Testing:** sin suite de frontend (`docs/TODO.md`, sigue en backlog). Verificación manual:
cada página que se migra sigue mostrando los mismos datos, las invalidaciones de sus propias
mutaciones (sin cambios, Decisión Q3) siguen disparando refetch como antes.

**Criterio de aceptación:**
- Los 3 hooks nuevos existen en `frontend/lib/hooks/` con la misma `queryKey`/`queryFn` que ya
  usaban los call sites migrados — ningún comportamiento de cacheo cambia.
- Ningún archivo de `backend/` cambia por este ítem.
- Las mutaciones de cada página siguen invalidando exactamente las mismas keys que antes.

---

### 25.5 — JWT de `localStorage` a cookies `httpOnly` (J1–J8) — ⚠️ scope flag

**J1 — Recomendación: este sub-ítem NO se implementa dentro de Fase 25. Se documenta el diseño
aquí (para no perder el análisis ya hecho) y se recomienda un spec propio y dedicado (Fase 26 o
equivalente) antes de tocar código.** Motivo, con evidencia concreta (no solo "es grande"):

- El propio ROADMAP lo estima en 1-2 semanas — igual o mayor que la suma de los otros 6 ítems
  de esta fase combinados (Hallazgo 10-11). Empaquetarlo como "un ítem más" de Fase 25 rompe la
  premisa de que los ítems de una fase pueden ejecutarse en paralelo por agentes distintos: este
  ítem, si se hiciera, bloquearía o sería bloqueado por cualquier trabajo simultáneo sobre auth.
- Toca **todo** el flujo autenticado de la app en producción, con usuarios reales ya activos
  (`alejomaringomez2004@gmail.com` vía Google, más la cuenta de pruebas) — un error de
  `SameSite`/`Secure`/CORS deja a todo el mundo deslogueado o, peor, abre una superficie CSRF
  nueva en una app que hoy no tiene ninguna (Hallazgo 10). No es el tipo de cambio que conviene
  aterrizar en el mismo lote que 6 ítems de refactor de bajo riesgo.
- No hay suite de tests de frontend (`docs/TODO.md`, confirmado sin cambios) ni tests E2E — la
  única red de seguridad para un cambio de esta superficie es verificación manual, lo que pide
  más cautela en el secuenciamiento, no menos.
- Interactúa con un mecanismo que YA funciona y que este cambio no debe romper: las API keys de
  Fase 16 (`Authorization: Bearer oikos_pat_...`, usadas por Shortcuts de iOS reales) no pasan
  por cookies ni por `lib/api.ts` — cualquier diseño tiene que probar explícitamente que ese
  camino queda intacto.

El resto de esta sección (J2-J8) es el diseño de referencia para cuando se decida ejecutarlo —
no una tarea de esta fase.

**J2 — Diseño de referencia, backend: `POST /auth/login`, `/auth/google` y `/auth/refresh`
además de devolver `TokenResponse` en el body (compatibilidad con clientes no-browser, ej.
`curl`/Postman/futuros clientes API), setean dos cookies en la respuesta:**
- `access_token`: `HttpOnly`, `Secure`, `SameSite=Lax` (mismo registrable domain, distinto
  puerto — `Lax` alcanza; no hace falta `None` porque no hay tercero involucrado), `Max-Age`
  igual al TTL del JWT (15 min).
- `refresh_token`: mismos flags, `Path=/api/v1/auth/refresh` (acotado, no viaja en cada
  request), `Max-Age` 30 días.

**J3 — `get_current_user` (`backend/app/core/security.py:108`) gana un tercer camino: si no
hay header `Authorization`, intenta leer el JWT de la cookie `access_token` antes de fallar con
401.** El camino de API key (`oikos_pat_` por header) y el de JWT por header (compatibilidad,
clientes no-browser) quedan sin cambios — la cookie es un fallback, no un reemplazo del header.

**J4 — CSRF: patrón *double-submit cookie*, no tokens server-side con estado.** Al loguear, el
backend también setea una cookie NO-`httpOnly` `csrf_token` (valor aleatorio); el frontend la
lee y la manda en un header custom (`X-CSRF-Token`) en cada mutación; un middleware nuevo
rechaza `POST`/`PUT`/`PATCH`/`DELETE` si el header no coincide con la cookie. Es el patrón más
barato de operar para un solo backend stateless (sin Redis/sesión server-side, consistente con
la escala actual del proyecto — mismo criterio que ya usa Fase 7 para no montar una blacklist de
JWT).

**J5 — `frontend/lib/api.ts`: se agrega `withCredentials: true` al cliente Axios, se elimina
toda lectura/escritura de `localStorage.getItem('jwt_token')`/`'refresh_token'` y el interceptor
de request que arma `Authorization: Bearer`.** El interceptor de respuesta 401 (mutex/cola de
refresh, líneas 29-83) se simplifica: ya no necesita leer/reescribir tokens manualmente, solo
reintentar la request original tras un `POST /auth/refresh` (que ahora rota la cookie sola);
mismo mutex para no disparar refresh duplicados bajo 401s concurrentes.

**J6 — Logout: `POST /auth/logout` limpia ambas cookies (`Set-Cookie` con `Max-Age=0`) además
de revocar el refresh token en DB (sin cambios en esa parte).**

**J7 — Mobile shortcuts / API keys: sin cambios, verificado explícitamente por un test nuevo**
que confirma que `Authorization: Bearer oikos_pat_...` sigue autenticando sin ninguna cookie
presente — regresión directa contra el Hallazgo 10.

**J8 — Alcance de la migración: SOLO `lib/api.ts` y el flujo de tokens — NO Google OAuth
(`GoogleAuthButton.tsx` sigue devolviendo un ID token que se manda una vez a `POST
/auth/google`; lo que cambia es qué hace esa respuesta con el `TokenResponse`, no el flujo de
Google Identity Services en sí).**

---

### 25.6 — Actualizar `frontend/docs/STATE_AND_FETCHING.md` (M1–M2)

**M1 — Gap real confirmado contra `frontend/lib/queryKeys.ts` (61 líneas) vs. lo documentado —
más preciso que la lista del ROADMAP.** Claves que existen en el código y NO aparecen en
`STATE_AND_FETCHING.md` hoy:
- `userPreferences` (`queryKeys.userPreferences()`, usada desde Fase 21/22 por
  `useUserPreferences.ts` y `settings/page.tsx`).
- `account-monthly-summary`, `account-category-breakdown`, `account-budgets-progress`
  (`queryKeys.accounts.monthlySummary/categoryBreakdown/budgetsProgress`, todas por-cuenta,
  Fase 17 §17.1).
- Los params `accountId`/`currency` de `analytics.cashflow`/`analytics.categories` (Fase 17,
  ampliados después) — hoy el doc solo lista `analytics-cashflow`/`analytics-categories` sin
  mencionar que la key incluye esos dos segmentos adicionales opcionales.
- Las invalidaciones de mutations de Settings (Fase 21/22): `useUserPreferences.ts` invalida
  `userPreferences()`, `currentUser()`, `dashboard.categoryBreakdown()` y, condicionalmente,
  `accounts.all()` (Decisión 22.1.6 de `fase_22_spec.md`) — ninguna de esas reglas está en el
  doc.

**M2 — Corrección: NO existe una key separada para "categorías ocultas".** El ROADMAP menciona
"keys de categorías ocultas" como algo pendiente de documentar — verificado contra
`categories/page.tsx:309` (`hiddenCategories = categories?.filter((c) => c.is_hidden)`):
`is_hidden` es un campo más de la respuesta de `GET /categories/`, filtrado client-side sobre
el mismo `queryKeys.categories.all()` que ya está documentado. No hay ninguna key nueva que
agregar por este punto — se corrige la instrucción del ROADMAP en vez de inventar una entrada
que no existe en el código.

**Archivos a modificar:** `frontend/docs/STATE_AND_FETCHING.md` (secciones "Query keys
utilizadas" y "Invalidation patterns") — agregar las entradas del Hallazgo M1, con una nota
aclaratoria sobre M2. Si el ítem 25.4 (hooks) ya está implementado quando se toque este doc,
también vale la pena una sección breve "Hooks compartidos" listando `useAccounts`/
`useCategories`/`useTransactions` junto a `useCurrentUser` (ya documentado) — no bloqueante,
oportunista.

---

### 25.7 — Test dedicado para `ensure_recurring_budgets_for_period` (R1–R4)

**R1 — Archivo nuevo `backend/tests/test_budget_recurrence.py`, llamando la función
directamente (`db_session` + `models.Budget` insertados a mano), no vía HTTP.** Complementa,
no reemplaza, los 6 tests HTTP ya existentes en `TestRecurringBudgets`
(`backend/tests/test_budgets.py:152-271`, Hallazgo 12) — esos se quedan intactos como cobertura
de caja negra del contrato HTTP.

**R2 — Casos nuevos que cierran la brecha real identificada en el Hallazgo 12** (no
duplicados de lo que ya cubre `test_budgets.py`):

```python
# backend/tests/test_budget_recurrence.py (fragmentos representativos)
from app.core.budget_recurrence import ensure_recurring_budgets_for_period
from app.models import models


class TestEnsureRecurringBudgetsForPeriod:
    def test_year_rollover_generates_row_in_january_from_december_template(self, db_session, test_user, make_category):
        categoria = make_category(...)  # vía fixture existente, o insert directo
        db_session.add(models.Budget(
            amount_limit=Decimal("500.00"), currency="COP", month=12, year=2029,
            is_recurring=True, user_id=test_user["id"], category_id=categoria["id"],
        ))
        db_session.commit()

        ensure_recurring_budgets_for_period(db_session, test_user["id"], month=1, year=2030)

        generado = db_session.query(models.Budget).filter(
            models.Budget.user_id == test_user["id"], models.Budget.month == 1, models.Budget.year == 2030,
        ).one()
        assert generado.amount_limit == Decimal("500.00")
        assert generado.is_recurring is True

    def test_most_recent_template_wins_across_a_gap_of_several_months(self, db_session, test_user, make_category):
        """La plantilla "más reciente" no tiene que ser la del mes inmediatamente
        anterior — si el usuario no abrió la app en varios meses, la más reciente
        sigue siendo la correcta (mas_reciente_por_categoria ordena por (year, month))."""
        categoria = make_category(...)
        db_session.add_all([
            models.Budget(amount_limit=Decimal("800.00"), currency="COP", month=1, year=2030,
                          is_recurring=True, user_id=test_user["id"], category_id=categoria["id"]),
            models.Budget(amount_limit=Decimal("1200.00"), currency="COP", month=3, year=2030,
                          is_recurring=True, user_id=test_user["id"], category_id=categoria["id"]),
        ])
        db_session.commit()

        ensure_recurring_budgets_for_period(db_session, test_user["id"], month=6, year=2030)

        generado = db_session.query(models.Budget).filter(
            models.Budget.user_id == test_user["id"], models.Budget.month == 6, models.Budget.year == 2030,
        ).one()
        assert generado.amount_limit == Decimal("1200.00")  # la de marzo, no la de enero

    def test_category_with_existing_non_recurring_row_in_target_period_is_skipped(self, db_session, test_user, make_category):
        """Si ya existe CUALQUIER fila (recurrente o no) para (categoría, período), no
        se genera una segunda — categorias_con_fila no distingue el origen de la fila."""
        categoria = make_category(...)
        db_session.add_all([
            models.Budget(amount_limit=Decimal("800.00"), currency="COP", month=1, year=2030,
                          is_recurring=True, user_id=test_user["id"], category_id=categoria["id"]),
            models.Budget(amount_limit=Decimal("50.00"), currency="COP", month=2, year=2030,
                          is_recurring=False, user_id=test_user["id"], category_id=categoria["id"]),
        ])
        db_session.commit()

        ensure_recurring_budgets_for_period(db_session, test_user["id"], month=2, year=2030)

        filas = db_session.query(models.Budget).filter(
            models.Budget.user_id == test_user["id"], models.Budget.month == 2, models.Budget.year == 2030,
        ).all()
        assert len(filas) == 1
        assert filas[0].amount_limit == Decimal("50.00")  # la manual, sin pisarla

    def test_two_categories_each_generate_independently_in_the_same_call(self, db_session, test_user, make_category):
        ...  # dos plantillas de categorías distintas → una llamada genera ambas filas

    def test_race_condition_integrity_error_rolls_back_without_raising(self, db_session, test_user, make_category, monkeypatch):
        """Simula la carrera de budget_recurrence.py:66-73: otra petición ya insertó la
        fila del período antes de que esta llamada llegue al commit. No debe propagar
        la excepción — el caller (evaluate_budget_thresholds_for_category) depende de
        que esto nunca tumbe una evaluación de umbral en curso."""
        categoria = make_category(...)
        db_session.add(models.Budget(
            amount_limit=Decimal("800.00"), currency="COP", month=1, year=2030,
            is_recurring=True, user_id=test_user["id"], category_id=categoria["id"],
        ))
        db_session.commit()

        # Pre-inserta la fila "ganadora" que la función más tarde también intentará crear,
        # forzando el choque contra el índice único parcial en su propio commit.
        db_session.add(models.Budget(
            amount_limit=Decimal("999.00"), currency="COP", month=2, year=2030,
            is_recurring=True, user_id=test_user["id"], category_id=categoria["id"],
        ))
        db_session.commit()

        ensure_recurring_budgets_for_period(db_session, test_user["id"], month=2, year=2030)  # no debe lanzar

        filas = db_session.query(models.Budget).filter(
            models.Budget.user_id == test_user["id"], models.Budget.month == 2, models.Budget.year == 2030,
        ).all()
        assert len(filas) == 1
        assert filas[0].amount_limit == Decimal("999.00")  # la que ya estaba, sin duplicar
```

**R3 — El caso "salto de año" del test R2 depende de que `Budget.month != month) | (Budget.year
!= year)` (`budget_recurrence.py:28`) ya sea agnóstico de año — verificado: el filtro compara
ambos campos independientemente, sin ninguna suposición de "mismo año". El test confirma el
comportamiento correcto que el código ya tiene, no corrige un bug — cierra la brecha de
cobertura que señala el Hallazgo 12, no un defecto nuevo.**

**R4 — El test de carrera (`test_race_condition_integrity_error_rolls_back_without_raising`)
depende del índice único parcial de `Budget` para forzar el `IntegrityError` real, no un mock.**
Si el índice no dispara con ese setup exacto en SQLite (motor de test), el test debe ajustarse
para monkeypatchear `db_session.commit` y lanzar `IntegrityError` a mano en la primera llamada
dentro de `ensure_recurring_budgets_for_period` — mismo criterio de contingencia que ya usó
`fase_23_spec.md` (Decisión P2) para el caso de `caplog`: si el mecanismo "real" no es viable
en el entorno de test, cae a una simulación explícita y se anota la limitación en un comentario,
sin bloquear el ítem por eso.

**Archivos a modificar:** `backend/tests/test_budget_recurrence.py` (nuevo). Ningún archivo de
`backend/app/` cambia — es un ítem 100% de tests sobre código ya existente y correcto.

**Testing:** `cd backend && pytest tests/test_budget_recurrence.py -v` y
`pytest tests/test_budgets.py -v` (sin cambios, deben seguir pasando).

**Criterio de aceptación:**
- `ensure_recurring_budgets_for_period` tiene cobertura unit-level directa, sin pasar por HTTP.
- El salto de año y la rama de `IntegrityError`/rollback quedan ejercitados por primera vez.
- Ningún test HTTP existente de `test_budgets.py` cambia.

---

## Orden de ejecución recomendado

```
1. Backend: app/services/ledger.py + wiring en transactions.py + test_ledger.py (§25.1)
   ── Primero por mandato explícito del ROADMAP ("empezando por el código de mayor riesgo,
      no por lo más fácil de extraer"). Sin dependencias de ningún otro ítem.

2. Backend: app/core/exceptions.py (piloto) + wiring en transactions.py + handler en
   main.py (§25.3)
   ── Depende de (1) solo en el sentido de "mismo archivo, mejor hacerlo en el mismo lote
      para no re-tocar transactions.py dos veces por separado" — no hay dependencia de
      código real entre ledger.py y exceptions.py. Puede ir en un commit separado del (1)
      dentro del mismo PR, o inmediatamente después.

3. Backend: split de schemas.py por dominio + shim de compatibilidad (§25.2)
   ── Completamente independiente de (1)/(2): no comparte ningún archivo con
      transactions.py, services/ ni core/exceptions.py. Puede empezar en paralelo desde
      el día 1, incluso por un agente backend distinto.

4. Backend: test_budget_recurrence.py (§25.7)
   ── Completamente independiente de (1)-(3): archivo de test nuevo, sin tocar ningún
      módulo de app/. Puede empezar en paralelo desde el día 1.

5. Frontend: useAccounts/useCategories/useTransactions + migración de call sites (§25.4)
   ── Independiente de todo el trabajo de backend. Puede empezar en paralelo desde el
      día 1, incluso antes que el backend.

6. Docs: frontend/docs/STATE_AND_FETCHING.md (§25.6)
   ── Independiente de (1)-(4). Oportunista hacerlo DESPUÉS de (5) para poder documentar
      los hooks nuevos en la misma pasada, pero no es una dependencia real — el gap de
      query keys que cierra ya existe hoy, con o sin (5).

7. NO EJECUTAR dentro de esta fase: JWT → cookies httpOnly (§25.5)
   ── Ver Decisión J1: recomendado como spec propio y dedicado (Fase 26), secuenciado
      después de que Fase 25 completa (1-6) esté en producción sin regresiones, no en
      paralelo con ellas — es el único ítem de esta fase con blast radius sobre TODO el
      tráfico autenticado de la app.
```

Los ítems (1)-(4) de backend no comparten archivos entre sí salvo (1)/(2) sobre
`transactions.py` (mismo archivo, sin colisión real de líneas — (1) toca los bloques de
`update()`, (2) toca los `raise HTTPException` de `_resolver_cuenta`/checks de pertenencia,
áreas disjuntas del archivo). (5) y (6) de frontend no tienen ninguna dependencia de (1)-(4).

---

## Resumen de archivos tocados por ítem

| Ítem | Backend | Frontend |
|---|---|---|
| 25.1 ledger | `app/services/__init__.py` (nuevo), `app/services/ledger.py` (nuevo), `api/transactions.py` (3 bloques reemplazados por llamadas a `ledger.*`), `tests/test_ledger.py` (nuevo) | — |
| 25.2 split schemas | `schemas/__init__.py` (nuevo), `schemas/{common,users,transactions,accounts,categories,budgets,dashboard,auth,notifications,push,api_keys}.py` (nuevos, 11 archivos), `schemas/schemas.py` (reducido a shim de re-exports) | — |
| 25.3 excepciones (piloto) | `core/exceptions.py` (nuevo), `api/transactions.py` (4 `raise HTTPException` → `AccountNotFoundError`/`CategoryNotFoundError`), `main.py` (handler nuevo) | — |
| 25.4 hooks de queries | — | `lib/hooks/useAccounts.ts` (nuevo), `useCategories.ts` (nuevo), `useTransactions.ts` (nuevo), 11 call sites de `accounts.all()`, 8 de `categories.all()`, `transactions/page.tsx` |
| 25.5 JWT → cookies | **No ejecutado en esta fase** — diseño documentado en J1-J8, implementación diferida a un spec propio | **No ejecutado en esta fase** |
| 25.6 docs STATE_AND_FETCHING | — | `docs/STATE_AND_FETCHING.md` |
| 25.7 test budget_recurrence | `tests/test_budget_recurrence.py` (nuevo) | — |
| Cruzando toda la fase | Sin cambios de contrato de API en ningún ítem ejecutado (25.1-25.3, 25.7 son refactors internos; 25.2 es un shim transparente) — no aplica la convención de `CLAUDE.md` sobre `API_REFERENCE.md`/`API_CONTRACT.md` | — |

---

## Out of scope

- **Migrar los 11 routers a importar directo de los módulos de dominio de `schemas/`** en vez
  de seguir pasando por el shim `schemas.py` (Decisión S3): mejora futura oportunista, no
  bloqueante — el shim ya da el 100% del beneficio de mantenibilidad (código organizado por
  dominio) sin el riesgo de tocar 11 archivos de rutas HTTP en producción en el mismo cambio.
- **Split de `models.py` por dominio**: el propio ROADMAP lo marca "no urgente" (Hallazgo 4,
  ya "bien encapsulado por clase") — sin tareas en esta spec.
- **Reescribir los 61 `raise HTTPException` restantes (de los 63 totales) fuera del piloto de
  `transactions.py`** con la capa de excepciones nueva: explícitamente diferido (Decisión X1) a
  trabajo incremental futuro, router por router, cuando cada uno se toque por otra razón.
- **Mutaciones (`useMutation`) de cuentas/categorías/transacciones dentro de los hooks
  compartidos**: solo se extraen las lecturas (Decisión Q3) — las invalidaciones por página son
  demasiado heterogéneas para forzarlas a un hook único sin perder precisión.
- **Implementación real de JWT → cookies `httpOnly`** (§25.5): diseñado pero explícitamente NO
  ejecutado en esta fase — ver Decisión J1 y "Orden de ejecución recomendado", punto 7.
- **CI/CD, tests de frontend (Vitest/RTL), sincronización offline**: ya marcados "solo si el
  proyecto crece" en `docs/TODO.md` — sin relación directa con los 7 ítems de esta fase.
- **Corregir el hallazgo L5** (`aplicar_delta` no verifica `rowcount` bajo una carrera de
  soft-delete): documentado como hallazgo colateral de la extracción, no como tarea — el
  comportamiento es idéntico al código actual, no una regresión introducida por esta fase.

---

## Further notes

- Los 7 checkboxes de la sección "Fase 25" del ROADMAP (líneas 1029-1054) quedan cubiertos: 6
  con plan de ejecución directo dentro de esta fase (§25.1, §25.2, §25.3 piloto, §25.4, §25.6,
  §25.7) y 1 (§25.5, JWT → cookies) con diseño completo pero ejecución recomendada como spec
  propio — ver Decisión J1 para el razonamiento completo de por qué, con evidencia concreta del
  código (usuarios reales activos, ausencia de CSRF y de tests de frontend, interacción con
  API keys de Shortcuts) y no solo "es una tarea grande".
- Dos correcciones de precisión sobre el ROADMAP quedaron documentadas sin cambiar ninguna
  decisión de alcance: `schemas.py` tiene 48 clases (no 49, Hallazgo 3) y `models.py` tiene 13
  (no 14, Hallazgo 4). Una corrección que sí cambia el contenido de un ítem: no existe ninguna
  query key separada para "categorías ocultas" (Hallazgo/Decisión M2) — `is_hidden` es un campo
  más de `categories.all()`, filtrado client-side.
- El Hallazgo 12 corrige la premisa del ítem 25.7: `test_budgets.py::TestRecurringBudgets` ya
  cubre más generación de períodos de lo que sugiere la frase del ROADMAP vía HTTP — la brecha
  real y priorizada en R1-R4 es más angosta (llamadas directas a la función, salto de año, la
  rama de `IntegrityError`), no una reescritura de la cobertura existente.
- La secuencia recomendada agrupa 25.1 y 25.3 en el mismo archivo (`transactions.py`) a
  propósito, para no volver a tocarlo dos veces por separado — sin que eso implique una
  dependencia de código real entre `app/services/ledger.py` y `app/core/exceptions.py`.
- Ningún archivo del repositorio fuera de `docs/specs/fase_25_spec.md` fue modificado al
  producir este documento — sigue siendo, en su totalidad, un documento de planificación.
