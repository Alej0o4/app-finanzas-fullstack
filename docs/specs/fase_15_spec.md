# Spec — Fase 15: Onboarding de 3 minutos

> Plan de implementación detallado para los 3 ítems de Fase 15 del [ROADMAP](../ROADMAP.md).
> Fuente de verdad de alcance: `docs/ROADMAP.md` (sección "Fase 15 — Onboarding de 3 minutos").
> Este documento no cambia el alcance ahí definido — lo desglosa en tareas ejecutables, con
> archivos concretos, decisiones de diseño numeradas y una estimación de horas revisada contra
> el código real.
>
> **No implementa nada.** Es el hand-off para quien vaya a codear (backend-engineer /
> frontend-engineer). Ningún archivo del repositorio fuera de `docs/specs/fase_15_spec.md` fue
> modificado al producir este documento. La evaluación arquitectónica (dónde vive la señal de
> "primera vez", qué se reusa vs. qué se construye) se hizo con el agente `software-architect`
> antes de redactar este documento, verificada contra el código real de `backend/` y `frontend/`.

Estado del repo al momento de escribir esto (2026-09-06): Fases 7–14 están completas. Fase 15
depende explícitamente de Fases 8 (cuenta por defecto, `User.monthly_income`), 10 (ruta
`/capture`) y 11 (balance de flujo mensual, card con vía de escape para fijar el ingreso). Las
tres ya están implementadas y verificadas en producción del repo — no hay ningún prerrequisito
pendiente. El hallazgo central de este documento, verificado línea por línea contra el código
real: **Fase 15, tal como puede diseñarse hoy, no requiere ningún cambio de backend, ningún
endpoint nuevo y ninguna migración de Alembic.** Es la primera fase del MVP (Fases 7–14) que es
100% frontend de punta a punta — más aislada incluso que Fase 12 ("100% frontend", ver
`docs/ROADMAP.md` línea 539), porque Fase 12 tocaba solo UI ya construida y esta fase, además, no
agrega ningún schema ni tipo de dato nuevo al contrato de API. La razón, con evidencia, está en
los hallazgos 3, 4 y 6 más abajo.

---

## Hallazgos de exploración que corrigen/precisan el ROADMAP

1. **El registro actual NO desloguea al usuario "por decisión" — simplemente nunca lo logueó.**
   `frontend/app/(auth)/register/page.tsx:50-56`:
   ```tsx
   await api.post('users/', { full_name: fullName, email, password });
   router.push('/login?registered=true');
   ```
   No hay ningún intento de loguear tras registrar; el usuario reingresa sus credenciales a mano
   en `/login` inmediatamente después de haberlas escrito en `/register`. Contra un objetivo de "3
   minutos sin fricción" esto es tiempo regalado gratis. **Resuelto por Decisión 15.1.1: login
   automático post-registro**, ver más abajo — sin cambios de backend, ver hallazgo 6.

2. **La verificación de email no bloquea el login — confirmado, no solo asumido.**
   `backend/app/api/users.py:71-73`, comentario explícito: *"No bloquea el login (decisión de
   producto tomada en `docs/specs/fase_07_spec.md` §2.2): el registro no debe fallar ni demorarse
   si el envío de email tiene un problema."* El login automático post-registro (hallazgo 1) no
   choca con nada de la verificación de email — el flujo de verificación sigue funcionando exactamente
   igual (link en el correo, `GET /api/v1/auth/verify-email`), en paralelo, sin gatear nada.

3. **El patrón "registrar y loguear inmediatamente después con las mismas credenciales" ya existe
   y ya está probado — en el backend de pruebas, no en el producto.**
   `backend/tests/conftest.py:94-130`, fixture `register_and_login`: hace exactamente
   `POST /api/v1/users/` seguido de `POST /api/v1/auth/login` con el mismo email/password, y
   **cada uno de los ~40 tests de `backend/tests/test_auth.py` y del resto de la suite pasa por
   esta fixture.** No es una secuencia nueva ni un patrón hipotético — es el flujo más ejercitado
   de todo el backend, solo que nunca se implementó en la UI real. Mover esta secuencia al
   frontend de `register/page.tsx` no es una apuesta de diseño, es adoptar en el producto lo que
   los tests ya validan miles de veces.

4. **`GET /api/v1/transactions/` ya devuelve un conteo total del usuario, gratis.**
   `backend/app/api/transactions.py:189-202` (`schemas.PaginatedResponse`, campo `total`, vía
   `query.with_entities(func.count()).scalar()`). El dashboard **ya llama a este endpoint** para
   "Transacciones recientes" (`frontend/app/(dashboard)/page.tsx:62-67`,
   `queryKeys.dashboard.recentTransactions()`, `limit: 5`) y ya recibe `total` en la respuesta sin
   usarlo hoy. Esto es la pieza central para resolver la pregunta abierta del punto 2 del brief
   ("¿campo nuevo, inferir por `monthly_income IS NULL`, o por conteo de transacciones?") — ver
   Decisión 15.0.1 más abajo: se usa este campo, ya presente en una query que el dashboard ya
   hace, en vez de agregar cualquier cosa nueva.

