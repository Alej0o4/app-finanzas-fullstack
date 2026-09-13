# Spec — Fase 19: Fricción post-onboarding y analítica de ingreso

> Plan de implementación detallado para los 3 ítems de Fase 19 del [ROADMAP](../ROADMAP.md).
> Fuente de verdad de alcance: `docs/ROADMAP.md` (sección "Fase 19 — Fricción post-onboarding y
> analítica de ingreso", decidida en sesión de grilling del 2026-09-12). Este documento no
> cambia el alcance ahí definido — lo desglosa en tareas ejecutables, con archivos concretos,
> diffs y decisiones de diseño numeradas, separadas explícitamente en Backend/Frontend por
> ítem, para que agentes `backend-engineer`/`frontend-engineer` distintos puedan tomar cada
> mitad en paralelo.
>
> **No implementa nada.** Ningún archivo del repositorio fuera de `docs/specs/fase_19_spec.md`
> fue modificado al producir este documento. Los hallazgos de exploración de código fueron
> verificados directamente contra `backend/` y `frontend/` el 2026-09-12 (lectura completa de
> `login/page.tsx`, `register/page.tsx`, `auth.py`, `users.py`, `schemas.py`, `dashboard.py`,
> `SummaryCard.tsx`, `AccountMonthlyBalanceCard.tsx`, `accounts/[id]/page.tsx`,
> `CategoryDonutChart.tsx`, `AnalyticsSummary.tsx`, `analytics/page.tsx`, `dashboard/page.tsx`,
> `queryKeys.ts`, `lib/api.ts`, `database.py`, `models.py`), no inferidos del texto del ROADMAP.
> Las decisiones de arquitectura (P1–P3 abajo) fueron evaluadas por el agente
> `software-architect` a partir de ese mismo código, con cita de línea exacta.

Estado del repo al momento de escribir esto (2026-09-12): Fases 7–17 están completas (Fase 17
mergeada el mismo día de esta sesión de grilling — `AccountMonthlyBalanceCard`,
`dashboard/page.tsx` y `dashboard.py` reflejan ya ese estado, no el anterior a Fase 11/17). Fase
18 (categorías personalizables) está planeada pero no implementada — no se solapa con Fase 19 en
ningún archivo. Fase 19 es la segunda fase post-MVP decidida en la misma sesión de grilling que
Fase 17, a partir de una semana de uso real desde celular.

---

## Hallazgos de exploración que corrigen/precisan el ROADMAP

1. **`login/page.tsx` no tiene ningún dato para condicionar el redirect, confirmado línea por
   línea.** `frontend/app/(auth)/login/page.tsx:46-58`: `handleLogin` hace `POST auth/login`
   (form-urlencoded), guarda `access_token`/`refresh_token` en `localStorage` y hace
   `router.push('/capture')` **sin ninguna condición ni fetch adicional**. `POST /auth/login`
   (`backend/app/api/auth.py:17-45`) devuelve `schemas.TokenResponse`
   (`backend/app/schemas/schemas.py:298-301`: `access_token`, `refresh_token`, `token_type`) —
   ningún dato de usuario. `GET /users/me` (`UserResponse`, `schemas.py:86-94`) tampoco expone
   ningún conteo de transacciones hoy.

2. **`register/page.tsx` es un camino completamente separado, no tocado por este ítem.**
   `frontend/app/(auth)/register/page.tsx:56-73`: el registro con auto-login (Decisión 15.0.3)
   **siempre** hace `router.push('/capture?onboarding=1')` tras loguearse — el ROADMAP no lo
   menciona, y no tiene sentido tocarlo: un usuario recién registrado nunca tiene 2+
   transacciones, así que la condición de este ítem sería siempre falsa ahí de todas formas.

3. **`TokenResponse` es compartido literalmente por login y por refresh — una trampa real si el
   campo nuevo se agrega ahí.** `backend/app/api/auth.py:17-45` (`login`) y `:48-87` (`refresh`)
   devuelven el mismo `schemas.TokenResponse`. El interceptor de Axios
   (`frontend/lib/api.ts:29-75`) dispara `POST auth/refresh` en background cada vez que
   cualquier request recibe un `401` — con el access token de 15 minutos (Fase 7 §2.5) esto
   ocurre varias veces por sesión activa, no una sola vez como el login. Agregar el campo a
   `TokenResponse` obligaría a correr una query de conteo en cada refresh silencioso para un
   consumidor (el interceptor) que nunca redirige a nada con ese dato.

4. **Existe un índice que hace barata la pregunta "¿tiene 2+ transacciones?", pero no una
   respuesta gratis.** `backend/app/models/models.py:96`:
   `Index("ix_transactions_user_id_date", "user_id", "date")` (Fase 7) — permite un scan acotado
   por `user_id` como prefijo, pero no evita que un `COUNT(*)` sin límite recorra todas las filas
   de un usuario con miles de transacciones para responder una pregunta binaria.

5. **El dashboard ya tiene, confirmado, exactamente la redundancia que describe el ROADMAP.**
   `frontend/app/(dashboard)/page.tsx:151-242`: una `SummaryCard` grande (`size="lg" elevated`,
   líneas 157-207) para "Balance del mes" — con el formulario inline de fijar `monthly_income`
   cuando `flowBalanceValue === null` (líneas 168-202) y el banner de onboarding enganchado a los
   mismos datos (`cameFromOnboardingCapture`, líneas 107-137) — y, debajo, un grid de 2 columnas
   (líneas 209-241) con "Ingresos del Mes"/"Gastos del Mes". Balance = ingreso − gasto, y ambos
   operandos ya se muestran aparte: exactamente "las mismas 3 cifras en 3 tarjetas separadas" que
   dice el ROADMAP.

6. **`SummaryCard` no tiene hoy ningún soporte para "una cifra grande + cifras secundarias en la
   misma card".** `frontend/components/ui/SummaryCard.tsx`: props `label`, `value`, `children`,
   `trend`, `color`, `size?: 'md'|'lg'`, `elevated?: boolean` — cada instancia es una sola
   cifra/label. Fase 11 (Decisión 11.3.2) ya extendió este componente con `size` en vez de
   duplicarlo cuando necesitó una card más grande — mismo criterio aplicable aquí.

7. **`AccountMonthlyBalanceCard` (Fase 17) recalcula en el cliente un valor que el backend ya
   entrega calculado — hallazgo no señalado por el ROADMAP, pero corregible en esta misma
   fase.** `frontend/components/charts/AccountMonthlyBalanceCard.tsx:30`: `const balance = income
   - expense;` — a pesar de que `GET /accounts/{id}/monthly-summary` ya devuelve
   `monthly_flow_balance` calculado (`backend/app/schemas/schemas.py:223-225`,
   `AccountMonthlySummary`). La propia card del dashboard, en cambio, sí lee
   `summary.monthly_flow_balance` directo (`dashboard/page.tsx:95`), sin restar nada. Es una
   inconsistencia introducida en Fase 17, que dejó escrito explícitamente en su spec (§17.1.2):
   *"cuando Fase 19 rediseñe la card del dashboard, es esa fase la que decide si unifica ambos
   usos — no se anticipa ese diseño aquí"* — este es el momento natural de resolverlo, no
   scope creep.

8. **`CategoryDonutChart` ya tiene un selector "Tipo: Gastos | Ingresos" — y es un eje distinto
   al que pide el ROADMAP, con el riesgo real de que ambos se confundan si coexisten sin
   distinguirse.** `frontend/components/CategoryDonutChart.tsx` (`TYPE_OPTIONS`, líneas 13-16,
   dentro de `ChartControlsPopover`, líneas 109-127): cambia **qué categorías** se piden al
   backend (`type=expense|income`). El porcentaje de cada slice (`percentage = item.value /
   totalAmount`, líneas 61-74) siempre se calcula sobre el subtotal de lo que está cargado —
   100% de los gastos mostrados, o 100% de los ingresos mostrados si se cambia el tipo — nunca
   cruza ambos. El ROADMAP pide un eje **distinto**: no "qué categorías muestro" sino "contra qué
   denominador divido" (gasto de categoría X sobre **ingreso** total, no sobre gasto total). Dos
   controles usando las mismas dos palabras ("Gastos"/"Ingresos") para cosas distintas, en el
   mismo popover, es una fuente real de confusión si no se nombran de forma explícitamente
   distinta.

9. **Ya existe en el propio archivo un precedente aceptado de sumar en cliente valores que el
   backend entrega desagregados por bucket — no es lo mismo que "recalcular un agregado
   financiero".** `frontend/app/(dashboard)/analytics/page.tsx:212-216`: `totals.totalIncome`/
   `totals.totalExpense` se calculan sumando `parsedTrendData` (que viene de `GET
   /dashboard/cashflow-series`) para alimentar `<AnalyticsSummary>`
   (`frontend/components/AnalyticsSummary.tsx:14`, que además calcula `total = totalIncome -
   totalExpense` en cliente). Sumar/restar cifras ya calculadas por el backend, para
   presentación, es un patrón ya aceptado en este archivo — distinto de recomputar
   `monthly_flow_balance` desde datos crudos, que sí violaría `CLAUDE.md`.

10. **`category-distribution` y `cashflow-series` filtran por los mismos tres predicados —
    equivalencia hoy implícita, nunca probada.** `backend/app/api/dashboard.py:213-218`
    (`obtener_serie_flujo_caja`) y `:256-261` (`obtener_distribucion_categorias`) filtran ambos
    por exactamente `(user_id, currency == filtro_moneda, date >= start_date, date <=
    end_date)` — mismo criterio global de soft-delete heredado vía `with_loader_criteria`
    (`backend/app/core/database.py:45-50`), sin filtro explícito en ninguno de los dos. Para
    `neto=False`, `sum(category-distribution, type=income)` y `sum(cashflow-series.income)`
    deben coincidir siempre con los mismos parámetros — pero no existe ningún test que lo
    verifique. La Decisión 19.3.4 (abajo) convierte esa igualdad, hoy accidental, en un
    invariante del que depende una feature visible.

---

## Decisiones de arquitectura (P1–P3, evaluadas por `software-architect` el 2026-09-12)

- **P1 (Hallazgos 1, 3, 4).** El campo nuevo vive en `UserResponse` (`GET /users/me`), no en
  `TokenResponse` — evita cargar el refresh silencioso con una query de conteo que nunca se lee.
  Ver Decisiones 19.1.1–19.1.5.
- **P2 (Hallazgos 5, 6, 7).** No se unifica `AccountMonthlyBalanceCard` (Fase 17) con la card del
  dashboard — audiencias y estados distintos (el dashboard tiene un estado "ingreso sin definir"
  y un banner de onboarding que la card de cuenta nunca tiene). Se extiende `SummaryCard` otra
  vez, mismo criterio que Fase 11 (Decisión 11.3.2). Ver Decisiones 19.2.1–19.2.3.
- **P3 (Hallazgos 8, 9, 10).** El nuevo control vive dentro del popover de `CategoryDonutChart`
  (no a nivel de página), como grupo "Referencia" con copy explícitamente distinto de "Tipo"; se
  deshabilita en las combinaciones sin significado de producto claro (`categoryType==='income'`,
  `netMode===true`); el denominador reutiliza `totals.totalIncome`, ya sumado en cliente, sin
  endpoint nuevo. Ver Decisiones 19.3.1–19.3.5.

---

## Orden de ejecución recomendado

```
1. Backend: campo has_transaction_history en UserResponse (§19.1)
   ── Independiente de todo lo demás; un solo archivo de schema + un query nuevo.
      Bloquea el paso 2 (el frontend necesita el campo real en el contrato).

2. Frontend: redirect condicional en login/page.tsx (§19.1)
   ── Depende de (1). Sin el campo, no hay forma de decidir el destino.

3. Frontend: rediseño de la card "Balance del mes" + fix de AccountMonthlyBalanceCard (§19.2)
   ── Independiente de (1)-(2); toca page.tsx del dashboard, SummaryCard.tsx,
      AccountMonthlyBalanceCard.tsx y accounts/[id]/page.tsx. Puede hacerse en paralelo
      por otro agente/persona.

4. Frontend: "Referencia" en CategoryDonutChart + analytics/page.tsx (§19.3)
   ── Independiente de (1)-(3); un componente y una página distintos a los de los otros
      dos ítems. Puede hacerse en paralelo desde el día 1.

5. Backend (opcional, no bloqueante): test de equivalencia category-distribution/
   cashflow-series (§19.3, Decisión 19.3.5)
   ── Puede ir en el mismo PR que (1) o como PR aparte — no depende de (4) para
      escribirse (el invariante que prueba ya existe hoy, antes de que (4) lo use),
      pero (4) es la razón de negocio para escribirlo ahora.
```

Los ítems 19.1, 19.2 y 19.3 son, en la práctica, tres líneas de trabajo totalmente
independientes entre sí (no comparten ningún archivo) — mismo criterio que
`docs/specs/fase_11_spec.md`/`docs/specs/fase_17_spec.md` aplicaron a sus ítems sin dependencia
cruzada. Dentro de 19.1, backend bloquea frontend; 19.2 y 19.3 son 100% frontend de punta a
punta (19.3 con un test backend opcional).

---

## 19.1 Redirección de login condicionada al uso real

### Backend

**Decisión 19.1.1 — nombre del campo: `has_transaction_history`, no `has_transactions`.** El
ROADMAP mismo lo deja abierto ("`has_transactions` (o equivalente)"). El umbral real de producto
es "2 o más", no "al menos 1" (ver Hallazgo del ROADMAP: resuelve la Decisión 10.1.4 de Fase 10,
que habla de "usuario recurrente"). Nombrar el campo literalmente `has_transactions` describiría
mal la semántica y ataría el contrato de API al número exacto — si el umbral cambia a 3 mañana,
un nombre literal quedaría desalineado con el dato real. `has_transaction_history` describe el
resultado de una decisión de producto que el backend posee por completo, sin exponer el umbral
como parte del contrato.

**Decisión 19.1.2 — query `LIMIT 2`, no `COUNT(*)`.** Ver Hallazgo 4. Un `func.count()` (mismo
patrón que ya usa `transactions.py` para paginación) recorre todas las filas que matchean para un
usuario con miles de transacciones; un `.limit(2).all()` sobre la misma condición se detiene
apenas encuentra 2 filas, sin importar cuántas existan en total — estrictamente más barato y es
exactamente lo que la pregunta necesita responder (¿hay 2 o más?), no un total exacto.

**Archivo a modificar:** `backend/app/api/users.py`, función `obtener_usuario_actual`
(líneas 78-80).

```python
# backend/app/api/users.py
@router.get("/me", response_model=schemas.UserResponse)
def obtener_usuario_actual(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),  # 🆕
):
    # Fase 19 §19.1.2: LIMIT 2, no COUNT(*) — solo hace falta saber si hay 2 o más,
    # no cuántas exactamente. El filtro de deleted_at IS NULL ya lo aplica el
    # with_loader_criteria global (database.py:45-50), no hace falta explícito aquí.
    primeras_dos = (
        db.query(models.Transaction.id).filter(models.Transaction.user_id == current_user.id).limit(2).all()
    )
    current_user.has_transaction_history = len(primeras_dos) >= 2  # 🆕, atributo no persistido
    return current_user
```

`has_transaction_history` no es una columna de `models.User` — se asigna como atributo de
instancia justo antes de serializar (mismo patrón que ya usaría cualquier campo calculado sobre
un modelo `from_attributes=True`; no requiere migración Alembic).

**Decisión 19.1.3 — `default=False` en el schema; no se calcula en `crear_usuario` ni en
`actualizar_perfil`.** `backend/app/api/users.py:41-75` (`crear_usuario`) y `:83-94`
(`actualizar_perfil`) devuelven el objeto ORM directamente vía `from_attributes=True`; sin
default, Pydantic fallaría al serializar esas dos respuestas (el atributo no existe en esas
instancias, que nunca pasan por el bloque de arriba). Con default `False`:
- `crear_usuario` devuelve un valor correcto sin costo — un usuario recién creado nunca tiene 2+
  transacciones.
- `actualizar_perfil` devuelve un valor potencialmente stale (`False` fijo, sin consultar) — pero
  ningún call site de ese endpoint (la mutación de `monthly_income` en `dashboard/page.tsx`) lee
  ese campo de la respuesta, así que el dato incorrecto ahí es inconsecuente. **Limitación
  conocida, documentada a propósito** (mismo criterio que Decisión 11.3.1/17.2.1 de fases
  anteriores): no es un bug, es un campo que solo se calcula donde alguien lo necesita leer.

```python
# backend/app/schemas/schemas.py — UserResponse (líneas 86-94)
class UserResponse(UserBase):
    id: int
    preferred_currency: str = "COP"
    preferred_locale: str = "es-CO"
    preferred_theme: str = "dark"
    monthly_income: Decimal | None = None
    has_transaction_history: bool = False  # 🆕 Fase 19 §19.1 — solo se calcula en GET /users/me

    class Config:
        from_attributes = True
```

**Testing:** nuevo bloque en `backend/tests/test_users.py` (si no existe, crear; verificar
primero si ya hay tests de `users.py` antes de asumir que hace falta un archivo nuevo):
- Usuario sin transacciones: `GET /users/me` devuelve `has_transaction_history: false`.
- Usuario con exactamente 1 transacción: `false`.
- Usuario con 2 transacciones: `true`.
- Usuario con muchas transacciones (ej. 50, del seed): `true` — y la query no debe hacer un
  `COUNT` completo (verificable indirectamente por tiempo de respuesta, no crítico para el test,
  pero documentar la intención en el nombre del test, ej.
  `test_has_transaction_history_uses_limit_not_count_semantics`).

### Frontend

**Decisión 19.1.4 — el frontend hace un round-trip explícito a `GET users/me` entre el login y
el redirect, y primea el cache de TanStack Query con el resultado.** `login/page.tsx:52-58` hoy
hace `router.push('/capture')` inmediatamente tras guardar los tokens, sin ningún fetch
adicional — no hay forma de decidir el destino sin conocer `has_transaction_history` primero, así
que el round-trip es inevitable, no opcional. El costo neto es menor de lo que parece: tanto
`/capture` como `/dashboard` ya llaman `useCurrentUser()` en su primer render (mismo `queryKey:
['currentUser']`, `staleTime` de 1 min en `QueryProvider`) — si `login/page.tsx` usa
`useQueryClient().setQueryData(queryKeys.currentUser(), data)` con la respuesta de este fetch, la
pantalla de destino no vuelve a pedirlo. El costo real es una sola llamada más, movida más
temprano en el flujo, no una llamada extra de por vida de la sesión.

**Decisión 19.1.5 — si el fetch a `users/me` falla, el fallback es `/capture` (el destino más
permisivo), no bloquear el login.** Consistente con el criterio ya usado en el registro (Fase 7
§2.2: "el registro no debe fallar ni demorarse si el envío de email tiene un problema") — una
pieza no crítica no debe bloquear el flujo principal (login exitoso). Tratar el fallo como
"asumir usuario poco activo" es seguro: en el peor caso, un usuario recurrente ve una pantalla de
captura de más, no pierde acceso.

**Archivo a modificar:** `frontend/app/(auth)/login/page.tsx`.

```tsx
// imports nuevos
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import type { UserResponse } from '@/types/api';

function LoginForm() {
  const queryClient = useQueryClient(); // 🆕
  // ... resto del estado sin cambios

  const handleLogin = async (e: React.FormEvent) => {
    // ... validación de campos sin cambios (líneas 26-36)
    setIsLoading(true);

    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const response = await api.post('auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });

      const { access_token, refresh_token } = response.data;
      localStorage.setItem('jwt_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);

      // Fase 19 §19.1.4/19.1.5: la Decisión 10.1.4 de Fase 10 ("login siempre redirige a
      // /capture") queda resuelta aquí — un usuario recurrente con 2+ transacciones va
      // directo al dashboard. Fallback a /capture si el fetch falla (no bloquear el login
      // por una pieza no crítica, mismo criterio que el envío de email de verificación).
      try {
        const meResponse = await api.get('users/me');
        const user = meResponse.data as UserResponse;
        queryClient.setQueryData(queryKeys.currentUser(), user); // evita refetch en destino
        router.push(user.has_transaction_history ? '/dashboard' : '/capture');
      } catch {
        router.push('/capture');
      }
    } catch (err: unknown) {
      // ... manejo de error sin cambios
    } finally {
      setIsLoading(false);
    }
  };
  // ...
}
```

**Archivos a modificar:**
- `frontend/app/(auth)/login/page.tsx` (diff arriba).
- `frontend/types/api.ts`: `UserResponse` — agregar `has_transaction_history: boolean;`.

**`register/page.tsx` no se toca** — confirmado en Hallazgo 2, camino separado, condición siempre
falsa para un usuario recién creado.

**Testing:** sin suite de frontend (igual que fases anteriores, `docs/TODO.md` "Tests de
frontend" sigue en backlog). Verificación manual: un usuario con 2+ transacciones (ej.
`test@test.com` del seed, 45 transacciones) que hace login normal llega a `/dashboard`
directamente; un usuario nuevo (0 o 1 transacción) sigue llegando a `/capture`; simular una falla
de red en `GET users/me` (ej. desconectar el backend justo después de login) y confirmar que
igual redirige a `/capture` sin quedarse colgado.

**Criterio de aceptación:**
- Un usuario con 2 o más transacciones que inicia sesión normalmente (no vía registro) llega
  directo a `/dashboard`.
- Un usuario con 0 o 1 transacción sigue llegando a `/capture`, sin cambio de comportamiento.
- El flujo de registro (`register/page.tsx`) no cambia — sigue yendo siempre a
  `/capture?onboarding=1`.
- `GET /users/me` no ejecuta un `COUNT(*)` sin límite sobre `transactions`.
- `docs/ROADMAP.md`: la Decisión 10.1.4 de Fase 10 (riesgo documentado, "validar con datos de uso
  reales") queda resuelta — anotar en el ROADMAP o en `docs/TODO.md` que se resolvió aquí.

---

## 19.2 Rediseño de la card "Balance del mes"

### Backend

**Sin cambios de backend** — todos los datos ya existen en `DashboardSummary`
(`monthly_flow_balance`, `monthly_income_by_currency`, `monthly_expense_by_currency`,
`backend/app/schemas/schemas.py:280-284`) y en `AccountMonthlySummary`
(`monthly_flow_balance`, `schemas.py:223-225`).

### Frontend

**Decisión 19.2.1 — layout: una sola `SummaryCard` (`size="lg" elevated`) con el balance como
cifra principal, y una fila secundaria compacta de "Ingresos"/"Gastos" debajo, dentro de la misma
card, reemplazando el grid de 2 columnas actual (`page.tsx:209-241`).** Se agrega a `SummaryCard`
una prop nueva `secondaryStats?: ReactNode` que renderiza contenido más pequeño bajo la cifra
principal — no un array tipado rígido, sino `ReactNode`, porque el contenido a mostrar ya es JSX
condicional existente (los `.map()` por moneda de `monthly_income_by_currency`/
`monthly_expense_by_currency`, líneas 218-226 y 229-237 actuales) que se reutiliza tal cual dentro
de esta prop, sin reescribirlo. Esto preserva el caso multi-moneda del seed (`test@test.com` con
cuentas COP y USD) sin diseño nuevo.

**Decisión 19.2.2 — la fila secundaria se muestra siempre, incluso cuando `monthly_flow_balance`
es `null`.** `monthly_income_by_currency`/`monthly_expense_by_currency` son datos independientes
de si el usuario fijó `user.monthly_income` (son sumas de transacciones reales del mes, no el
valor declarado) — no hay razón para ocultarlos mientras el formulario inline de "fijar ingreso"
ocupa el lugar de la cifra principal. Layout mobile-first: reutilizar el patrón ya existente en el
propio archivo (`SummaryCard.tsx`, clases `max-sm:`/`sm:` inline) en vez de introducir un
breakpoint nuevo — fila secundaria en columna en `max-sm:`, en fila en `sm:`.

**Archivo a modificar:** `frontend/components/ui/SummaryCard.tsx`.

```tsx
interface SummaryCardProps {
  label: string;
  value?: string;
  children?: ReactNode;
  trend?: 'up' | 'down';
  color?: string;
  size?: 'md' | 'lg';
  elevated?: boolean;
  secondaryStats?: ReactNode; // 🆕 Fase 19 §19.2.1 — fila compacta bajo la cifra principal
}

export default function SummaryCard({
  // ...props existentes
  secondaryStats, // 🆕
}: SummaryCardProps) {
  // ... JSX existente sin cambios hasta el cierre del bloque de children/value/trend
  return (
    <div className={/* ...clases existentes... */}>
      <p className={/* ...existente... */}>{label}</p>
      <div className={/* ...existente... */}>{/* ...cifra principal + trend, sin cambios... */}</div>
      {secondaryStats && (
        <div className="border-border/50 mt-4 flex flex-col gap-3 border-t pt-4 sm:flex-row sm:gap-6">
          {secondaryStats}
        </div>
      )}
    </div>
  );
}
```

**Archivo a modificar:** `frontend/app/(dashboard)/page.tsx`, sección "Summary Cards"
(líneas 151-242).

**Pasos:**
1. Eliminar el grid de 2 columnas (líneas 209-241) como bloque independiente.
2. Construir `secondaryStats` como JSX reutilizando literalmente el contenido de las dos
   `SummaryCard` que se retiran (los `.map()` por moneda), envuelto en dos columnas etiquetadas
   ("Ingresos"/"Gastos") en vez de dos cards completas:
   ```tsx
   const secondaryStats = (
     <>
       <div className="flex-1">
         <p className="text-text-muted text-xs font-medium">Ingresos del Mes</p>
         <div className="text-success mt-0.5 font-semibold tabular-nums">
           {summary?.monthly_income_by_currency.length ? (
             summary.monthly_income_by_currency.map((b) => (
               <p key={b.currency}>{formatCurrency(b.total, b.currency)}</p>
             ))
           ) : (
             <p>{formatCurrency(0, preferredCurrency)}</p>
           )}
         </div>
       </div>
       <div className="flex-1">
         <p className="text-text-muted text-xs font-medium">Gastos del Mes</p>
         <div className="text-danger mt-0.5 font-semibold tabular-nums">
           {summary?.monthly_expense_by_currency.length ? (
             summary.monthly_expense_by_currency.map((b) => (
               <p key={b.currency}>{formatCurrency(b.total, b.currency)}</p>
             ))
           ) : (
             <p>{formatCurrency(0, preferredCurrency)}</p>
           )}
         </div>
       </div>
     </>
   );
   ```
3. Pasar `secondaryStats={secondaryStats}` a la única `SummaryCard` restante ("Balance del mes",
   líneas 157-207) — el resto de esa card (cifra principal, `trend`, `color`, formulario inline
   de fijar ingreso) no cambia.
4. El bloque `Skeleton` de carga (líneas 154-155, 210-214) se colapsa a un solo `Skeleton` más
   alto (la card ahora incluye la fila secundaria) — ajustar altura aproximada si hace falta para
   no dar un salto de layout perceptible al cargar.

**Decisión 19.2.3 — bundlear el fix del Hallazgo 7: `AccountMonthlyBalanceCard` pasa a aceptar
`balance` como prop explícita (ya calculada por el backend) en vez de recibir `income`/`expense`
y restarlos internamente.** Cambio de contrato pequeño, con un solo call site
(`accounts/[id]/page.tsx:97-101`) a ajustar — ya carga `monthlySummary` completo (incluye
`monthly_flow_balance`), basta con pasar ese campo en vez de `income`/`expense` por separado, y
dejar de restar en el componente. Cierra el único punto del código donde un total financiero se
recalcula en cliente en vez de leerse ya calculado, sin ampliar el alcance de esta fase más allá
de lo que ya le tocaba tocar.

**Archivo a modificar:** `frontend/components/charts/AccountMonthlyBalanceCard.tsx`.

```tsx
interface AccountMonthlyBalanceCardProps {
  label: string;
  balance: number; // 🆕 antes: income + expense por separado
  currency: string;
  isLoading: boolean;
}

export default function AccountMonthlyBalanceCard({
  label,
  balance, // 🆕
  currency,
  isLoading,
}: AccountMonthlyBalanceCardProps) {
  // balance ya viene calculado por el backend — sin resta en cliente (Fase 19 §19.2.3,
  // cierra el Hallazgo 7 de docs/specs/fase_19_spec.md).
  const isPositive = balance >= 0;
  const trend = isPositive ? ('up' as const) : ('down' as const);
  const color = isPositive ? 'var(--color-success)' : 'var(--color-danger)';

  return (
    <SummaryCard label={label} size="lg" elevated trend={trend} color={color}>
      {isLoading ? (
        <Skeleton className="h-9 w-40" />
      ) : (
        <span className={isPositive ? '' : 'text-danger'}>{formatCurrency(balance, currency)}</span>
      )}
    </SummaryCard>
  );
}
```

**Archivo a modificar:** `frontend/app/(dashboard)/accounts/[id]/page.tsx` — call site de
`<AccountMonthlyBalanceCard>`: pasar `balance={Number(monthlySummary?.monthly_flow_balance ?? 0)}`
en vez de `income`/`expense`.

**Archivos a modificar:**
- `frontend/components/ui/SummaryCard.tsx` (prop `secondaryStats`).
- `frontend/app/(dashboard)/page.tsx` (pasos 1-4).
- `frontend/components/charts/AccountMonthlyBalanceCard.tsx` (Decisión 19.2.3).
- `frontend/app/(dashboard)/accounts/[id]/page.tsx` (call site actualizado).

**Testing:** sin suite de frontend. Verificación manual: la card "Balance del mes" muestra la
cifra principal + una fila con Ingresos/Gastos del mes en desktop y en mobile (~400px, sin
desbordar ni romper el layout); el formulario inline de fijar ingreso mensual sigue funcionando
igual cuando `monthly_flow_balance` es `null`; `accounts/[id]` muestra el mismo balance que antes
del cambio (verificar contra un cálculo manual `income - expense` para confirmar que el backend y
el componente coinciden, ya que antes el componente lo recalculaba y ahora lo lee).

**Criterio de aceptación:**
- El dashboard ya no muestra 3 cifras (balance, ingreso, gasto) en 3 tarjetas visualmente
  separadas — es una sola card con una fila secundaria compacta.
- Ningún dato se pierde: ingreso y gasto del mes siguen visibles, por moneda si aplica.
- `AccountMonthlyBalanceCard` ya no calcula `income - expense` en el cliente — lee
  `monthly_flow_balance` directo del backend.
- El cálculo del balance nunca se hace en el cliente en ningún punto tocado por este ítem.

---

## 19.3 Nueva métrica "% del ingreso por categoría" en Analítica

### Backend

**Sin cambios de backend requeridos** para el ítem en sí (Decisión 19.3.4) — el denominador se
obtiene sumando en cliente datos ya disponibles, no de un endpoint nuevo.

**Decisión 19.3.5 (opcional, no bloqueante) — test de regresión que verifica la equivalencia de
agregados entre `category-distribution` y `cashflow-series`.** Ver Hallazgo 10. La Decisión
19.3.4 convierte una igualdad hoy accidental (`sum(category-distribution, type=income) ==
sum(cashflow-series.income)` para los mismos parámetros) en un invariante del que depende una
feature visible — si algún cambio futuro toca el filtro de uno de los dos endpoints sin tocar el
otro, esta métrica mostraría porcentajes incoherentes sin que nada lo señale en código.

**Archivo a modificar/crear:** `backend/tests/test_dashboard.py`.

```python
def test_category_distribution_income_matches_cashflow_series_income_total(client, auth_headers, ...):
    # Crear transacciones de ingreso en 2+ categorías, mismo rango de fechas/moneda.
    # sum(item.total for item in category-distribution response, type=income)
    # == sum(item.income for item in cashflow-series response)
    ...
```

### Frontend

**Decisión 19.3.1 — el nuevo grupo se llama "Referencia" (no "Ver como %: Gastos | Ingresos"
literal), con etiquetas de opción explícitamente distintas de las de "Tipo".** Ver Hallazgo 8. El
riesgo es real: dos controles con las mismas dos palabras ("Gastos"/"Ingresos") en el mismo
popover, para ejes distintos. Usar el mismo texto en ambos ("Tipo: Gastos|Ingresos" arriba, "Ver
como %: Gastos|Ingresos" abajo) es la lectura literal del ROADMAP pero reproduce la confusión que
el propio hallazgo señala. Opciones del nuevo grupo: **"Mis gastos"** / **"Mi ingreso total"**
(evita repetir la palabra suelta "Ingresos" que ya usa "Tipo" un grupo arriba). El nombre exacto
del copy es una decisión de bajo riesgo ajustable en implementación — la decisión de arquitectura
es que **debe** diferenciarse textualmente, no solo espacialmente (un separador `border-t` no
basta: ya hay uno entre "Tipo" y "Modo" en el popover actual, y aun así ambos grupos podrían
confundirse si comparten vocabulario).

**Decisión 19.3.2 — el control "Referencia" solo es relevante y editable cuando `categoryType ===
'expense'`; se fuerza a "sobre gasto" (comportamiento actual) y se deshabilita visualmente cuando
`categoryType === 'income'`.** La combinación Tipo=Ingresos + Referencia=Ingreso total es
literalmente el comportamiento ya existente hoy (dona de ingresos, 100% de sí misma) — no aporta
nada nuevo. La combinación Tipo=Ingresos + Referencia=Gastos no tiene un significado de producto
claro (¿una categoría de ingreso como % de mis gastos totales?) y el ROADMAP no la pide. Se
reutiliza el patrón visual que el propio componente ya tiene para exactamente este tipo de
restricción: `pointer-events-none opacity-40`, que hoy aplica a los botones de "Tipo" cuando
`netMode` está activo (`CategoryDonutChart.tsx:118-122`) — mismo idioma visual, aplicado ahora a
"Referencia" cuando Tipo=Ingresos.

**Decisión 19.3.3 — "Referencia" es mutuamente excluyente con `netMode=true`; se deshabilita
(mismo tratamiento visual) cuando el modo neto está activo.** `netMode` ya fuerza `categoryType` a
`'expense'` en el backend (`analytics/page.tsx:185`) y muestra montos netos por categoría
(`ingreso - gasto` por categoría, puede incluir categorías con signo mixto). Definir "neto por
categoría como % de mi ingreso bruto total" es una métrica sin especificación clara en el ROADMAP
y de valor de producto dudoso (mezcla un neto por categoría con un bruto total como
denominador) — no construir algo que nadie pidió, mismo criterio que la Decisión 17.2.1 de Fase
17 usó para no agregar validación de moneda no solicitada.

**Decisión 19.3.4 — el denominador (ingreso total del período) se calcula reutilizando
`totals.totalIncome`, ya presente en `analytics/page.tsx:212-216`, sin endpoint nuevo ni campo
nuevo en `category-distribution`.** Ver Hallazgo 9. Ese valor ya se obtiene sumando en cliente los
buckets de `GET /dashboard/cashflow-series` — mismo patrón que ya alimenta el "Balance Neto" de
`AnalyticsSummary`, precedente ya aceptado en este archivo. No es la misma categoría de riesgo que
"recalcular `monthly_flow_balance`": no se fabrica un dato financiero nuevo, se sigue sumando lo
que el backend ya calculó, aplicado a un nuevo consumidor (el denominador de un porcentaje) en vez
de a un KPI de tarjeta.

**Archivo a modificar:** `frontend/components/CategoryDonutChart.tsx`.

```tsx
export type ReferenceMode = 'expense-total' | 'income-total'; // 🆕

interface CategoryDonutChartProps {
  data: CategoryDistributionItem[] | undefined;
  isFetching: boolean;
  isError: boolean;
  categoryType: CategoryType;
  onCategoryTypeChange: (type: CategoryType) => void;
  netMode: boolean;
  onNetModeChange: (net: boolean) => void;
  hiddenCategories: Set<string>;
  onHiddenCategoriesChange: (set: Set<string>) => void;
  referenceMode: ReferenceMode; // 🆕
  onReferenceModeChange: (mode: ReferenceMode) => void; // 🆕
  totalIncomeForPeriod: number; // 🆕 Decisión 19.3.4 — ya sumado en analytics/page.tsx
}
```

Cambios internos:
1. Nuevo grupo en `ChartControlsPopover` (después del grupo "Modo", líneas ~128-153 actuales),
   deshabilitado cuando `categoryType === 'income' || netMode`:
   ```tsx
   <div className="border-border/50 my-1 border-t" />
   <div className="flex flex-col gap-1">
     <p className="text-text-muted px-2 py-1 text-xs font-medium">Referencia</p>
     {(
       [
         { value: 'expense-total' as const, label: 'Mis gastos' },
         { value: 'income-total' as const, label: 'Mi ingreso total' },
       ]
     ).map((option) => (
       <button
         key={option.value}
         type="button"
         disabled={categoryType === 'income' || netMode}
         onClick={() => onReferenceModeChange(option.value)}
         className={`rounded-md px-2.5 py-1.5 text-left text-xs font-medium transition-colors ${
           referenceMode === option.value
             ? 'bg-surface text-text'
             : 'text-text-muted hover:text-text hover:bg-surface/50'
         } ${categoryType === 'income' || netMode ? 'pointer-events-none opacity-40' : ''}`}
       >
         {option.label}
       </button>
     ))}
   </div>
   ```
2. El cálculo de `percentage` (líneas 61-74, `originalCategoryData`) usa `totalIncomeForPeriod`
   como denominador cuando `referenceMode === 'income-total' && categoryType === 'expense' &&
   !netMode`; en cualquier otro caso, se comporta exactamente igual que hoy (denominador = suma
   de los ítems cargados):
   ```tsx
   const originalCategoryData = useMemo(() => {
     const items =
       (data as CategoryDistributionItem[])?.map((item) => ({ ...item, value: Number(item.total) })) || [];

     const usesIncomeReference =
       referenceMode === 'income-total' && categoryType === 'expense' && !netMode;
     const denominator = usesIncomeReference
       ? totalIncomeForPeriod
       : items.reduce((sum, item) => sum + item.value, 0);

     return items.map((item) => ({
       ...item,
       percentage: denominator > 0 ? (item.value / denominator) * 100 : 0,
     }));
   }, [data, referenceMode, categoryType, netMode, totalIncomeForPeriod]);
   ```
   Mismo ajuste en `visibleCategoryData` (líneas 76-87, ocultar categorías vía leyenda) —
   `denominator` se recalcula igual, sustituyendo la suma de `items` visibles por
   `totalIncomeForPeriod` bajo la misma condición.
3. Tooltip y leyenda (líneas 194-199, 236-243): cuando `usesIncomeReference` es verdadero, el
   texto "% del subtotal" pasa a "% del ingreso total" — evita que el usuario lea "% del
   subtotal" y asuma que se refiere al subtotal de gastos.

**Archivo a modificar:** `frontend/app/(dashboard)/analytics/page.tsx`.

**Pasos:**
1. Nuevo estado vía `useQueryParamState` (mismo patrón que `categoryType`/`netoRaw`, con
   validador whitelist siguiendo el criterio de Fase 13 §13.6):
   ```tsx
   const validateReferenceMode = (raw: string): ReferenceMode =>
     (['expense-total', 'income-total'] as const).includes(raw as ReferenceMode)
       ? (raw as ReferenceMode)
       : 'expense-total';

   const [referenceMode, setReferenceMode] = useQueryParamState(
     'reference',
     'expense-total',
     validateReferenceMode
   );
   ```
2. Pasar `referenceMode`, `onReferenceModeChange={setReferenceMode}` y
   `totalIncomeForPeriod={totals.totalIncome}` a `<CategoryDonutChart>` (línea 294-304 actual).

**Archivos a modificar:**
- `frontend/components/CategoryDonutChart.tsx` (diff arriba).
- `frontend/app/(dashboard)/analytics/page.tsx` (pasos 1-2).

**Testing:** backend — Decisión 19.3.5 (opcional, ver arriba). Frontend sin suite automatizada.
Verificación manual: con `categoryType=expense` y `netMode=false`, alternar "Referencia" entre
"Mis gastos" (comportamiento actual, sin cambios) y "Mi ingreso total" (los porcentajes ahora
suman menos de 100% si hay ahorro, o exactamente 100% si el usuario gasta exactamente su ingreso,
y cada categoría muestra qué fracción del ingreso total se fue ahí); cambiar a `categoryType =
income` o `netMode = true` deshabilita visualmente el control "Referencia" y lo deja en su último
valor sin aplicarlo.

**Criterio de aceptación:**
- Un usuario puede ver, para sus categorías de gasto, qué porcentaje de su ingreso total del
  período representa cada una — no solo qué porcentaje de sus gastos totales.
- El control nuevo tiene un nombre visualmente distinto del selector "Tipo" ya existente, sin
  ambigüedad de qué eje controla cada uno.
- Ninguna combinación sin significado de producto claro (`Tipo=Ingresos` + `Referencia`,
  `Modo=Neto` + `Referencia`) es seleccionable.
- El denominador nuevo no proviene de un endpoint nuevo ni de un cálculo financiero fabricado en
  cliente — reutiliza una suma que el propio archivo ya hacía para otro consumidor.

---

## Resumen de archivos tocados por ítem

| Ítem | Backend | Frontend |
|---|---|---|
| 19.1 redirect de login | `api/users.py` (`obtener_usuario_actual`, query `LIMIT 2`), `schemas/schemas.py` (`UserResponse.has_transaction_history`), `tests/test_users.py` (nuevo o extendido) | `app/(auth)/login/page.tsx`, `types/api.ts` |
| 19.2 card "Balance del mes" | — | `components/ui/SummaryCard.tsx` (`secondaryStats`), `app/(dashboard)/page.tsx`, `components/charts/AccountMonthlyBalanceCard.tsx`, `app/(dashboard)/accounts/[id]/page.tsx` |
| 19.3 % del ingreso por categoría | `tests/test_dashboard.py` (test de equivalencia, opcional) | `components/CategoryDonutChart.tsx`, `app/(dashboard)/analytics/page.tsx` |
| Cruzando toda la fase | — | `docs/ROADMAP.md`/`docs/TODO.md` (marcar resuelta la Decisión 10.1.4 de Fase 10), `backend/docs/API_REFERENCE.md` + `frontend/docs/API_CONTRACT.md` (documentar `UserResponse.has_transaction_history` — convención de `CLAUDE.md` sobre contratos de API compartidos) |

---

## Cierre

Este documento no implementa ningún cambio en el repositorio — es el desglose ejecutable de la
sección "Fase 19" de `docs/ROADMAP.md`, con archivos, diffs y decisiones de diseño concretas para
que agentes `backend-engineer`/`frontend-engineer` distintos puedan tomar cada mitad (o los tres
ítems, que son independientes entre sí) sin tener que re-explorar el código para tomar las mismas
decisiones. Dos de sus hallazgos (7 y 8) van más allá de lo que pide el texto literal del
ROADMAP: el primero corrige una inconsistencia de cálculo introducida por Fase 17 y que esa misma
fase dejó pendiente a propósito para esta; el segundo señala un riesgo real de confusión de UI
entre un control ya existente y el que pide este ítem, ninguno de los dos derivable solo del
texto del ROADMAP en aislado. Las tres decisiones de arquitectura (P1–P3) fueron evaluadas por el
agente `software-architect` contra el código real (no contra el texto del ROADMAP en aislado) el
2026-09-12, con cita de línea exacta en cada caso. Todos los hallazgos de este documento fueron
verificados contra el código real de `backend/` y `frontend/` el 2026-09-12 — ningún archivo del
repositorio fuera de `docs/specs/fase_19_spec.md` fue modificado al producirlo.
