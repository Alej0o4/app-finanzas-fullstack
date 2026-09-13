# Spec — Fase 21: Configuración de cuenta — moneda principal y baja de cuenta

> Plan de implementación detallado para los 2 ítems de Fase 21 del [ROADMAP](../ROADMAP.md).
> Fuente de verdad de alcance: `docs/ROADMAP.md` (sección "Fase 21 — Configuración de cuenta:
> moneda principal y baja de cuenta", decidida en sesión del 2026-09-13). Este documento no
> cambia el alcance ahí definido — lo desglosa en tareas ejecutables, con archivos concretos,
> esquemas y decisiones de diseño numeradas, separadas explícitamente en Backend/Frontend por
> ítem, para que agentes `backend-engineer`/`frontend-engineer` distintos puedan tomar cada
> mitad en paralelo.
>
> **No implementa nada.** Ningún archivo del repositorio fuera de `docs/specs/fase_21_spec.md`
> fue modificado al producir este documento. Los hallazgos de exploración de código fueron
> verificados directamente contra `backend/` y `frontend/` el 2026-09-13 (lectura completa de
> `models.py`, `users.py`, `preferences.py`, `security.py`, `database.py`, `seed.py`,
> `accounts.py`, `categories.py`, `auth.py`, `schemas.py`, `settings/page.tsx`,
> `useUserPreferences.ts`, `useSetMonthlyIncome.ts`, `queryKeys.ts`, `AppConfigProvider.tsx`,
> `dashboard/page.tsx`, `analytics/page.tsx`, `accounts/page.tsx`, `ModalShell.tsx`,
> `Input.tsx`, `useConfirmStore.ts`, `backend/docs/BUSINESS_RULES.md`,
> `frontend/docs/STATE_AND_FETCHING.md`), no inferidos del texto del ROADMAP. Las decisiones de
> arquitectura más delicadas (A1–A6, B1 abajo) fueron evaluadas por el agente
> `software-architect` a partir de ese mismo código, con cita de línea exacta.

Estado del repo al momento de escribir esto (2026-09-13): Fases 7–19 completas, más las dos
paradas de UX post-pivote/post-Fase 19. Fase 20 completó sus dos primeros ítems el mismo día
(plantilla de correo con marca, placeholders genéricos); el login con Google de esa fase queda
evaluado pero no implementado, y no se solapa con ningún archivo de Fase 21. Fase 21 es la
segunda fase decidida en la sesión del 2026-09-13, separada de Fase 20 a propósito por ser un
tema distinto (gestión de cuenta, no correos/login social).

---

## Hallazgos de exploración que corrigen/precisan el ROADMAP

1. **`run_seed()` ya tiene, hoy, un borrado en cascada de usuario escrito a mano — y está
   desactualizado, con un bug latente real.** `backend/app/core/seed.py:105-127` borra, en
   orden dictado por FKs: `Notification`, `PushSubscription`, `Budget`, `IdempotencyKey`,
   `Transaction`, `Account`, `Category`, `RefreshToken`, `PasswordResetToken`,
   `EmailVerificationToken`. **Faltan `ApiKey` (Fase 16, `models.py:309-340`) y
   `HiddenCategory` (Fase 18, `models.py:135-152`)** — ninguna de las dos existía cuando se
   escribió ese bloque. Volver a correr `run_seed()` hoy contra un usuario de prueba que alguna
   vez creó una API key o ocultó una categoría revienta con `IntegrityError` en el `db.delete
   (existing)` final, porque esas dos tablas siguen apuntando a un `user_id` (y, en el caso de
   `HiddenCategory`, también a un `category_id`) que la corrida anterior no limpió. Es
   exactamente el problema estructural que este ítem de Fase 21 debe resolver de raíz, no un
   detalle aislado del seed.

2. **`User` hereda `SoftDeleteMixin`, pero un soft-delete puro dejaría el email "libre" para
   re-registro mientras los datos huérfanos quedan para siempre.** `backend/app/core/
   database.py:29-38` (`SoftDeleteMixin`, solo puebla `deleted_at`) + `database.py:41-51` (el
   listener global `_filtrar_borrados_logicos`, que excluye automáticamente toda fila con
   `deleted_at IS NOT NULL` de **cualquier** `SELECT`, incluida la verificación de unicidad de
   email). `crear_usuario` (`backend/app/api/users.py:50`) hace
   `db.query(models.User).filter(models.User.email == normalized_email).first()` sin considerar
   `deleted_at` explícitamente — no hace falta, el listener ya lo hace por él. Consecuencia: si
   Fase 21 solo pusiera `deleted_at` en el usuario, un segundo registro con el mismo email
   pasaría ese check (el usuario viejo es invisible) y **colisionaría contra el índice único de
   `email` en la tabla real**, no contra un `400` limpio — un `IntegrityError` no manejado.
   Peor: ninguna de las tablas que cuelgan de un usuario (`Account`, `Transaction`, `Budget`,
   etc.) se libera nunca — incompatible con la motivación 2 del ROADMAP ("limpiar usuarios de
   prueba de la base").

3. **Ninguna FK hacia `users.id` tiene `ondelete=CASCADE`, confirmado en las 12 tablas que la
   referencian.** `Account.user_id` (`models.py:58`), `Category.user_id` (`:70`),
   `Transaction.user_id` (`:88`), `Budget.user_id` (`:109`), `HiddenCategory.user_id`/
   `category_id` (`:149-150`), `RefreshToken.user_id` (`:158`), `PasswordResetToken.user_id`
   (`:176`), `EmailVerificationToken.user_id` (`:194`), `IdempotencyKey.user_id`/
   `transaction_id` (`:213,216`), `Notification.user_id`/`budget_id` (`:233,242`),
   `PushSubscription.user_id` (`:294`), `ApiKey.user_id` (`:327`) — todas planas, sin
   `ondelete=`. Un `db.delete(user)` directo revienta con `IntegrityError` en la primera fila
   hija que encuentre. El borrado manual en orden de dependencia (como ya hace `seed.py`) es
   obligatorio, no una elección de estilo.

4. **No existe ningún endpoint que hoy pida reingresar la contraseña para una acción sobre la
   propia cuenta.** `actualizar_perfil` (`PATCH /users/me`, `users.py:106-117`) actualiza
   `monthly_income`/`full_name` sin pedir contraseña. El único lugar del código que verifica
   contraseña contra `password_hash` es `login()` (`backend/app/api/auth.py:20-27`,
   `security.verify_password`). Borrar la cuenta completa sería la primera acción destructiva e
   irreversible del sistema — las demás (borrar cuenta bancaria, categoría) tienen guards de
   "no si tiene datos asociados" (`docs/BUSINESS_RULES.md`, sección "Eliminaciones") pero son
   reversibles en el sentido de que no se pierde la sesión ni el resto de los datos.

5. **Una API key tiene, por diseño, los mismos permisos que el JWT de su dueño — incluido este
   endpoint nuevo si no se decide lo contrario.** `backend/docs/BUSINESS_RULES.md:11-14`: "no
   tiene scopes en v1... tiene los mismos permisos que el JWT de su dueño". Un atacante con una
   API key robada (de vida potencialmente indefinida, sin expiración obligatoria, ver
   `BUSINESS_RULES.md` sección API keys) podría invocar `DELETE /api/v1/users/me` igual que con
   un JWT robado de 15 minutos — la exigencia de contraseña (Decisión 21.2.1 abajo) cierra este
   vector para ambos casos por igual, sin necesitar un tratamiento especial para API keys.

6. **El selector de moneda no tiene ningún precedente de lista fija o `Enum` en todo el
   backend.** `grep` sobre `preferred_currency`/`currency` en `backend/app`: siempre
   `str`/`String(3)` con default `"COP"`, nunca validado contra una lista (`schemas.py:88,129,
   182,257`; `models.py:24,54`). Mismo criterio ya usado por la Decisión 17.2.4 del selector de
   moneda de presupuestos (`docs/specs/fase_17_spec.md` §17.2.4): derivar las opciones de las
   cuentas reales del usuario, no inventar una lista ni un `Enum` nuevo.

7. **Ya existe en el propio código un precedente exacto de qué invalidar cuando una mutación
   cambia un campo de `User` que otras pantallas leen — pero `useUserPreferences.ts` no lo
   sigue para `preferred_currency`.** `frontend/lib/hooks/useSetMonthlyIncome.ts:13-15`
   (mutación de `monthly_income`, otro campo de `User`) invalida **tanto**
   `queryKeys.currentUser()` **como** `queryKeys.dashboard.summary()` en su `onSuccess`.
   `frontend/lib/hooks/useUserPreferences.ts` (mutación de `preferred_currency` vía
   `PATCH /users/me/preferences`) solo invalida `queryKeys.userPreferences()`
   (líneas ~39-40) y nunca `queryKeys.currentUser()` — a pesar de que `user?.preferred_currency`
   (leído de la cache de `currentUser()`, no de `userPreferences()`) alimenta directamente
   `frontend/app/(dashboard)/page.tsx:43,75`, `accounts/page.tsx:185,241` y
   `analytics/page.tsx:170,349`.

8. **Ese gap tiene una consecuencia concreta y verificada: `dashboard/page.tsx` puede quedar
   mostrando el desglose por categoría en la moneda vieja indefinidamente tras cambiar la
   preferencia.** `frontend/app/(dashboard)/page.tsx:67-75`: la query
   `queryKeys.dashboard.categoryBreakdown()` (clave **fija**, sin moneda —
   `frontend/lib/queryKeys.ts:32-33`) llama `GET /dashboard/category-distribution` pasando
   `currency: user?.preferred_currency` como parámetro explícito. Como ni la clave cambia ni
   nada invalida esa query al cambiar la preferencia, TanStack Query no tiene motivo para
   volver a pedirla — sigue sirviendo, desde cache, los montos de la moneda anterior hasta un
   reload manual. Esto es justo lo que el ROADMAP pide investigar ("confirmar qué partes del
   dashboard dependen de esta preferencia para revalidar cache tras el cambio"), no una
   suposición. Por contraste, `GET /dashboard/summary` (`backend/app/api/dashboard.py:22-23`,
   `obtener_resumen`) lee `current_user.preferred_currency` **fresco desde la DB** en cada
   request (sin query param) — una vez que `queryKeys.dashboard.summary()` sí refetchea, sus
   datos son correctos; el problema ahí es solo de oportunidad, no de dato incorrecto servido
   desde cache. `analytics/page.tsx` no tiene este problema en absoluto: sus claves
   (`queryKeys.analytics.cashflow(...)`/`analytics.categories(...)`,
   `frontend/lib/queryKeys.ts` sección `analytics`) **sí** incluyen la moneda, así que
   cualquier cambio se autocorrige en cuanto `currentUser()` refresca (por `staleTime` de 1 min
   o remount).

---

## Decisiones de arquitectura (A1–A6, B1 — evaluadas por `software-architect` el 2026-09-13)

### Baja de cuenta (A1–A6)

- **A1 — Hard delete, tanto de `User` como de todo lo que posee.** La motivación 2 del ROADMAP
  ("limpiar usuarios de prueba de la base") es incompatible con soft-delete (Hallazgo 2): la
  fila y todo lo que cuelga de ella seguiría ocupando espacio para siempre, y el `IntegrityError`
  del email duplicado sería peor que el problema que se intenta resolver. Ninguna de las tablas
  hijas relevantes (`ApiKey`, `IdempotencyKey`, `HiddenCategory`) tiene `SoftDeleteMixin` de
  todos modos — hard delete es consistente con su diseño ya existente.
- **A2 — Función compartida `delete_user_cascade(db: Session, user: models.User) -> None`, en
  un módulo nuevo `backend/app/core/user_deletion.py`.** Toma el objeto `User` ya cargado (no un
  email) para que cada caller decida cómo lo encontró — el endpoint vía `current_user`, el
  script vía email — sin duplicar el `.filter(...).first()` dentro de la función compartida.
  Ver Decisión 21.2.2 para el orden exacto (extiende `seed.py:105-124`, insertando `ApiKey` y
  `HiddenCategory` en los puntos que sus FKs exigen).
- **A3 — `seed.py` se refactoriza en esta misma fase para llamar a `delete_user_cascade` en vez
  de repetir la lógica inline.** El bug de Hallazgo 1 ya es real y latente; dejar dos copias
  (una correcta en `user_deletion.py`, una vieja y desactualizada en `seed.py`) garantiza que
  vuelvan a desincronizarse en cuanto exista una tabla nueva con FK a `users.id`. Cambio
  puramente mecánico: reemplazar las ~10 líneas de `.delete()` de `seed.py:105-124` por una
  llamada a la función compartida.
- **A4 — `DELETE /api/v1/users/me` exige reingresar la contraseña en el body, y lleva rate
  limit 5/min.** Es la primera acción irreversible y total del sistema — todo lo demás en el
  proyecto es editable o recuperable (Hallazgo 4). El JWT de 15 min y las API keys de permisos
  equivalentes (Hallazgo 5) amplían la ventana de "sesión robada = cuenta borrada" lo bastante
  como para justificar el primer endpoint del proyecto que pide reconfirmación de contraseña —
  no es una convención rota, es la primera vez que la acción lo amerita. Verificación con
  `security.verify_password(plain, user.password_hash)`, mismo patrón que `login()`
  (`auth.py:27`); contraseña incorrecta devuelve `403` sin tocar ningún dato. Rate limit
  `@limiter.limit("5/minute")`, mismo decorador que `crear_usuario` (`users.py:47`).
- **A5 — Script de limpieza como invocación `python -c` de una línea, no un archivo nuevo bajo
  `scripts/`.** Mantiene la convención ya documentada en el `CLAUDE.md` raíz
  (`docker compose exec backend python -c "from app.core.seed import run_seed; run_seed()"`) en
  vez de introducir una segunda forma de correr management de Python justo cuando `scripts/` ya
  está reservado para shell (`backup.sh`/`restore.sh`). Firma:
  `delete_user_by_email(db: Session, email: str) -> bool` en el mismo `user_deletion.py` —
  resuelve el `User` por email (devuelve `False` si no existe, sin lanzar) y delega en
  `delete_user_cascade`.
- **A6 — Una sola transacción: todos los `.delete()` seguidos de un único `db.commit()` final,
  sin commits intermedios.** Mismo criterio que `crear_usuario` con la cuenta por defecto
  (`users.py:56-71`, "mismo commit... o existen ambos, o ninguno"): un fallo a mitad de la
  cascada (p. ej. una tabla nueva otra vez olvidada, el mismo bug de Hallazgo 1) debe dejar al
  usuario intacto, no a medio borrar. El endpoint envuelve la llamada en
  `try/except IntegrityError` (`db.rollback()` + `500`); el script deja que la excepción se
  propague sin capturarla — es un operador con acceso shell quien la ve, no un usuario final.

### Cache de moneda preferida (B1)

- **B1 — Invalidar `queryKeys.currentUser()` y `queryKeys.dashboard.categoryBreakdown()` (además
  de `queryKeys.userPreferences()`) cuando `preferred_currency` cambia; no ensanchar la clave de
  `categoryBreakdown()` con la moneda.** `currentUser()` es la fuente real de
  `user?.preferred_currency` que leen `dashboard/page.tsx`, `accounts/page.tsx` y
  `analytics/page.tsx` (Hallazgo 7) — nada la invalida hoy al cambiar preferencias, a pesar de
  que `useSetMonthlyIncome.ts:14` ya sienta el precedente exacto para otro campo de `User`. No
  ensanchar la clave de `categoryBreakdown()` con la moneda (a diferencia de `analytics.*`):
  la regla de `frontend/docs/STATE_AND_FETCHING.md` ("cada pantalla de negocio debe tener su
  propia queryKey") separa por pantalla, no por cada parámetro dentro de una pantalla — en
  Analítica la moneda es una dimensión que el usuario elige activamente por cuenta
  (`effectiveCurrency`, Fase 17), mientras que en el dashboard general es un efecto secundario
  de una preferencia de cuenta que cambia raramente, editada en una pantalla distinta
  (Settings). Invalidar explícitamente desde `useUserPreferences.ts` es más simple y no
  dispersa "esta query depende de currency" en la key misma.

---

## Orden de ejecución recomendado

```
1. Backend: delete_user_cascade() + refactor de seed.py (§21.2)
   ── Independiente de todo lo demás; corrige el bug latente de Hallazgo 1 antes de
      construir nada nuevo sobre el mismo patrón.

2. Backend: DELETE /api/v1/users/me + verificación de contraseña + rate limit (§21.2)
   ── Depende de (1): el endpoint es un wrapper delgado sobre delete_user_cascade().

3. Backend: script de limpieza delete_user_by_email() (§21.2)
   ── Depende de (1); trivial una vez que la función compartida existe. Puede ir en el
      mismo PR que (1)-(2).

4. Frontend: modal de confirmación con contraseña en Settings (§21.2)
   ── Depende de (2) para tener el endpoint real. Independiente de 5-6.

5. Frontend: fix de invalidación de cache en useUserPreferences.ts (§21.1)
   ── Independiente de 1-4; un solo hook, sin backend nuevo.

6. Frontend: selector de moneda en Settings (§21.1)
   ── Depende de (5) para que el cambio de moneda se refleje sin reload manual — construirla
      antes dejaría el bug de Hallazgo 8 visible en la propia feature nueva.
```

Los dos ítems del ROADMAP (21.1 moneda, 21.2 baja de cuenta) son líneas de trabajo
independientes que no comparten ningún archivo — mismo criterio que
`docs/specs/fase_19_spec.md` aplicó a sus tres ítems sin dependencia cruzada.

---

## 21.1 Selector de moneda principal en Settings

### Backend

**Sin cambios de backend.** `GET`/`PATCH /api/v1/users/me/preferences` (`backend/app/api/
preferences.py:12-38`) ya acepta y persiste `preferred_currency` sin restricción de valores
(`schemas.PreferencesUpdate.preferred_currency: str | None`, `schemas.py:99`) — el trabajo de
este ítem es 100% frontend: exponer el control que hoy no existe y cerrar el gap de cache del
Hallazgo 8.

### Frontend

**Decisión 21.1.1 — opciones del selector derivadas de `GET /accounts/`, mismo patrón que la
Decisión 17.2.4 del selector de moneda de presupuestos.** Ver Hallazgo 6: no hay precedente de
lista fija de monedas en el proyecto. Reutilizar `queryKeys.accounts.all()` (ya en cache si el
usuario visitó `/accounts` o `/budgets` antes, `staleTime` de 1 min) y derivar
`Array.from(new Set(accounts.map(a => a.currency)))`. Si el usuario tiene una sola moneda entre
sus cuentas, el selector igual se muestra con una sola opción — mismo criterio que
`budgets/page.tsx` ya estableció (no ocultar el campo condicionalmente).

**Decisión 21.1.2 — fix de invalidación en `useUserPreferences.ts` primero, selector después**
(ver orden de ejecución). El fix (B1) es un cambio de 4 líneas en el `onSuccess` existente,
condicionado a que el body incluya `preferred_currency`:

```ts
// frontend/lib/hooks/useUserPreferences.ts
onSuccess: (_data, body) => {
  queryClient.invalidateQueries({ queryKey: queryKeys.userPreferences() });

  if (body.preferred_currency) {
    queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() });
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.categoryBreakdown() });
  }
  if (body.preferred_theme) {
    updateConfig({ theme: body.preferred_theme });
  }
},
```

**Archivo a modificar:** `frontend/app/(dashboard)/settings/page.tsx`.

**Pasos:**
1. Nuevo `useQuery<Account[]>` para `accounts/` (mismo patrón que `budgets/page.tsx`, Decisión
   17.2.4):
   ```tsx
   const { data: accounts } = useQuery<Account[]>({
     queryKey: queryKeys.accounts.all(),
     queryFn: async () => (await api.get('accounts/')).data,
   });
   const availableCurrencies = Array.from(new Set(accounts?.map((a) => a.currency) ?? []));
   ```
2. Nueva sección en la página (entre "Resumen semanal" y "API keys", agrupada bajo un
   encabezado "Cuenta" o similar — mismo patrón visual `bg-surface border-border/70` que las
   otras dos `<section>` ya presentes), con un `<Select>` (mismo componente que
   `budgets/page.tsx` usa para su selector de moneda):
   ```tsx
   <Select
     label="Moneda principal"
     value={preferences?.preferred_currency ?? ''}
     onChange={(e) =>
       updatePreferences.mutate(
         { preferred_currency: e.target.value },
         { onError: (err) => toast.error(getApiError(err)) }
       )
     }
     disabled={updatePreferences.isPending}
     className="bg-background"
   >
     {availableCurrencies.map((c) => (
       <option key={c} value={c}>
         {c}
       </option>
     ))}
   </Select>
   ```
   Sin estado local ni botón "Guardar" — mismo patrón "cambio = guardado" que ya usa el
   `<Switch>` de resumen semanal en la misma página (`handleToggle`, líneas 41-54), no un
   formulario con submit separado.

**Archivos a modificar:**
- `frontend/lib/hooks/useUserPreferences.ts` (Decisión 21.1.2).
- `frontend/app/(dashboard)/settings/page.tsx` (pasos 1-2).

**Testing:** sin suite de frontend (igual que fases anteriores, `docs/TODO.md` "Tests de
frontend" sigue en backlog). Verificación manual: cambiar la moneda principal en Settings con
un usuario multi-moneda (ej. `test@test.com` del seed, cuentas COP y USD) y confirmar que el
desglose por categoría del dashboard (`/`) muestra los montos de la nueva moneda sin recargar
la página; confirmar que `formatCurrency` en el resto de la UI (símbolos, `CashflowChart`,
`CategoryDonutChart`) también refleja el cambio de inmediato (ya funcionaba antes de este
ítem, vía `AppConfigProvider` — no debe regresar).

**Criterio de aceptación:**
- Un usuario puede cambiar su moneda principal desde `/settings`, con opciones derivadas de
  sus propias cuentas.
- El dashboard (`/`) refleja el cambio de moneda en su desglose por categoría sin necesidad de
  recargar la página.
- El backend no gana ninguna validación de moneda nueva — sigue siendo una restricción de UI,
  mismo criterio que la Decisión 17.2.1 de Fase 17.

---

## 21.2 Baja de cuenta de usuario (self-service) + script de limpieza

### Backend

**Decisión 21.2.1 — nuevo módulo `backend/app/core/user_deletion.py`** con dos funciones:

```python
# backend/app/core/user_deletion.py
from sqlalchemy.orm import Session
from app.models import models


def delete_user_cascade(db: Session, user: models.User) -> None:
    """Borra físicamente un usuario y todo lo que le pertenece, en el orden que exigen
    las FKs (ninguna tiene ondelete=CASCADE — ver Hallazgo 3 de docs/specs/fase_21_spec.md).
    Una sola transacción: el caller hace el único db.commit() al final."""
    # HiddenCategory primero: referencia tanto users.id como categories.id, y Category
    # se borra más abajo en este mismo método (Decisión A2).
    db.query(models.HiddenCategory).filter(models.HiddenCategory.user_id == user.id).delete()
    db.query(models.Notification).filter(models.Notification.user_id == user.id).delete()
    db.query(models.PushSubscription).filter(models.PushSubscription.user_id == user.id).delete()
    db.query(models.ApiKey).filter(models.ApiKey.user_id == user.id).delete()
    db.query(models.Budget).filter(models.Budget.user_id == user.id).delete()
    # IdempotencyKey.transaction_id -> transactions.id: antes de Transaction.
    db.query(models.IdempotencyKey).filter(models.IdempotencyKey.user_id == user.id).delete()
    db.query(models.Transaction).filter(models.Transaction.user_id == user.id).delete()
    db.query(models.Account).filter(models.Account.user_id == user.id).delete()
    db.query(models.Category).filter(models.Category.user_id == user.id).delete()
    db.query(models.RefreshToken).filter(models.RefreshToken.user_id == user.id).delete()
    db.query(models.PasswordResetToken).filter(models.PasswordResetToken.user_id == user.id).delete()
    db.query(models.EmailVerificationToken).filter(
        models.EmailVerificationToken.user_id == user.id
    ).delete()
    db.delete(user)


def delete_user_by_email(db: Session, email: str) -> bool:
    """Wrapper para el script de limpieza (Decisión A5) — resuelve por email, no persigue
    la sesión de un usuario autenticado. Devuelve False si el email no existe, sin lanzar."""
    user = db.query(models.User).filter(models.User.email == email.lower().strip()).first()
    if user is None:
        return False
    delete_user_cascade(db, user)
    db.commit()
    return True
```

**Decisión 21.2.2 — orden de borrado (ver A2), extendiendo `seed.py:105-124` con `HiddenCategory`
y `ApiKey` en los puntos que sus FKs exigen** — ambas sin dependientes propios dentro del
alcance de un usuario, así que se insertan temprano (junto a `Notification`/
`PushSubscription`, mismo perfil de "bitácora/credencial técnica sin FKs salientes propias").

**Decisión 21.2.3 — `seed.py` se refactoriza para usar la función compartida (Decisión A3).**

**Archivo a modificar:** `backend/app/core/seed.py`, bloque `if existing:` (líneas 105-127):

```python
# backend/app/core/seed.py
from app.core.user_deletion import delete_user_cascade
# ...
if existing:
    delete_user_cascade(db, existing)
    db.flush()
```

Reemplaza las ~19 líneas actuales de `.delete()` inline — el comentario explicativo sobre
orden-por-FK se mueve a `user_deletion.py`, junto a la función que ahora lo implementa.

**Decisión 21.2.4 — `DELETE /api/v1/users/me`, en `users.py`, exige `password` en el body y
rate limit 5/min (ver A4).**

```python
# backend/app/schemas/schemas.py
class UserDeleteRequest(BaseModel):
    password: str


# backend/app/api/users.py
from sqlalchemy.exc import IntegrityError
from app.core.user_deletion import delete_user_cascade


@router.delete("/me", status_code=204)
@limiter.limit("5/minute")
def eliminar_cuenta_propia(
    request: Request,
    body: schemas.UserDeleteRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not security.verify_password(body.password, current_user.password_hash):
        raise HTTPException(status_code=403, detail="Contraseña incorrecta.")

    try:
        delete_user_cascade(db, current_user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="No se pudo eliminar la cuenta. Contactá soporte.",
        ) from None
```

Declarado junto a `PATCH /me` en `users.py` (mismo router, misma sección de "operaciones sobre
la propia cuenta"). No hay colisión de rutas con `/me/preferences` (router distinto,
`preferences.py`) ni con `/{user_id}` (no existe ningún endpoint así — todas las operaciones de
`users.py` son sobre `current_user`, nunca por ID arbitrario).

**Decisión 21.2.5 — script de limpieza vía `python -c` (Decisión A5), documentado en el
`CLAUDE.md` raíz junto al comando de seed existente:**

```sh
docker compose exec backend python -c "
from app.core.database import SessionLocal
from app.core.user_deletion import delete_user_by_email
db = SessionLocal()
try:
    print(delete_user_by_email(db, 'email@ejemplo.com'))
finally:
    db.close()
"
```

**Archivos a modificar:**
- `backend/app/core/user_deletion.py` (nuevo — Decisiones 21.2.1/21.2.2).
- `backend/app/core/seed.py` (Decisión 21.2.3).
- `backend/app/schemas/schemas.py` (`UserDeleteRequest`, Decisión 21.2.4).
- `backend/app/api/users.py` (`DELETE /me`, Decisión 21.2.4).
- Root `CLAUDE.md`, sección "Run (Docker, recommended)" — agregar el comando de limpieza junto
  al de seed existente (convención de `CLAUDE.md`: documentar comandos operativos ahí).

### Frontend

**Decisión 21.2.6 — modal dedicado con campo de contraseña, no `useConfirmStore`.**
`frontend/store/useConfirmStore.ts` (20 líneas) solo soporta mensaje + callback, sin campos de
formulario — insuficiente para pedir contraseña. Se construye un `ModalShell` propio (mismo
patrón que el modal de creación de API key ya presente en `settings/page.tsx:220-278`), con un
`Input type="password"` (`InputHTMLAttributes` nativo, `frontend/components/ui/Input.tsx:5`, sin
cambios necesarios al componente) y doble fricción: el botón de apertura dice "Eliminar mi
cuenta" (no "Eliminar"), y el submit del modal queda deshabilitado hasta que el campo de
contraseña tenga contenido — no hay un segundo paso de "escribir DELETE para confirmar" (no hay
precedente de ese patrón en el proyecto y la contraseña ya cumple la función de fricción
deliberada).

**Archivo a modificar:** `frontend/app/(dashboard)/settings/page.tsx`.

**Pasos:**
1. Nueva sección "Zona de peligro" al final de la página (después de "API keys"), con un solo
   botón `variant="danger"` (o `variant="ghost"` con clases `text-danger`, si no existe la
   variante — verificar `Button.tsx` en implementación) "Eliminar mi cuenta".
2. Nuevo estado local: `isDeleteOpen`, `password`, `passwordError`, mismo patrón que el modal de
   API key (`isCreateOpen`, `newKeyName`, `nameError`, líneas 62-76 actuales).
3. Nueva mutación:
   ```tsx
   const deleteAccount = useMutation({
     mutationFn: async (password: string) => {
       await api.delete('users/me', { data: { password } });
     },
     onSuccess: () => {
       localStorage.removeItem('jwt_token');
       localStorage.removeItem('refresh_token');
       queryClient.clear();
       toast.success('Tu cuenta fue eliminada.');
       router.push('/login');
     },
     onError: (err) => setPasswordError(getApiError(err)),
   });
   ```
   `queryClient.clear()` (no solo `invalidateQueries`) porque, a diferencia de un logout normal
   (`Sidebar.tsx`, que no limpia la cache de React Query — el próximo login la repuebla igual),
   aquí no debe quedar ningún dato del usuario borrado accesible ni por un instante en memoria
   si el navegador queda abierto.
4. Modal con `Input type="password"` + botón "Eliminar definitivamente" (`variant="danger"` o
   equivalente), deshabilitado mientras `password` esté vacío o `deleteAccount.isPending`. Texto
   de advertencia explícito: qué se borra (cuentas, transacciones, presupuestos, categorías
   propias) y que es irreversible.

**Archivos a modificar:**
- `frontend/app/(dashboard)/settings/page.tsx` (pasos 1-4).

**Testing:**

Backend (`backend/tests/test_users.py`, ya existe — extender, no crear archivo nuevo):
- `DELETE /users/me` con contraseña correcta: `204`, y un `GET /users/me` posterior con el
  mismo token devuelve `401` (el usuario ya no existe — `get_current_user`,
  `security.py:120-122`, hace `.first()` y lanza `credentials_exception` si es `None`).
- `DELETE /users/me` con contraseña incorrecta: `403`, y el usuario sigue existiendo
  (`GET /users/me` con el mismo token sigue devolviendo `200`).
- Usuario con datos en **todas** las tablas relevantes (cuentas, transacciones, presupuestos,
  categoría propia, categoría propia oculta vía `HiddenCategory`, una API key, un refresh
  token) — `DELETE /users/me` no lanza `IntegrityError` y ninguna fila hija sobrevive
  (verificar con querys directas a cada tabla filtradas por el `user_id` ya borrado).
- Tras eliminar la cuenta, un registro nuevo con el mismo email tiene éxito (`201`) — cierra el
  Hallazgo 2 explícitamente con un test, no solo con la implementación.
- `DELETE /users/me` sin token: `401` (guard estándar de `get_current_user`).

Backend (`backend/tests/test_seed.py`, si no existe crear uno mínimo, o inline en el módulo que
ya cubra `seed.py` — verificar primero): `run_seed()` corrido dos veces seguidas contra una base
donde el usuario de prueba ya tiene una API key y una categoría oculta no lanza `IntegrityError`
— regresión directa del Hallazgo 1.

Frontend: sin suite automatizada. Verificación manual: el flujo completo de borrado desde
`/settings` (contraseña incorrecta muestra error sin cerrar el modal; contraseña correcta borra
la cuenta, limpia localStorage y cache, y redirige a `/login`); intentar navegar hacia atrás
tras el borrado no debe mostrar datos de la cuenta eliminada (verifica que `queryClient.clear()`
realmente vació la cache, no solo la invalidó).

**Criterio de aceptación:**
- Un usuario puede eliminar su propia cuenta desde `/settings`, reingresando su contraseña.
- Contraseña incorrecta no borra nada y muestra un error claro.
- La eliminación es física (hard delete): ninguna fila del usuario ni de sus datos sobrevive en
  ninguna tabla, y el email queda disponible para un registro nuevo.
- El mismo mecanismo de borrado (`delete_user_cascade`) se usa desde el endpoint HTTP y desde el
  script de limpieza — sin lógica de cascada duplicada en ningún punto del código.
- `seed.py` puede correrse repetidamente sin `IntegrityError`, incluso contra un usuario de
  prueba que acumuló API keys y categorías ocultas en corridas anteriores.
- No se introduce ningún concepto de rol/admin nuevo — el script de limpieza sigue
  confiando en el acceso shell al deploy, mismo nivel de confianza que `run_seed()` o leer
  `.env` (decisión ya tomada en el ROADMAP, no reabierta aquí).

---

## Resumen de archivos tocados por ítem

| Ítem | Backend | Frontend |
|---|---|---|
| 21.1 moneda principal | — | `lib/hooks/useUserPreferences.ts` (fix de invalidación), `app/(dashboard)/settings/page.tsx` (selector nuevo) |
| 21.2 baja de cuenta | `core/user_deletion.py` (nuevo), `core/seed.py` (refactor), `schemas/schemas.py` (`UserDeleteRequest`), `api/users.py` (`DELETE /me`), `tests/test_users.py`, root `CLAUDE.md` (comando de limpieza) | `app/(dashboard)/settings/page.tsx` (modal de baja) |
| Cruzando toda la fase | — | Sin cambios de contrato de API compartido más allá de `DELETE /api/v1/users/me` (nuevo) — actualizar `backend/docs/API_REFERENCE.md` + `frontend/docs/API_CONTRACT.md` con ese endpoint (convención de `CLAUDE.md` sobre contratos de API compartidos) |

---

## Out of scope

- **Login con Google/rol admin**: ninguno de los dos se toca — el login social sigue siendo
  Fase 20 sin implementar, y el rol admin fue explícitamente descartado por el ROADMAP para
  este mismo ítem (ver "Decisión de esta sesión sobre el mecanismo de borrado" en
  `docs/ROADMAP.md`, Fase 21).
- **Exportar los datos antes de borrar ("descargá tu información")**: no lo pide el ROADMAP ni
  esta sesión; no se construye un mecanismo de exportación como parte de esta fase.
- **Período de gracia / cancelación de la baja** (ej. "podés recuperar tu cuenta en 30 días"):
  el ROADMAP decide explícitamente hard delete inmediato, no un soft-delete con ventana de
  arrepentimiento — no se construye ninguna cola de borrado diferido.
- **Notificar a soporte/admin cuando alguien se da de baja**: no pedido; no hay ningún canal de
  notificación a operador en el proyecto hoy (fuera de push/email al propio usuario).
- **Migración de Alembic**: ninguno de los dos ítems de esta fase cambia el esquema —
  `preferred_currency` ya existe (Fase 8) y la baja de cuenta no agrega columnas.

---

## Further notes

- Este documento no implementa ningún cambio en el repositorio — es el desglose ejecutable de
  la sección "Fase 21" de `docs/ROADMAP.md`, con archivos, esquemas y decisiones de diseño
  concretas para que un `backend-engineer`/`frontend-engineer` puedan partir directamente de
  aquí. Dos de sus hallazgos (1 y 8) van más allá de lo que pide el texto literal del ROADMAP:
  el primero es un bug latente ya presente en `seed.py` que esta fase corrige de raíz en vez de
  parchear; el segundo es un gap de invalidación de cache que el propio ROADMAP pide investigar
  ("confirmar qué partes... dependen de esta preferencia") sin nombrar la causa exacta.
- Las seis decisiones de baja de cuenta (A1–A6) y la de cache de moneda (B1) fueron evaluadas
  por el agente `software-architect` contra el código real (no contra el texto del ROADMAP en
  aislado) el 2026-09-13, con cita de línea exacta en cada caso.
- Todos los hallazgos de este documento fueron verificados contra el código real de `backend/`
  y `frontend/` el 2026-09-13 — ningún archivo del repositorio fuera de
  `docs/specs/fase_21_spec.md` fue modificado al producirlo.