5. **`UserResponse` (frontend) existe con `monthly_income` pero no lo usa nadie — `useCurrentUser`
   tiene su propio tipo duplicado, más pobre, sin ese campo.** `frontend/types/api.ts:83-91`
   define `UserResponse { id, email, full_name, preferred_currency, preferred_locale,
   preferred_theme, monthly_income }` — `grep -rn "UserResponse" frontend --include=*.tsx
   --include=*.ts` no devuelve ningún import, en ningún archivo: es un tipo muerto. En paralelo,
   `frontend/lib/hooks/useCurrentUser.ts:9-17` declara su propio tipo inline con solo
   `id/email/full_name/preferred_currency/preferred_locale` — **sin `monthly_income`**, aunque
   `GET /users/me` ya lo devuelve en runtime (`backend/app/schemas/schemas.py:86-94`,
   `UserResponse.monthly_income: Decimal | None`). Fase 15 necesita `user.monthly_income` en el
   frontend (para decidir si mostrar el paso de ingreso en el onboarding) — es la primera fase que
   de hecho *necesita* este dato desde `useCurrentUser`, así que es el momento natural de conectar
   el tipo `UserResponse` ya existente en `types/api.ts` en vez de mantener dos tipos divergentes
   del mismo endpoint (ver Decisión 15.2.1).

6. **Confirmado con los tres hallazgos anteriores: los tres "minutos" del ROADMAP se resuelven
   reusando endpoints que ya existen, sin tocar `backend/` en absoluto.**
   - Minuto 0-1 (pregunta de ingreso mensual) → `PATCH /api/v1/users/me` con
     `schemas.UserProfileUpdate.monthly_income` (`backend/app/schemas/schemas.py:104-112`) — el
     mismo endpoint que ya usa la card inline del dashboard (`page.tsx:92-101`, Decisión 11.3.2 de
     `docs/specs/fase_11_spec.md`).
   - Minuto 1-2 (redirección a captura) → la ruta `/capture` ya existe completa desde Fase 10, con
     `TransactionCaptureForm` y su guard `useRequireAuth` (`frontend/app/capture/page.tsx`,
     `layout.tsx`). Lo único que falta es *copy* condicional, no infraestructura.
   - Minuto 2-3 (aha moment) → `GET /dashboard/summary` ya devuelve `monthly_expense_by_currency`
     y `monthly_flow_balance` (`backend/app/api/dashboard.py:106-123`), datos que el dashboard ya
     consulta. El mensaje "Has gastado X de tu ingreso mensual" se arma con datos que ya están en
     el cliente cuando el usuario aterriza en `/`.

   Esto no significa que Fase 15 sea trivial — el trabajo real es de **orquestación de UI y
   estado de sesión** (qué se muestra cuándo, con qué copy, condicionado a qué señal), no de
   modelo de datos. Se documenta explícitamente para que quien implemente no busque una migración
   ni un endpoint nuevo que este análisis descartó a propósito.

7. **Fase 10 ya dejó constancia explícita de que la distinción "primera vez" era tarea de esta
   fase, no de la suya.** `docs/specs/fase_10_spec.md`, Decisión 10.1.4 (líneas 283-294): *"el
   flujo guiado de la primera captura de un usuario nuevo ya es un ítem aparte de Fase 15... Fase
   10 no necesita — ni debería — construir un caso especial de 'solo-primera-vez' que Fase 15 va a
   reemplazar de todas formas."* Esto confirma que el redirect genérico de `login/page.tsx:58`
   (`router.push('/capture')` en *todo* login) es intencional y **no se toca** en esta fase — ver
   Decisión 15.0.2.

8. **Fase 11 ya dejó constancia explícita de que su control inline de ingreso mensual convive con
   el onboarding de Fase 15, no lo reemplaza.** `docs/specs/fase_11_spec.md`, Decisión 11.3.2
   (líneas 470-480): *"Esto no reemplaza el flujo guiado de Fase 15 (que seguirá existiendo como
   la vía principal para usuarios nuevos) — es una vía de escape para que la card no nazca rota
   hoy."* Resuelve directamente el punto 1 del brief: **no se reemplaza, no se duplica lógica —
   coexisten**, ver Decisión 15.3.2.

9. **No existe ningún framework de test de frontend en el repo.** `frontend/package.json` no
   tiene `jest`, `vitest` ni `playwright`, solo `"lint": "eslint"` y `"build": "next build"` —
   mismo estado que documentó Fase 12 (100% frontend, verificación por lint/build/manual). Como
   esta fase tampoco toca `backend/`, no hay ningún archivo de pytest que agregar — la única
   verificación posible es lint/build + QA manual del flujo completo (ver sección Testing).

10. **La política de contraseñas real del registro es `min_length=10` con validador de fuerza**
    (`backend/app/schemas/schemas.py`, `UserCreate.password`, `_validate_password_strength`), no
    los "8 caracteres" que `CLAUDE.md` describe de forma genérica para Fase 7 §2.3. No es un
    hallazgo que Fase 15 deba corregir (no toca el formulario de contraseña), se deja anotado por
    exactitud pero fuera del alcance de este documento.

---

## Decisiones que resuelven los 5 puntos abiertos del brief

**Decisión 15.0.1 — señal de "primera vez", para los tres usos que la necesitan (copy de
`/capture`, paso de ingreso, aha moment): dato derivado (`total` de transacciones, `monthly_income
IS NULL`), **no** una columna nueva `User.onboarding_completed_at`.**

Se evaluaron 3 opciones:

| Opción | Costo | Riesgo |
|---|---|---|
| **(A) Columna `onboarding_completed_at`** | Migración Alembic + lógica de cuándo escribirla (¿al primer login? ¿al primer gasto? ¿al ver el dashboard?) + un endpoint o extensión de `PATCH /users/me` para poder setearla | Estado que puede quedar "atascado" (p. ej. si se resetea data de prueba/seed) o requiere una decisión arbitraria de "cuándo se considera completo" que ningún otro flag del proyecto necesita hoy |
| **(B) Inferir por `monthly_income IS NULL`** | Cero costo — el campo ya existe | **Rechazada**: un usuario que decide no fijar su ingreso (lo salta) o cualquier usuario ya existente pre-Fase-15 con `monthly_income` nunca seteado se vería para siempre como "en onboarding" — falso positivo permanente, no transitorio |
| **(C) Derivar de `total` de `GET /transactions/` (hallazgo 4)** | Cero costo de backend — el campo ya viaja en una respuesta que el dashboard ya pide | Ninguno relevante: `total === 0` es literalmente cierto mientras no haya transacciones; `total === 1` es cierto exactamente una vez en la vida del usuario (la primera transacción) y nunca más, sin necesidad de "apagar" nada a mano |

**Se elige (C)**, con una precisión importante: **no se usa `total` como señal de "vengo del
registro"** (eso lo resuelve un query param efímero, Decisión 15.0.2) — se usa exclusivamente como
señal de **"esta es la primera transacción que este usuario registra en toda su historia"**, que
es justo lo que necesita el aha moment del dashboard (§15.5) para decidir mostrarse una única vez,
de forma automática, sin ningún flag que apagar ni ninguna migración. Tradeoff aceptado
explícitamente: si un usuario borra transacciones hasta volver a quedar en `total === 1`, vería el
aha moment de nuevo — edge case de bajísima probabilidad, sin ningún dato financiero en juego, no
justifica una columna nueva (mismo criterio de costo/beneficio que ya usa el proyecto para otras
decisiones "diferido a propósito", p. ej. Fase 14 §14.4.4).

**Decisión 15.0.2 — el copy de "primer gasto guiado" en `/capture` se activa por un query param
efímero (`?onboarding=1`), propagado únicamente desde el registro — el login genérico
(`login/page.tsx:58`) NO cambia.** Esto respeta el hallazgo 7 al pie de la letra: Decisión 10.1.4
de Fase 10 sigue siendo la implementación vigente (todo login redirige a `/capture`, sin
distinción), y esta fase no la reabre. Solo el flujo `registro → auto-login → /capture` agrega el
parámetro. Si el usuario cierra la pestaña a mitad del onboarding y vuelve a entrar más tarde por
`/login`, aterriza en `/capture` sin el parámetro — ve la pantalla de captura normal, sin el copy
guiado ni el paso de ingreso. Tradeoff aceptado: el onboarding "de lujo" solo cubre el camino
feliz (registro → completar sin cerrar la pestaña); un usuario que lo abandona a mitad de camino
no lo retoma automáticamente. Alternativa descartada: usar `total === 0` para decidir si mostrar
el copy guiado en *cada* login (no solo el que sigue al registro) — se descarta porque
confundiría "usuario nuevo que aún no gastó nada" con "usuario que llevaba tres meses sin abrir la
app"; el query param, al venir solo del registro, no tiene ese falso positivo.

**Decisión 15.0.3 — login automático post-registro, con degradación explícita si falla.** Resuelve
el punto 3 del brief. `register/page.tsx` encadena `POST /users/` → `POST /auth/login` (mismas
credenciales, ya en el estado del formulario) → guarda tokens → `router.push('/capture?onboarding=1')`.
Si el login automático falla (red, 5xx — no debería fallar por credenciales, son las que el propio
usuario acaba de definir), se cae al comportamiento actual (`router.push('/login?registered=true')`)
en vez de dejar al usuario en una pantalla rota. Sin cambios de backend (hallazgo 3).

---

## Orden de dependencia real

```
1. (§15.1) Login automático post-registro — prerrequisito de todo lo demás: sin esto, el usuario
   nunca llega autenticado a /capture?onboarding=1 en el mismo flujo.

2. (§15.2) Exponer `monthly_income` en `useCurrentUser` (conectar el tipo `UserResponse` ya
   existente en types/api.ts, hallazgo 5) — prerrequisito de (3) y (5): ambos necesitan saber si
   el usuario ya fijó su ingreso.

3. (§15.3) Paso "¿cuál es tu ingreso mensual?" dentro de /capture, condicionado a
   `?onboarding=1 && monthly_income == null` — depende de (1) y (2).

4. (§15.4) Copy explícito de "primer gasto guiado" en /capture, mismo condicionamiento — depende
   de (1); es independiente de (3) salvo que ambos viven en el mismo archivo
   (`app/capture/page.tsx`), así que se implementan juntos en la práctica.

5. (§15.5) Aha moment en el dashboard, condicionado a `total === 1` (Decisión 15.0.1) — depende de
   que (3)/(4) hayan producido la primera transacción, pero no depende de su código: es una
   condición sobre datos ya existentes, se puede construir en paralelo desde el día 1.
```

Orden de implementación recomendado: **15.1 → 15.2 → 15.3/15.4 (mismo archivo) → 15.5 en
paralelo**. No hay ningún ítem de backend que bloquee al resto — a diferencia de Fase 14, aquí no
hay "infraestructura" que construir antes que el resto pueda apoyarse en ella.

---

## 15.1 Login automático post-registro

**Archivo:** `frontend/app/(auth)/register/page.tsx`.

```tsx
// frontend/app/(auth)/register/page.tsx — dentro de handleRegister, reemplaza el bloque actual
// (líneas 50-56: `await api.post('users/', ...); router.push('/login?registered=true');`)
try {
  await api.post('users/', {
    full_name: fullName,
    email,
    password,
  });

  // Decisión 15.0.3: login automático reusando /auth/login (mismo patrón que ya
  // ejercita `register_and_login` en backend/tests/conftest.py, hallazgo 3 — no es
  // una secuencia nueva para el backend). Evita que el usuario reescriba sus
  // credenciales que acaba de definir 10 segundos antes.
  try {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);
    const loginResponse = await api.post('auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    localStorage.setItem('jwt_token', loginResponse.data.access_token);
    localStorage.setItem('refresh_token', loginResponse.data.refresh_token);
    router.push('/capture?onboarding=1');
  } catch {
    // Degradación explícita (Decisión 15.0.3): si el auto-login falla, no se pierde
    // el registro — se cae al flujo manual anterior con su mensaje de éxito.
    router.push('/login?registered=true');
  }
} catch (err: unknown) {
  // ... manejo de error de registro sin cambios (líneas 57-75 actuales) ...
}
```

**Nada más cambia en este archivo** — los campos del formulario (`full_name`, `email`, `password`,
`confirmPassword`), su validación y su rate limiting (`5/minute` en `POST /users/`, sin cambios en
`backend/app/api/users.py:42`) quedan exactamente igual. El ROADMAP dice "solo email, sin
formularios largos" — se interpreta (hallazgo 10, y consistente con que `full_name`/`password` son
campos ya establecidos desde Fase 0/7, fuera del alcance de esta fase) como "no agregar ningún
campo nuevo al formulario de registro", no como "quitar los que ya existen".

**Criterio de aceptación:** tras un registro exitoso, el usuario aterriza en `/capture` ya
autenticado (JWT en `localStorage`), sin pasar por `/login`. Un fallo del login automático (rate
limit, red) no deja al usuario sin ningún camino — cae al flujo anterior.

---

## 15.2 Exponer `monthly_income` en `useCurrentUser`

**Decisión 15.2.1 — conectar el tipo `UserResponse` de `types/api.ts` (hallazgo 5), no ampliar el
tipo inline duplicado.**

```ts
// frontend/lib/hooks/useCurrentUser.ts
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { UserResponse } from '@/types/api';

export function useCurrentUser() {
  return useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: async () => {
      const response = await api.get('users/me');
      return response.data as UserResponse;
    },
  });
}
```

Cero cambio de comportamiento para los ~6 call sites existentes de `useCurrentUser` (todos leen un
subconjunto de los mismos campos); gana `monthly_income: number | null`, que es lo único que Fase
15 necesita de aquí.

---

## 15.3 Paso de ingreso mensual dentro de `/capture`

**Decisión 15.3.1 — mutación compartida `useSetMonthlyIncome`, extraída de la mutación inline que
hoy vive solo en el dashboard (`page.tsx:92-101`).** El paso de onboarding y la card inline del
dashboard (Decisión 11.3.2) llaman al mismo endpoint (`PATCH /api/v1/users/me`) con el mismo
payload — duplicar la definición de la mutación en dos archivos es la clase de duplicación que
`frontend/docs/COMPONENTS_GUIDE.md` pide evitar ("si una UI aparece dos veces, primero pensar en
un componente compartido"), aplicado aquí a la mutación, no a la UI (las dos UIs son distintas a
propósito — una es un formulario inline en una card, la otra es un paso de un wizard — pero la
mutación subyacente es idéntica).

```ts
// frontend/lib/hooks/useSetMonthlyIncome.ts (nuevo)
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';

/** PATCH /api/v1/users/me { monthly_income } — compartido entre la card inline del
 * dashboard (Decisión 11.3.2) y el paso de onboarding de Fase 15 (Decisión 15.3.1).
 * No hace toast aquí: cada caller decide su propio mensaje/transición. */
export function useSetMonthlyIncome() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (monthly_income: number) =>
      (await api.patch('users/me', { monthly_income })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
    },
  });
}
```

`frontend/app/(dashboard)/page.tsx` reemplaza su `setMonthlyIncomeMutation` inline (líneas 92-101)
por este hook, conservando su propio `toast.success`/`getApiError` en el `onSuccess`/`onError` de
la llamada a `.mutate()` — sin cambio de comportamiento visible en el dashboard.

**Componente nuevo**, condicionado desde `/capture` (Decisión 15.0.2 — solo con
`?onboarding=1 && monthly_income == null`):

```tsx
// frontend/components/forms/OnboardingIncomeStep.tsx (nuevo)
'use client';

import { useState } from 'react';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';
import { useSetMonthlyIncome } from '@/lib/hooks/useSetMonthlyIncome';

export default function OnboardingIncomeStep({ onDone }: { onDone: () => void }) {
  const [value, setValue] = useState('');
  const mutation = useSetMonthlyIncome();

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const parsed = Number(value);
    if (!value.trim() || Number.isNaN(parsed) || parsed < 0) return;
    mutation.mutate(parsed, { onSuccess: onDone });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <h1 className="text-text font-sans text-xl font-bold tracking-tight">
        ¿Cuál es tu ingreso mensual aproximado?
      </h1>
      <p className="text-text-muted text-sm">
        Lo usamos para mostrarte cuánto te queda cada mes. Puedes cambiarlo después.
      </p>
      <Input
        type="number"
        inputMode="decimal"
        autoFocus
        min={0}
        step="0.01"
        aria-label="Ingreso mensual aproximado"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        className="bg-background"
        placeholder="Ej. 3000000"
      />
      <div className="flex gap-3 pt-2">
        <Button type="button" variant="ghost" onClick={onDone} className="flex-1">
          Omitir por ahora
        </Button>
        <Button type="submit" variant="primary" loading={mutation.isPending} className="flex-1">
          Continuar
        </Button>
      </div>
    </form>
  );
}
```

**Decisión 15.3.2 (resuelve el punto 1 del brief) — no se reemplaza ni se elimina la card inline
del dashboard (Decisión 11.3.2); coexisten como dos entradas al mismo contrato
`PATCH /users/me`.** Si el usuario completa el paso de onboarding, `monthly_income` queda fijado y
la card del dashboard nunca muestra su formulario inline (esa rama solo se activa cuando
`monthly_flow_balance` es `null`, que ya no ocurre). Si el usuario **salta** el paso ("Omitir por
ahora") o abandona el onboarding a mitad de camino, `monthly_income` sigue `null` y la card inline
del dashboard sigue siendo, exactamente como ya lo describe `fase_11_spec.md`, la vía de escape
permanente — sin duplicar lógica, sin ningún caso especial nuevo. Esto también cubre gratis a
todos los usuarios que se registraron **antes** de que existiera esta fase.

---

## 15.4 Copy de "primer gasto guiado" en `/capture`

**Archivo:** `frontend/app/capture/page.tsx` (reescribe el componente completo).

```tsx
// frontend/app/capture/page.tsx
'use client';

import { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import TransactionCaptureForm from '@/components/forms/TransactionCaptureForm';
import OnboardingIncomeStep from '@/components/forms/OnboardingIncomeStep';
import { useCurrentUser } from '@/lib/hooks/useCurrentUser';

/**
 * Pantalla de captura como ruta principal (Fase 10, ítem 10.1). Fase 15 agrega un
 * wizard de dos pasos SOLO cuando se llega desde el registro (`?onboarding=1`,
 * Decisión 15.0.2): primero el ingreso mensual (si aún no está fijado, Decisión
 * 15.3.2), después la captura guiada con copy explícito. Un login normal
 * (Decisión 10.1.4, sin cambios) sigue viendo la pantalla de siempre.
 */
function CaptureScreen() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isOnboarding = searchParams.get('onboarding') === '1';
  const { data: user } = useCurrentUser();

  // Estado local, no persistido (Decisión 15.0.1/15.3.2): un refresh a mitad del
  // wizard puede volver a mostrar el paso de ingreso si `monthly_income` sigue
  // null — edge case aceptado, mismo criterio que el resto de esta fase.
  const [incomeStepDone, setIncomeStepDone] = useState(false);
  const showIncomeStep = isOnboarding && user?.monthly_income == null && !incomeStepDone;

  return (
    <div className="bg-surface border-border/70 shadow-background/40 w-full max-w-md rounded-3xl border p-8 shadow-2xl">
      {showIncomeStep ? (
        <OnboardingIncomeStep onDone={() => setIncomeStepDone(true)} />
      ) : (
        <>
          {isOnboarding && (
            <p className="text-text-muted mb-4 text-sm">
              Ya casi. Registra tu primer gasto para ver el impacto en tu dashboard.
            </p>
          )}
          <TransactionCaptureForm onSuccess={() => router.push('/')} />
        </>
      )}
    </div>
  );
}

export default function CapturePage() {
  return (
    <Suspense fallback={null}>
      <CaptureScreen />
    </Suspense>
  );
}
```

`Suspense` es necesario porque `useSearchParams` lo exige en App Router para rutas sin
`generateStaticParams` — mismo patrón que ya usa `frontend/app/(auth)/login/page.tsx:183-189`.

**Sin cambios en `TransactionCaptureForm.tsx` ni en `capture/layout.tsx`** — el guard
`useRequireAuth` y el link "Ver dashboard" (Decisión 10.1.3 de Fase 10) siguen funcionando igual;
un usuario en medio del onboarding que hace clic en "Ver dashboard" sale sin guardar, exactamente
como ya sale cualquier otro usuario de `/capture` hoy.

---

## 15.5 El "aha moment" en el dashboard

**Archivo:** `frontend/app/(dashboard)/page.tsx`.

```tsx
// frontend/app/(dashboard)/page.tsx — agregar tras el cálculo de flowBalanceValue existente
// (líneas 106-119), antes del bloque de "Summary Cards"

// Fase 15 §15.5, Decisión 15.0.1: `total === 1` es cierto exactamente una vez en la
// vida del usuario — la primera transacción registrada — sin ningún flag que apagar.
const isFirstEverTransaction = recentTransactionsData?.total === 1;
const preferredExpense =
  summary?.monthly_expense_by_currency.find((b) => b.currency === preferredCurrency)?.total ?? 0;
```

```tsx
{/* Aha moment (Fase 15 §15.5) — se muestra solo mientras total === 1; desaparece solo
    con la segunda transacción, sin estado adicional que mantener. */}
{isFirstEverTransaction && (
  <div
    role="status"
    className="bg-primary/10 border-primary/20 text-text rounded-2xl border p-4 text-sm"
  >
    {user?.monthly_income != null ? (
      <>
        Has gastado {formatCurrency(preferredExpense, preferredCurrency)} de tus{' '}
        {formatCurrency(user.monthly_income, preferredCurrency)} de ingreso mensual.
      </>
    ) : (
      '¡Registraste tu primer movimiento! Define tu ingreso mensual abajo para ver cuánto te queda cada mes.'
    )}
  </div>
)}
```

**Decisión 15.5.1 — dos variantes de mensaje, no una sola condicionada a que `monthly_income` esté
seteado.** Si el usuario saltó el paso de ingreso (Decisión 15.3.2), `monthly_flow_balance` es
`null` y la card principal ya muestra el formulario inline de Fase 11 justo debajo — el mensaje
del aha moment en ese caso apunta explícitamente a ese formulario en vez de fingir un dato que no
existe.

**Decisión 15.5.2 (riesgo aceptado, mismo criterio que Fase 14 §14.4.4) — sin mecanismo de
"descartar" el banner.** Mientras `total === 1` siga siendo cierto (el usuario no registra una
segunda transacción), el banner reaparece en cada visita al dashboard. Es un mensaje informativo,
no una alerta — el costo de una repetición ocasional es menor que la complejidad de agregar un
estado de "visto" (local o de servidor) para una feature cuya propia condición ya la apaga sola en
cuanto el usuario siga usando la app con normalidad.

---

## 15.6 Hallazgo de implementación: `Decimal` serializa a `string`, no a `number`

**Encontrado durante la implementación, no anticipado por este documento** — la sección §15.5
de más arriba todavía muestra `formatCurrency(preferredExpense, preferredCurrency)` y
`formatCurrency(user.monthly_income, preferredCurrency)` sin normalizar; ese código, tal cual,
no compila contra el tipo real que expone el backend.

`DashboardSummary.monthly_flow_balance` y `UserResponse.monthly_income` están tipados `Decimal`
en `backend/app/schemas/schemas.py`, sin `json_encoders` propio. `model_dump(mode="json")`
serializa `Decimal` a `string` (para no perder precisión), no a `number` — el mismo patrón que
ya obliga a envolver con `Number(...)` en `budget.amount_limit`, `budget.spent`, `item.total`,
etc. en todo el resto del frontend (`page.tsx`, `CategoryBreakdownBars.tsx`, `analytics/page.tsx`).
`frontend/app/(dashboard)/page.tsx` no seguía esa convención en un solo lugar:

```ts
// Antes (Fase 11): `typeof flowBalance === 'number'` nunca es cierto porque flowBalance
// llega como string — flowBalanceValue quedaba en `null` SIEMPRE, incluso con
// monthly_income fijado. La card "Balance del mes" mostraba el estado "sin definir" desde
// que existe (Fase 11, 2026-08-23) hasta este hallazgo.
const flowBalanceValue = typeof flowBalance === 'number' ? flowBalance : null;

// Después (Decisión 15.6): normaliza igual que el resto del archivo.
const flowBalanceValue = flowBalance == null ? null : Number(flowBalance);
```

Mismo ajuste en §15.5: `formatCurrency(Number(preferredExpense), preferredCurrency)` y
`formatCurrency(Number(user.monthly_income), preferredCurrency)`.

**Decisión 15.6 — corregir en el mismo cambio, no abrir un ítem de deuda técnica separado.**
Es una línea, en un archivo que esta fase ya está tocando, y bloquea directamente el propio aha
moment de §15.5 (que depende de `flowBalanceValue`/`preferredExpense` para calcular el mensaje).
Dejarlo para después significaría que Fase 15 se auto-documenta con un bug conocido en el mismo
banner que introduce.

---

## Testing

**No hay tests de backend que agregar — no hay ningún archivo de `backend/` modificado por esta
fase** (hallazgo 6). `pytest` no necesita ningún cambio; la suite completa debe seguir en verde
sin tocarla.

**No hay framework de test de frontend en el repo** (hallazgo 9) — la verificación es
`pnpm lint`/`pnpm build` limpios más QA manual. Checklist mínimo:

- Registro nuevo → aterriza en `/capture?onboarding=1` ya autenticado (sin pasar por `/login`).
- En `/capture?onboarding=1` con `monthly_income` sin fijar: se ve el paso de ingreso antes que el
  formulario de captura.
  - "Continuar" con un valor válido → pasa al formulario de captura con el copy guiado.
  - "Omitir por ahora" → pasa al formulario de captura con el copy guiado, sin fijar ingreso.
- Guardar la primera transacción → navega a `/` → aparece el banner del aha moment con la
  variante correcta (con cifras si se fijó ingreso, mensaje genérico si se saltó).
- Registrar una **segunda** transacción → el banner del aha moment ya no aparece en visitas
  posteriores al dashboard.
- Un usuario **existente** (pre-Fase-15, con transacciones ya registradas) que inicia sesión
  normalmente: sigue yendo a `/capture` sin ningún copy de onboarding (Decisión 10.1.4 intacta) y
  el dashboard no muestra ningún banner de aha moment.
- Fallback: simular un fallo del login automático (p. ej. cortar red tras el registro) →
  confirma que cae a `/login?registered=true` sin perder el registro ya creado.
- Regresión: la card inline "fijar ingreso mensual" del dashboard (Decisión 11.3.2) sigue
  funcionando igual para un usuario que nunca pasó por el onboarding (o lo saltó).

---

## Resumen de estimación de horas

| Ítem | ROADMAP | Ajustado | Motivo del ajuste |
|---|---|---|---|
| 15.1 Login automático post-registro | *(parte de "Minuto 0-1", 1d)* | 3h | Reusa `POST /auth/login` tal cual (mismo patrón que la fixture de tests, hallazgo 3); sin backend |
| 15.2 `monthly_income` en `useCurrentUser` | *(no dimensionado aparte)* | 1h | Conectar un tipo ya existente (`UserResponse`), no crear uno nuevo |
| 15.3 `useSetMonthlyIncome` + `OnboardingIncomeStep` + refactor del dashboard | *(parte de "Minuto 0-1", 1d)* | 5h | Componente nuevo pequeño + extracción de una mutación ya escrita; sin backend |
| 15.4 Copy guiado en `/capture` (wizard de 2 pasos) | 1d ("Minuto 1-2") | 3h | La ruta, el guard y el formulario ya existen íntegros desde Fase 10 — solo falta orquestación de estado y copy |
| 15.5 Aha moment en el dashboard | 1d ("Minuto 2-3") | 3h | Usa datos que el dashboard ya consulta (`total`, `monthly_expense_by_currency`); sin endpoint nuevo |
| Documentación (`frontend/docs/ARCHITECTURE.md`, nota sobre `?onboarding=1`) | *(no dimensionado aparte)* | 1h | No hay contrato de API que cambie (CLAUDE.md solo exige sincronizar docs de API compartida) — nota breve, no una sección nueva |
| QA manual end-to-end (checklist de arriba) | *(no dimensionado aparte)* | 2h | Único mecanismo de verificación disponible (hallazgo 9) |
| **Total** | **~3d (24h)** | **~2.25d (18h)** | |

El ajuste es a la baja, en la dirección opuesta a Fase 14: ahí el hallazgo principal era trabajo
oculto (la primera página de Ajustes); acá el hallazgo principal es que **no hace falta
construir infraestructura nueva** — los tres "minutos" del ROADMAP se resuelven encadenando
endpoints y datos que Fases 8, 10 y 11 ya dejaron listos. El riesgo de una estimación así de baja
es subestimar el tiempo de pulir el copy/UX del wizard de dos pasos en `/capture` — se deja
margen explícito en 15.3/15.4 (8h combinadas) para esa iteración, más que para escribir el código
en sí.

---

## Resumen de archivos tocados por ítem

| Ítem | Archivos |
|---|---|
| 15.1 Login automático | `frontend/app/(auth)/register/page.tsx` |
| 15.2 Tipo de `useCurrentUser` | `frontend/lib/hooks/useCurrentUser.ts` (usa `UserResponse` de `frontend/types/api.ts`, sin cambios en ese archivo) |
| 15.3 Paso de ingreso | `frontend/lib/hooks/useSetMonthlyIncome.ts` (nuevo), `frontend/components/forms/OnboardingIncomeStep.tsx` (nuevo), `frontend/app/(dashboard)/page.tsx` (reemplaza la mutación inline por el hook) |
| 15.4 Copy guiado en `/capture` | `frontend/app/capture/page.tsx` (reescrito) |
| 15.5 Aha moment | `frontend/app/(dashboard)/page.tsx` |
| Documentación | `frontend/docs/ARCHITECTURE.md` (nota breve sobre `/capture?onboarding=1` y el wizard de dos pasos) |

**Ningún archivo de `backend/` se toca en esta fase.** Ningún archivo de
`backend/docs/API_REFERENCE.md` ni `frontend/docs/API_CONTRACT.md` requiere cambios: no hay
ningún endpoint nuevo ni ningún schema modificado (regla de CLAUDE.md sobre sincronizar ambos docs
no aplica porque no hay contrato de API compartido que haya cambiado).

---

## Cierre

Este documento no implementa ningún cambio en el repositorio — es el desglose ejecutable de la
sección "Fase 15" de `docs/ROADMAP.md`. El hallazgo con más impacto práctico es que, a diferencia
de toda fase anterior del MVP, **esta no necesita tocar `backend/` en absoluto**: la cuenta por
defecto (Fase 8), la ruta `/capture` con su guard (Fase 10) y el balance de flujo mensual con su
vía de escape para el ingreso (Fase 11, Decisión 11.3.2) ya dejaron listo todo lo que los tres
"minutos" del ROADMAP necesitan — el trabajo real es encadenar esas piezas con estado de UI y
copy, no construir infraestructura nueva. La decisión más importante del documento es la 15.0.1:
se descarta explícitamente agregar una columna `User.onboarding_completed_at` (la opción que el
brief dejaba abierta) a favor de derivar la señal de "primera vez" del campo `total` que
`GET /transactions/` ya devuelve — cero migración, cero endpoint nuevo, y sin el riesgo de un flag
que se pueda "atascar". La segunda decisión relevante es la 15.0.2: el redirect genérico de todo
login a `/capture` (Decisión 10.1.4 de Fase 10) **no se reabre** — el copy de onboarding se activa
solo vía un query param que nace en el registro, dejando el comportamiento de los usuarios
recurrentes exactamente como está hoy, documentado como riesgo a validar con datos de uso reales,
no como algo que esta fase deba resolver.

**Deliberadamente fuera de alcance** (no tocar en esta fase):

- **Google OAuth** — aplazado en la decisión del 2026-08-22 (`docs/ROADMAP.md`, backlog
  priorizado, prioridad Media). El registro sigue siendo solo email/password.
- **Reabrir la Decisión 10.1.4** (login recurrente siempre a `/capture`) — sigue siendo un riesgo
  documentado, no una certeza; se revisa con datos de uso reales, no en esta fase (hallazgo 7).
- **Un mecanismo de "reanudar onboarding"** para usuarios que lo abandonan a mitad de camino
  (Decisión 15.0.2) — el onboarding de 3 minutos está optimizado para el camino feliz continuo;
  un usuario que se va y vuelve más tarde usa la app en su modo normal, sin flujo guiado.
- **Estado persistido de "aha moment ya visto"** (Decisión 15.5.2) — se apoya en que
  `total === 1` deja de ser cierto en cuanto el usuario sigue usando la app con normalidad.
- **Corregir el desfase de `CLAUDE.md` sobre la política de contraseñas** (hallazgo 10) — real,
  pero ortogonal a esta fase; no se toca el formulario de contraseña del registro.

Todos los hallazgos fueron verificados contra el código real de `backend/` y `frontend/` el
2026-09-06, con el análisis arquitectónico (dónde vive la señal de "primera vez", qué reusar vs.
qué construir) hecho por el agente `software-architect` antes de redactar este documento. Ningún
archivo del repositorio fuera de `docs/specs/fase_15_spec.md` fue modificado al producirlo.
