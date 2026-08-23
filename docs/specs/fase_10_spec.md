# Spec — Fase 10: Captura en 3 toques

> Plan de implementación detallado para los 5 items de Fase 10 del [ROADMAP](../ROADMAP.md).
> Fuente de verdad de alcance: `docs/ROADMAP.md` (sección "Fase 10 — Captura en 3 toques",
> líneas ~213-235). Este documento no cambia el alcance ahí definido — lo desglosa en tareas
> ejecutables, con archivos concretos, pasos, dependencias y decisiones de diseño.
>
> **No implementa nada.** Es el hand-off para quien vaya a codear (frontend-engineer /
> backend-engineer). A diferencia de `docs/specs/fase_09_spec.md` (puramente frontend), Fase 10
> tiene tareas reales de backend (idempotencia de `POST /transactions`) — la estructura de este
> documento sigue el precedente de `docs/specs/fase_07_spec.md` y `docs/specs/fase_08_spec.md`
> para esas secciones.

Estado del repo en el momento de escribir esto (2026-08-23): Fase 8 (modelo de datos del nuevo
MVP) y Fase 9 (accesibilidad y componentes base de UI) están mergeadas a `main`, ambas completas
el mismo día. Fase 10 depende de las dos:

- **De Fase 8**, depende del dato, no del código: `Transaction.payment_method` (nullable,
  `cash`/`card`/`transfer`) ya existe de punta a punta — modelo, schema, creación y
  actualización — verificado en esta exploración (ver hallazgo 4). El ítem "Tag de método de
  pago" de Fase 10 es, en efecto, **100% frontend**, tal como anticipaba el encargo.
- **De Fase 9**, depende del componente, no del dato: `Button`, `Input`, `Select` y `ModalShell`
  ya tienen `focus-visible`, `htmlFor`/`id`, `aria-label`/`aria-expanded`, cierre por `Escape`,
  `overscroll-contain` y animación de entrada real (`animate-fade-in`/`animate-slide-in-bottom`).
  `FloatingActionButton.tsx` y `FabManager.tsx` en particular ya están limpios (`aria-expanded`,
  `active:scale-95`, `transition-[transform,box-shadow,background-color]`) — Fase 10 construye
  sobre esta base sin heredar deuda de accesibilidad ahí. El componente nuevo que sí introduce
  Fase 10 (el grid de íconos de categoría, ver 10.2) es genuinamente nuevo y **no** hereda nada
  de Fase 9 automáticamente — se decide su propio manejo de foco/teclado en este documento.

Fase 10 es explícitamente el bloqueador de **Fase 11** (dashboard de flujo mensual — el propio
ROADMAP dice "captura primero, dashboard después de guardar", y Fase 11 reformula la pantalla a
la que ese "después" apunta) y de **Fase 15** (onboarding de 3 minutos, que redirige "directo a
la captura"). Este documento no toca ninguna de las dos — ni el balance de flujo mensual, ni las
barras por categoría, ni los 3 bugs multi-moneda restantes (`budgets-progress`,
`cashflow-series`, `category-distribution`), ni `actualizar_transaccion` no actualiza `currency`
(los cuatro son explícitamente Fase 11 en el ROADMAP) — ni el flujo guiado de onboarding
(Fase 15).

---

## Hallazgos de exploración que corrigen/precisan el ROADMAP

1. **El formulario de 6 campos está confirmado tal cual lo describe el encargo, con la ubicación
   exacta de cada uno.** `frontend/components/modals/QuickTransactionModal.tsx`: toggle
   Gasto/Ingreso (líneas 109-132, dos `<button>` sin `aria-pressed`, ver hallazgo 9), `Input`
   monto (134-143, `type="number"`, ya `autoFocus`), `Select` cuenta (146-161), `Select`
   categoría (162-177), `Input` fecha (181-188, `type="date"`), `Input` descripción opcional
   (189-196). `filteredCategories` (49-52) ya filtra por `type` — reusable sin cambios.

2. **El selector de cuenta "solo aparece si hay más de una" NO está implementado hoy, aunque la
   preselección sí existe parcialmente.** `effectiveAccountId = accountId || (accounts?.length ?
   String(accounts[0].id) : '')` (línea 54) autoselecciona la primera cuenta, pero el `<Select>`
   (146-161) se renderiza siempre, sin condicionar por `accounts.length`. Confirmado además que
   `TransactionModal.tsx` (el modal "completo", abierto vía FAB → "Nueva transacción") es un
   componente **distinto e independiente**, sin ningún import compartido con
   `QuickTransactionModal.tsx` — el ROADMAP no lo nombra y este documento tampoco lo toca; queda
   fuera de alcance a propósito (ver Decisión 10.2.1).

3. **El fallo silencioso está confirmado exactamente en la línea que cita el encargo.**
   `QuickTransactionModal.tsx:87`: `if (!effectiveAccountId || !categoryId || !amount) return;`
   dentro de `handleSubmit` (85-97) — sin ningún `toast`, a diferencia del `onError` de la
   mutation (80-82) que sí llama `toast.error(getApiError(error))`.

4. **`payment_method` ya está implementado de punta a punta en el backend — incluyendo el fix
   de `actualizar_transaccion` que `docs/specs/fase_08_spec.md` marcaba como pendiente.**
   Verificado en el código actual (no en el spec de Fase 8, que describe el estado *antes* de
   implementar):
   - `backend/app/models/models.py:78` — `payment_method = Column(String(20), nullable=True)`.
   - `backend/app/schemas/schemas.py:119-122` — enum `PaymentMethod(str, Enum)` con
     `cash`/`card`/`transfer`; `TransactionBase.payment_method: PaymentMethod | None = None`
     (línea 133) — se propaga automáticamente a `TransactionCreate` y `TransactionResponse`.
   - `backend/app/api/transactions.py::crear_transaccion` (línea 51) — usa
     `transaccion.model_dump(exclude_none=True)`, así que `payment_method` se persiste sin
     ningún cambio adicional si viene en el body.
   - `backend/app/api/transactions.py::actualizar_transaccion` (líneas 242-244) — **ya tiene**
     `if transaccion_actualizada.payment_method is not None: transaccion_db.payment_method =
     transaccion_actualizada.payment_method`, con un comentario explícito sobre preservar el
     valor si el cliente no lo reenvía. El bug que anticipaba `fase_08_spec.md` (`payment_method`
     borrado silenciosamente en cada `PUT`) **ya no existe**.
   - `frontend/types/api.ts` — `Transaction.payment_method`, `CreateTransactionPayload
     .payment_method` y `UpdateTransactionPayload.payment_method` (líneas 20, 104, 116) ya están
     tipados como `'cash' | 'card' | 'transfer' | null` opcional.
   - Lo único que falta, confirmado por `grep -rn "payment_method\|paymentMethod" frontend/
     --include="*.tsx" --include="*.ts"`: **cero** consumo en JSX — ningún `<Select>`, botón o
     texto en ninguna pantalla lo muestra o lo edita. El ítem 10.3 es, en efecto, puramente de
     UI.

5. **La fecha puede eliminarse del formulario por completo, no solo ocultarse detrás de un
   valor por defecto — hallazgo más fuerte que lo que sugiere el ROADMAP.** El ROADMAP dice
   "Fecha = hoy por defecto, sin mostrar", lo que podría leerse como "seguir enviándola, pero sin
   campo visible". No hace falta: `Transaction.date` tiene `server_default=func.now()`
   (`backend/app/models/models.py:76`), `TransactionBase.date: datetime | None = None`
   (`schemas.py:132`) ya es opcional, y `crear_transaccion` construye la fila con
   `transaccion.model_dump(exclude_none=True)` (línea 51) — si `date` no viene en el payload, se
   omite del `dict` y la columna toma su `server_default` en el INSERT. Conclusión: el frontend
   puede simplemente **dejar de enviar `date`** en vez de calcular `todayAsInputValue()` en el
   cliente (`QuickTransactionModal.tsx:21,34`) y reenviarlo — cero cambios de backend, cero
   lógica de timezone en el cliente. Ver 10.2, paso 4.

6. **No existe ningún mecanismo de idempotencia en todo el proyecto — confirmado por grep
   exhaustivo, hay que diseñarlo desde cero.** `grep -rni "idempot" backend/app frontend/` (fuera
   de `venv/` y comentarios de terceros) solo devuelve las menciones del propio `docs/TODO.md` y
   `docs/ROADMAP.md` describiendo el problema — ninguna tabla, columna, header ni lógica
   existente que reutilizar. Ver diseño completo en la sección de Backend, ítem 10.4.

7. **`POST /transactions` no tiene rate limiting hoy, y no debería agregársele en esta fase.**
   `grep -n "@limiter.limit" backend/app/api/*.py` devuelve exactamente 2 resultados, ambos en
   `auth.py` (líneas 18 y 113 — login y password-reset). `transactions.py::crear_transaccion` no
   tiene el decorador. Esto es correcto y debe quedarse así: Fase 7 limitó los endpoints
   propensos a abuso automatizado (credential stuffing, enumeración de cuentas); `POST
   /transactions` es exactamente el endpoint de mayor volumen de uso *legítimo* del producto —
   el objetivo mismo de esta fase ("menos de 8 segundos", "3 toques") implica que un usuario real
   puede disparar varias creaciones seguidas en poco tiempo. La idempotencia (10.4) resuelve el
   problema real de esta fase (reintento accidental duplica saldo); un rate limit resolvería un
   problema distinto (abuso) que no está en alcance aquí y arriesga bloquear a un usuario legítimo
   registrando varios gastos seguidos.

8. **El punto de entrada post-login es un único call site, lo que simplifica mucho la Decisión
   10.1.1.** `grep -rn "router.push('/')\|router.replace('/')\|href=\"/\"" frontend/` devuelve
   exactamente una coincidencia: `frontend/app/(auth)/login/page.tsx:45-46`
   (`router.push('/');`, con el comentario `// Redirigimos al Dashboard (la fuente de verdad)`).
   El guard de autenticación (`localStorage.getItem('jwt_token')` + redirect a `/login`) también
   vive en un único lugar: `frontend/app/(dashboard)/layout.tsx:12-17`. Ninguna otra pantalla
   redirige a `/` ni duplica el guard — el blast radius de introducir una nueva ruta de entrada es
   pequeño y acotado a estos dos archivos más los nuevos que se crean.

9. **No existe ningún patrón de grid de íconos seleccionables (ni radio nativo, ni ARIA
   `radiogroup`) en todo el proyecto — es un componente genuinamente nuevo.** Verificado con
   `grep -rn "type=\"radio\"\|role=\"radio` frontend/` (sin resultados) y revisando los otros
   selectores tipo-toggle existentes: el toggle Gasto/Ingreso de `QuickTransactionModal.tsx:109-
   132` y el selector de tipo de cuenta en `accounts/page.tsx:270-271,338-339` son, ambos,
   `<select>` nativos o `<button>` planos sin semántica de grupo — ninguno usa `<input
   type="radio">` ni `role="radiogroup"`. No hay una convención existente que seguir ni romper;
   la decisión de diseño 10.2.3 abajo parte de cero. Nota relacionada: el propio toggle
   Gasto/Ingreso que sí existe hoy tampoco tiene `aria-pressed` — es un gap preexistente, menor,
   que no está en el alcance nombrado por el ROADMAP para esta fase (se señala para no repetirlo
   por descuido al construir el nuevo grid, no para arreglarlo aquí).

10. **La suite de tests de transacciones ya tiene el fixture scaffolding necesario para probar
    idempotencia sin fixtures nuevas.** `backend/tests/test_transactions.py` (439 líneas) usa
    `client`, `auth_headers`, `make_account`, `make_category` de `conftest.py` (líneas 94-198) —
    mismo patrón reusable para los tests de 10.4. `conftest.py` corre sobre SQLite en memoria vía
    `Base.metadata.create_all()` (líneas 24-30), no vía Alembic — cualquier tabla nueva agregada a
    `models.py` queda disponible en tests automáticamente, sin depender de que la migración se
    ejecute en el entorno de test.

---

## Orden de ejecución recomendado

La dependencia real entre tareas, no la importancia percibida:

```
1. Backend: tabla + endpoint de idempotencia (10.4, mitad
   backend)                                                 ── sin dependencia de nada de
                                                                 frontend; puede arrancar el día 1
                                                                 en paralelo con 2-6
2. Extraer TransactionCaptureForm + rediseño de 3
   interacciones + grid de categorías + eliminar el
   campo fecha (10.2)                                       ── sin dependencia de (1); es el
                                                                 componente base que 10.1, 10.3,
                                                                 10.4 (frontend) y 10.5 modifican o
                                                                 consumen después — hacerlo primero
                                                                 evita reabrir el mismo archivo
                                                                 varias veces
3. Corregir el fallo silencioso del submit (10.5)            ── implementar DENTRO del mismo PR
                                                                 que (2), no como diff separado
                                                                 posterior: ambos tocan
                                                                 exactamente `handleSubmit`:
                                                                 hacerlo aparte significaría
                                                                 escribirlo una vez y reescribirlo
                                                                 al redisañar el submit en (2)
4. Tag de método de pago (10.3)                               ── implementar DENTRO del mismo PR
                                                                 que (2): ambos tocan el mismo
                                                                 archivo, y el bloque "Más
                                                                 opciones" que 10.3 necesita se
                                                                 crea precisamente en (2) al mover
                                                                 la descripción ahí
5. Enviar `Idempotency-Key` desde el formulario (10.4,
   mitad frontend)                                            ── depende de (2) [necesita el call
                                                                 site de `createMutation.mutate`
                                                                 ya existente]; depende de (1) para
                                                                 ser verificable de punta a punta,
                                                                 pero el código en sí no bloquea a
                                                                 (1) — puede escribirse en paralelo
6. Pantalla de captura como ruta principal: `/capture`,
   hook `useRequireAuth`, redirect de login (10.1)            ── depende de (2)-(4) terminados: la
                                                                 ruta nueva reusa
                                                                 `TransactionCaptureForm` ya
                                                                 estable; es el último paso porque
                                                                 es el que más cambia el flujo
                                                                 observable de la app (login ya no
                                                                 aterriza en el dashboard) y
                                                                 conviene probarlo con el
                                                                 formulario ya terminado, no a
                                                                 medio construir
```

Los pasos 2-4 están agrupados en un solo PR porque **tocan el mismo archivo** (el nuevo
`TransactionCaptureForm.tsx`), igual que Fase 9 agrupó ítems que tocaban `ModalShell.tsx` o
`Input.tsx`/`Select.tsx` — no por urgencia relativa. El paso 1 (backend de idempotencia) es la
única rama sin ninguna dependencia del resto: puede implementarse en paralelo desde el día 1 por
otro agente/persona, igual que Fase 9 señaló para los formularios de auth.

Estimación total heredada del ROADMAP: 2d (10.1) + 2d (10.2) + 4h (10.3) + 1d (10.4) + 2h (10.5)
= 16h + 16h + 4h + 8h + 2h = **46h (~5¾ días de trabajo de 8h)**. Dos ajustes puntuales frente al
número heredado, ninguno que cambie el total:
- **10.1 probablemente termina bajo las 2d asignadas** si se implementa después de (2)-(4): el
  trabajo neto de 10.1 en solitario (hook de auth, layout minimalista, la página en sí, el
  cambio de una línea en `login/page.tsx`) es más pequeño que 2d una vez que
  `TransactionCaptureForm` ya existe — la mayor parte del esfuerzo de "la pantalla de captura"
  está, en la práctica, en 10.2. Se deja la estimación del ROADMAP sin tocar (puede haber
  imprevistos de layout/responsive no capturados aquí), pero se avisa que es generosa, no
  ajustada.
- **10.2 es más ajustada de lo que parece** si, en cambio, alguien decide implementar 10.2, 10.3
  y 10.5 como tres PRs separados en vez de uno solo (contra la recomendación de este documento):
  la re-apertura de `handleSubmit` y del layout del formulario tres veces separadas fácilmente
  excede 2d + 4h + 2h combinadas. La estimación combinada (2d + 4h + 2h ≈ 2¾ días) solo es
  realista si se ejecuta como un único pase, tal como recomienda el orden de arriba.

---

## Tareas de Frontend

### 10.1 — Pantalla de captura como ruta principal

**Problema confirmado:** hoy el punto de entrada tras login es el dashboard (`/`,
`frontend/app/(dashboard)/page.tsx`), y la captura es un FAB (`FloatingActionButton.tsx` vía
`FabManager.tsx`) que abre `QuickTransactionModal` como overlay. `login/page.tsx:45-46` redirige
a `/` tras un login exitoso (hallazgo 8) — es el único lugar que decide el destino post-login.

**Decisión 10.1.1 — nueva ruta `/capture`, no reasignar el significado de `/`.** La alternativa
obvia sería que `/` pase a ser la pantalla de captura y el dashboard se mueva a `/dashboard`. Se
descarta: el hallazgo 8 confirma que solo **un** call site redirige a `/` tras login, pero mover
el significado de `/` tiene un costo mayor y menos acotado — el ítem del sidebar "Dashboard"
(`Sidebar.tsx:64`, `{ name: 'Dashboard', href: '/', icon: LayoutDashboard }`), el resaltado de
ruta activa que compara contra `pathname`, y cualquier asunción implícita de que `/` es "la
pantalla principal" en el resto del código, tendrían que revisarse una por una para confirmar que
nada se rompe — sin ningún beneficio adicional sobre la alternativa de una ruta nueva. Además,
Fase 11 va a reescribir el contenido de la página que hoy vive en `/` (tarjeta de flujo mensual,
barras por categoría) — mantener `/` estable evita que Fase 10 y Fase 11 compitan por la
identidad del mismo archivo dos veces. Costo de la alternativa elegida: una ruta nueva, un layout
nuevo, un hook de auth compartido — todo aislado, sin tocar el dashboard existente.

**Decisión 10.1.2 — extraer el guard de autenticación a un hook compartido
`useRequireAuth`.** `(dashboard)/layout.tsx:12-17` tiene hoy:
```tsx
useEffect(() => {
  const token = localStorage.getItem('jwt_token');
  if (!token) {
    router.replace('/login');
  }
}, [router]);
```
La nueva ruta `/capture` necesita exactamente el mismo guard (es una ruta autenticada, no forma
parte de `(auth)`). Mismo razonamiento que la Decisión 9.4.1 de `fase_09_spec.md` (extraer
`useEscapeToClose` para 2 call sites idénticos): escribirlo dos veces es la duplicación mecánica
que, si una futura ruta agrega un tercer layout autenticado, se copiaría una vez más.

```ts
// frontend/lib/hooks/useRequireAuth.ts
export function useRequireAuth() {
  const router = useRouter();
  useEffect(() => {
    const token = localStorage.getItem('jwt_token');
    if (!token) router.replace('/login');
  }, [router]);
}
```

**Decisión 10.1.3 — layout minimalista para `/capture`, sin `Sidebar`/`FabManager`/
`ConfirmDialog`, pero con una salida explícita.** El objetivo ("menos de 8 segundos") compite
directamente con el chrome completo del shell autenticado — no tiene sentido cargar `Sidebar` y
`FabManager` (que a su vez monta otro `QuickTransactionModal` y `TransactionModal`) en una
pantalla cuyo propósito es no distraer. Se recomienda un layout tipo `(auth)/layout.tsx`
(centrado, sin sidebar) pero **con** un control explícito para salir sin guardar (ej. un link
"Saltar" o "Ver dashboard" hacia `/`) — a diferencia de `(auth)`, esta es una ruta autenticada
dentro del flujo normal de uso, no un formulario de una sola vía; un usuario que solo quiere
revisar el dashboard sin registrar nada necesita una salida, porque no hay sidebar desde donde
navegar.

**Decisión 10.1.4 (riesgo a validar, no una certeza de producto) — el redirect post-login apunta
a `/capture` en *todo* login, no solo la primera vez.** Es la lectura literal del ROADMAP ("El
MVP invierte esto: captura primero, dashboard después de guardar" — sin distinguir usuario nuevo
de recurrente); el flujo guiado de la *primera* captura de un usuario nuevo ya es un ítem aparte
de Fase 15 ("Minuto 1-2: primer gasto guiado — redirección directa a la captura con instrucción
explícita"), así que Fase 10 no necesita — ni debería — construir un caso especial de
"solo-primera-vez" que Fase 15 va a reemplazar de todas formas. Dicho esto, se deja constancia
explícita del riesgo: un usuario recurrente que abre la app solo para consultar su balance (no
para registrar nada) va a ver la pantalla de captura primero en cada login, con una fricción
extra (el toque de "Saltar" de la Decisión 10.1.3) que no tenía antes. Es la implementación
correcta según lo que dice el ROADMAP hoy, pero conviene confirmarlo con datos de uso reales una
vez lanzado — no es una decisión de arquitectura que este documento pueda validar por adelantado.

**Pasos:**
1. Crear `frontend/lib/hooks/useRequireAuth.ts` (código en la Decisión 10.1.2).
2. `frontend/app/(dashboard)/layout.tsx:12-17` — reemplazar el `useEffect` inline por
   `useRequireAuth();`.
3. Crear `frontend/app/capture/layout.tsx` — layout minimalista (ver Decisión 10.1.3), llama a
   `useRequireAuth()`.
4. Crear `frontend/app/capture/page.tsx` — renderiza `<TransactionCaptureForm
   onSuccess={() => router.push('/')} />` (el componente construido en 10.2), más el link de
   salida de la Decisión 10.1.3.
5. `frontend/app/(auth)/login/page.tsx:45-46` — cambiar `router.push('/')` por
   `router.push('/capture')`.
6. Verificar que `Sidebar.tsx:64` (`{ name: 'Dashboard', href: '/' }`) y el resaltado de ruta
   activa no necesitan ningún cambio — `/` sigue siendo el dashboard sin modificaciones.
7. Actualizar `frontend/docs/ARCHITECTURE.md` (y, si corresponde, la sección "Frontend" de
   `CLAUDE.md`, que hoy describe explícitamente "dos route groups": `(auth)` y `(dashboard)`) para
   documentar la tercera ruta minimalista `/capture` — deuda de documentación real que este ítem
   introduce, a resolver en la misma PR (no es parte de la implementación de código pero sí del
   contrato de "mantener la documentación al día" que exige `CLAUDE.md`).

**Estimación:** 2d (heredada del ROADMAP) — ver nota en "Orden de ejecución" sobre por qué
probablemente sobra tiempo si se implementa después de 10.2-10.4.

**Criterio de aceptación:**
- Login exitoso redirige a `/capture`, no a `/`.
- `/capture` sin token válido en `localStorage` redirige a `/login` (mismo comportamiento que
  cualquier otra ruta autenticada).
- Guardar una transacción en `/capture` navega a `/` y la transacción nueva aparece en el resumen
  y en la lista de transacciones recientes del dashboard (reutiliza la invalidación de queries ya
  existente en `TransactionCaptureForm`, sin cambios adicionales).
- `Sidebar`, `FabManager` y `ConfirmDialog` no se renderizan en `/capture`.
- Existe una forma explícita de salir de `/capture` sin guardar nada.
- Navegar directamente a `/` estando autenticado sigue mostrando el dashboard sin cambios de
  comportamiento.

---

### 10.2 — Rediseño del formulario a 3 interacciones

**Problema confirmado:** ver hallazgo 1. 6 campos reales, 2 `<select>` nativos.

**Decisión 10.2.1 — extraer un componente compartido `TransactionCaptureForm`, usado tanto por
`/capture` (10.1) como por `QuickTransactionModal` (que pasa a ser un wrapper delgado sobre
`ModalShell` + este componente).** 10.1 necesita el formulario de 3 toques en una página completa;
el FAB ("Gasto rápido") sigue necesitando una versión rápida en modal, sin navegar fuera de donde
esté el usuario. Construirlo dos veces divergiría de inmediato (un fix de UX aplicado solo a una
de las dos copias) — mismo razonamiento que la extracción de `useEscapeToClose` en Fase 9.
**`TransactionModal.tsx`** (el modal "completo", abierto vía FAB → "Nueva transacción",
hallazgo 2) **no se toca** — es un componente distinto, más completo (descripción obligatoria,
selector "mostrar todas las categorías"), y el ROADMAP no lo nombra en ningún ítem de Fase 10.

**Decisión 10.2.2 — las "3 interacciones" son: (1) monto vía teclado numérico, (2) categoría vía
un toque en un ícono, (3) guardar.** El toggle Gasto/Ingreso y la cuenta no cuentan como
interacciones adicionales porque ya tienen un valor por defecto razonable (`defaultType`,
`effectiveAccountId`) — el usuario solo los toca si quiere cambiarlos, no en el camino feliz.
Cambios concretos sobre `QuickTransactionModal.tsx`:
- El `Input` de monto (línea 136, hoy `type="number"`) gana `inputMode="decimal"` — es el
  mecanismo explícito y correcto para forzar el teclado numérico en móvil; `type="number"` por sí
  solo ya ayuda en la mayoría de navegadores móviles pero además agrega flechas de incremento en
  desktop que no aportan nada aquí.
- El `<Select>` de categoría (líneas 162-177) se reemplaza por el grid de íconos de la
  Decisión 10.2.3.
- El `<Select>` de cuenta (líneas 146-161) se envuelve en una condición: solo se renderiza si
  `accounts && accounts.length > 1` (hallazgo 2 — hoy no está condicionado pese a que el ROADMAP
  lo pide explícitamente). Con 0 o 1 cuenta, `effectiveAccountId` (línea 54) sigue resolviendo el
  valor sin selector visible.
- El `Input` de fecha (líneas 181-188) se elimina por completo, no se oculta — ver hallazgo 5: no
  se envía `date` en el payload, el backend la puebla vía `server_default=func.now()`.
- El `Input` de descripción (líneas 189-196) se mueve detrás de un `<details>`/`<summary>`
  ("Más opciones") en vez de mostrarse siempre — usar el elemento nativo `<details>` en vez de un
  disclosure hecho a mano con `useState` + `aria-expanded`: el navegador ya provee el
  comportamiento de expandir/contraer y la semántica accesible correcta sin JS adicional,
  consistente con la Decisión 10.2.3 de preferir semántica nativa sobre ARIA hecho a mano donde
  el HTML ya resuelve el problema.

**Decisión 10.2.3 — el grid de categorías se construye con `<input type="radio">` nativos
ocultos visualmente, no con un widget ARIA `role="radiogroup"` hecho a mano.** El hallazgo 9
confirma que no hay ningún patrón existente en el proyecto que seguir — es una decisión desde
cero. Se elige radio nativo sobre ARIA manual porque el navegador ya resuelve gratis exactamente
lo que el encargo pedía evaluar ("radiogroup semántico, roving tabindex"): navegación con flechas
entre las opciones del mismo `name`, un solo `Tab` para entrar/salir del grupo completo, y el
anuncio correcto de "seleccionado"/"no seleccionado" + el nombre del grupo (vía
`<fieldset><legend>`) para lectores de pantalla — sin escribir ningún `onKeyDown` ni gestionar
`tabIndex` a mano. Un `role="radiogroup"` construido con `<div>`/`<button>` reproduciría el mismo
comportamiento con más código propio y más superficie para el mismo tipo de bug que Fase 9 pasó
32h corrigiendo en otros componentes (foco, estado ARIA desincronizado del estado visual).
Implementación:
```tsx
<fieldset>
  <legend className="sr-only">Categoría</legend>
  <div className="grid grid-cols-4 gap-2">
    {filteredCategories.map((category) => (
      <label key={category.id} className="cursor-pointer">
        <input
          type="radio"
          name="category"
          value={category.id}
          checked={categoryId === String(category.id)}
          onChange={() => setCategoryId(String(category.id))}
          className="peer sr-only"
        />
        <div className="peer-checked:border-primary peer-checked:bg-primary/10 peer-focus-visible:ring-primary/50 peer-focus-visible:ring-2 border-border/70 flex flex-col items-center gap-1 rounded-xl border p-3 transition-colors">
          <CategoryIcon icon={category.icon} size={22} />
          <span className="text-xs">{category.name}</span>
        </div>
      </label>
    ))}
  </div>
</fieldset>
```
El anillo de foco usa `peer-focus-visible:` (no `peer-focus:`), consistente con la corrección de
Fase 9 §9.1 — copiar `peer-focus:` aquí reintroduciría exactamente el bug que esa fase cerró, solo
que en un componente nuevo en vez de uno viejo.

**Pasos:**
1. Crear `frontend/components/forms/TransactionCaptureForm.tsx` — mover a este archivo el estado
   (`amount`, `type`, `accountId`, `categoryId`, `description`), los dos `useQuery` de
   cuentas/categorías (líneas 37-47), `filteredCategories` (49-52) y `createMutation` (56-83) de
   `QuickTransactionModal.tsx`, parametrizado con una prop `onSuccess: () => void` (el modal le
   pasa `onClose`, la ruta `/capture` le pasa `() => router.push('/')`).
2. Aplicar los cambios de la Decisión 10.2.2 (monto, grid de categorías, cuenta condicional,
   eliminar fecha, descripción tras "Más opciones").
3. `createMutation.mutate({...})` (línea 89-96 hoy) deja de incluir `date`.
4. `QuickTransactionModal.tsx` queda como wrapper:
   `<ModalShell isOpen={isOpen} onClose={onClose} title={title}><TransactionCaptureForm
   onSuccess={onClose} defaultType={defaultType} /></ModalShell>` — debería quedar en menos de
   20 líneas.
5. `frontend/types/api.ts:98` — `CreateTransactionPayload.date` pasa de requerido a opcional
   (`date?: string;`), reflejando que ya no siempre se envía.

**Estimación:** 2d (heredada del ROADMAP) — realista solo si 10.3 y 10.5 se implementan en el
mismo pase (ver "Orden de ejecución").

**Criterio de aceptación:**
- En móvil, el campo de monto abre el teclado numérico (sin letras).
- Seleccionar una categoría es un solo toque sobre un ícono; el ícono seleccionado tiene un
  estado visual claro.
- Con teclado únicamente: `Tab` desde el monto llega al `fieldset` de categorías como una sola
  parada; las flechas mueven la selección entre íconos; `Enter`/espacio selecciona.
- Un lector de pantalla anuncia el `legend` ("Categoría") y el estado seleccionado de cada
  opción.
- Enviar el formulario con solo monto + categoría (sin tocar cuenta, fecha ni descripción) crea
  la transacción; su `date` refleja el momento de creación (verificado en la respuesta de la API
  o la base de datos, no un valor tecleado).
- Un usuario con exactamente 1 cuenta nunca ve el selector de cuenta; un usuario con 2+ cuentas
  sí lo ve, preseleccionado en la primera.
- `QuickTransactionModal` (abierto vía FAB → "Gasto rápido") renderiza el mismo formulario dentro
  de `ModalShell`, sin divergencia de comportamiento respecto a `/capture`.

---

### 10.3 — Tag de método de pago en la captura

**Confirmado 100% frontend** — ver hallazgo 4: backend completo, cero UI en cualquier pantalla.

**Decisión 10.3.1 — el selector de método de pago vive dentro de "Más opciones" (el mismo
`<details>` de la descripción, introducido en 10.2), no como un cuarto toque siempre visible.**
Mantiene literal el objetivo de "3 interacciones" del ROADMAP (monto → categoría → guardar) para
el camino feliz. Valor por defecto: `'cash'` — coincide con el tipo de cuenta por defecto
("Efectivo") que Fase 8 crea automáticamente al registrarse. Recordar el último método usado (vía
`localStorage`) es una mejora razonable pero no la pide el ROADMAP — se deja fuera, no bloqueante.

**Decisión 10.3.2 — UI: 3 botones tipo chip (segmented control), reusando el patrón visual del
toggle Gasto/Ingreso ya existente (`QuickTransactionModal.tsx:109-132`), no un `<Select>` ni un
tercer grid de radios nativos.** Un `<Select>` reintroduciría el dropdown que todo el rediseño
busca evitar. Un grid de radios (como el de categorías, 10.2.3) sería redundante y visualmente
ruidoso justo debajo del grid de categorías para solo 3 opciones, cuando ya existe en el mismo
archivo un patrón de toggle de pocas opciones — reusarlo mantiene consistencia interna sin
inventar un tercer patrón de selección en la misma pantalla. Nota (relacionada con el hallazgo
9): el toggle Gasto/Ingreso que se está reusando como plantilla no tiene `aria-pressed` — el chip
de método de pago hereda ese mismo gap al copiar el patrón. No se corrige aquí (no está en el
alcance nombrado por el ROADMAP para Fase 10); se dejan ambos igual de incompletos en vez de
corregir uno y no el otro, para no generar una inconsistencia nueva entre dos controles
gemelos.

**Pasos:**
1. `TransactionCaptureForm.tsx`: `const [paymentMethod, setPaymentMethod] =
   useState<'cash' | 'card' | 'transfer'>('cash');`.
2. Agregar el chip de 3 opciones ("Efectivo"/"Tarjeta"/"Transferencia" → `cash`/`card`/
   `transfer`, `schemas.py:119-122`) dentro del bloque "Más opciones" creado en 10.2.
3. Incluir `payment_method: paymentMethod` en el objeto de `createMutation.mutate({...})`.
4. Resetear `paymentMethod` a `'cash'` en el `onSuccess` de la mutation, junto al resto de
   resets (`amount`, `categoryId`, `description`).

**Estimación:** 4h (heredada del ROADMAP) — confirmada holgada: cero cambios de backend, reusa
un patrón visual existente en vez de inventar uno.

**Criterio de aceptación:**
- Crear una transacción sin abrir "Más opciones" persiste `payment_method="cash"` (verificado en
  la respuesta de la API o la base de datos, no solo visualmente).
- Abrir "Más opciones", elegir "Tarjeta" y guardar persiste `payment_method="card"`.
- El chip es operable con teclado igual que el toggle Gasto/Ingreso existente (mismo componente
  base, mismo nivel — no mejor ni peor — de accesibilidad).

---

### 10.5 — Corregir el fallo silencioso del submit

**Problema confirmado:** hallazgo 3, `QuickTransactionModal.tsx:87` (se mueve a
`TransactionCaptureForm.tsx` tras la extracción de 10.2). `return` sin ninguna señal.

**Decisión 10.5.1 — un `toast.error` por campo faltante, sin construir validación granular por
campo con foco en el primer error.** `docs/ROADMAP.md` Fase 12 ya tiene un ítem dedicado
("Validación de formularios por campo, con foco en el primer error al hacer submit — 1d") que
cubre exactamente ese patrón para *todos* los formularios del proyecto. Construirlo aquí para uno
solo se adelantaría a ese ítem y probablemente generaría un patrón distinto al que Fase 12 termine
adoptando de forma consistente. El trabajo de Fase 10 es más angosto: reemplazar el silencio total
por *alguna* señal, usando el idioma de error que ya usa el resto del formulario (`sonner`,
`toast.error`, igual que el `onError` de la mutation en la línea 80-82) en vez de introducir un
banner inline nuevo solo para este caso.

**Complemento recomendado, no exigido por la estimación de 2h del ROADMAP:** mover el foco al
campo que falta (`ref.current?.focus()`) al fallar la validación, para que un usuario de teclado o
lector de pantalla llegue directo al punto a corregir en vez de depender solo del toast. Costo
marginal (un `useRef`, ya casi necesario por el `autoFocus` actual del monto).

**Pasos:**
1. En `handleSubmit`, reemplazar:
   ```tsx
   if (!effectiveAccountId || !categoryId || !amount) return;
   ```
   por ramas explícitas, cada una con un `toast.error(...)` describiendo el campo faltante
   (ej. "Ingresa un monto", "Elige una categoría", o un mensaje combinado si ambos faltan), antes
   de retornar.
2. Agregar un `ref` al `Input` de monto (o al `fieldset` de categorías) y llamar `.focus()` en la
   rama correspondiente al campo que falta.

**Estimación:** 2h (heredada del ROADMAP) — correcta como trabajo aislado; ver "Orden de
ejecución" sobre por qué debe implementarse en el mismo pase que 10.2 (mismo `handleSubmit`).

**Criterio de aceptación:**
- Enviar sin monto muestra un toast nombrando el campo faltante; no hay ningún no-op silencioso.
- Enviar con monto pero sin categoría muestra un toast distinto (o uno combinado, según se
  elija); tampoco hay no-op silencioso.
- Tras el error, el foco queda en el campo a corregir (verificado navegando solo con teclado).
- Un formulario completo sigue enviándose sin que aparezca ningún toast de error (no hay
  regresión).

---

### 10.4 (frontend) — Enviar `Idempotency-Key` desde el formulario de captura

**Diseño del backend correspondiente:** ver sección "Tareas de Backend", ítem 10.4. Esta mitad
solo cubre el lado del cliente.

**Decisión 10.4.1 — generar la clave con `crypto.randomUUID()` una vez por montaje del
formulario, y regenerarla tras cada envío exitoso.** El propósito de la clave es que **reintentos
de la misma acción lógica** (el mismo toque de "Guardar" repetido por el usuario tras una mala
señal de red) reusen la misma clave, mientras que **una transacción nueva** (después de haber
guardado la anterior con éxito) use una clave distinta. Generar la clave en el montaje del
componente y solo rotarla en `onSuccess` cumple exactamente esa distinción sin lógica adicional:
mientras el usuario sigue reintentando el mismo envío fallido, el componente no se desmonta ni
cambia de clave.

**Pasos:**
1. `TransactionCaptureForm.tsx`: `const [idempotencyKey, setIdempotencyKey] =
   useState(() => crypto.randomUUID());`.
2. En `createMutation`, pasar el header explícito:
   `api.post('transactions/', newTx, { headers: { 'Idempotency-Key': idempotencyKey } })`.
3. En el `onSuccess` de la mutation, junto a los demás resets, regenerar la clave:
   `setIdempotencyKey(crypto.randomUUID())`.
4. Verificar que tanto `/capture` como `QuickTransactionModal` **remontan** el componente en cada
   apertura (patrón `{isOpen && <TransactionCaptureForm ... />}` o equivalente) — si en algún
   punto el componente permanece montado entre aperturas del modal, agregar un `useEffect` que
   regenere la clave cuando `isOpen` pasa de `false` a `true`, para no reusar por accidente la
   clave de una captura ya completada.
5. **Sin cambios en `frontend/lib/api.ts`** — verificado: un header pasado en el tercer argumento
   de `api.post(...)` viaja en `config.headers`, y el interceptor de refresh de token
   (`lib/api.ts`, el bloque `error.response?.status === 401`) reintenta la petición original vía
   `return api(originalRequest);`, reusando el mismo objeto `config` — el header de idempotencia
   sobrevive automáticamente ese reintento interno sin ninguna modificación al interceptor.

**Estimación:** incluida en la 1d total de 10.4 del ROADMAP (ver desglose en la sección de
Backend).

**Criterio de aceptación:**
- Dos toques rápidos sobre "Guardar" antes de que la mutation resuelva disparan un solo `POST`
  (esto ya ocurre hoy porque `Button` deshabilita el botón mientras `loading` — la
  `Idempotency-Key` protege el caso que este guard *no* cubre: una petición que sí salió al
  servidor pero cuya respuesta se perdió, y el usuario reintenta manualmente creyendo que no se
  envió).
- Verificado en las herramientas de red del navegador: un reintento manual del mismo envío fallido
  reusa el mismo header `Idempotency-Key`; una captura nueva tras un envío exitoso usa un valor
  distinto.

---

## Tareas de Backend

### 10.4 (backend) — Idempotencia (`Idempotency-Key`) en `POST /transactions`

**Problema confirmado (hallazgo 6):** cero mecanismo existente. Diseño completo a continuación —
alcance explícitamente acotado a `POST /transactions`, tal como pide el ROADMAP ("no expandas a
los otros verbos salvo que lo justifiques" — no se justifica aquí: `PUT`/`DELETE` de transacciones
no están en el alcance de este ítem y agregar idempotencia ahí es un problema distinto, sin
ningún síntoma reportado en `docs/TODO.md`).

**Decisión 10.4.1 — tabla nueva `idempotency_keys`, no una columna `idempotency_key` nullable
directo en `Transaction`.** Ambas opciones resuelven el problema; se evalúan explícitamente:
- *Columna nullable en `Transaction`* con un índice único parcial `WHERE idempotency_key IS NOT
  NULL` (mismo patrón que `Budget.uq_budgets_user_category_period_active`,
  `backend/app/models/models.py:111-122`) sería viable y más barata en líneas de código. Se
  descarta porque conflaría dos responsabilidades distintas en la misma fila: "el registro
  contable" y "la bitácora de reintentos seguros" — y porque el flujo de idempotencia necesita
  poder responder "¿ya existe una transacción para esta clave?" **antes** de decidir si crea una
  fila nueva, lo cual es más natural con una tabla separada (una consulta simple por
  `(user_id, key)`) que con una columna que vive en la misma tabla cuyo INSERT se está intentando
  evitar duplicar.
- *Tabla separada `IdempotencyKey`* (elegida): mantiene `Transaction` limpio de una columna casi
  siempre `NULL` que no tiene relación con el dominio contable, y separa con claridad "¿esta
  petición ya se procesó?" de "¿cuál es el saldo de esta cuenta?" — el código de
  `crear_transaccion` que muta `Account.balance` no necesita razonar sobre reintentos en absoluto,
  solo sobre si debe ejecutarse o no.
- **No se generaliza a una tabla polimórfica** (`resource_type` + `resource_id` para cubrir
  cualquier endpoint futuro) — el ROADMAP acota el alcance a un solo endpoint hoy; generalizar
  ahora sería construir para un caso de uso que no existe todavía (mismo criterio que
  `docs/specs/fase_08_spec.md` Decisión 3.3 aplicó para no crear `app/services/` por un solo caso
  de reutilización). Si Fase 16 u otra fase necesita idempotencia en otro endpoint, una tabla
  chica como esta se puede generalizar entonces sin dolor de migración de datos.

```python
# backend/app/models/models.py
class IdempotencyKey(Base):
    """Bitácora de reintentos seguros para POST /transactions (Fase 10, ROADMAP).

    No es una tabla polimórfica a propósito (Decisión 10.4.1 del spec de Fase 10): el
    alcance actual es un solo endpoint. Sin SoftDeleteMixin, mismo criterio que
    RefreshToken/PasswordResetToken/EmailVerificationToken (Decisión 6.3 de Fase 8):
    es bitácora técnica, no un dato de dominio que el usuario liste o borre.
    """
    __tablename__ = "idempotency_keys"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key = Column(String(255), nullable=False)
    request_hash = Column(String(64), nullable=False)  # sha256 hex del payload canónico
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("uq_idempotency_keys_user_key", "user_id", "key", unique=True),
    )
```
A diferencia del índice único parcial de `Budget` (que necesita `postgresql_where`/`sqlite_where`
porque conviven filas activas y soft-deleted), este es un índice único simple — `IdempotencyKey`
no tiene borrado lógico, así que no hace falta la variante parcial.

**Decisión 10.4.2 — sin TTL ni job de limpieza en esta fase.** El tamaño de la tabla crece 1:1
con las transacciones efectivamente creadas (no se acumulan filas huérfanas sin límite: cada fila
corresponde a una transacción real que ya existe de todas formas) — no hay ninguna presión de
almacenamiento hoy que justifique una tarea de limpieza, y el proyecto no tiene todavía ningún
scheduler (`docs/ROADMAP.md` Fase 14 lo introduce recién ahí). Construir un cron/job de purga
ahora sería infraestructura dimensionada para un problema que no existe todavía — mismo criterio
que ya aplicó el proyecto al diferir el rate limiting distribuido en Fase 7
(`docs/specs/fase_07_spec.md §2.6.1`). Si en el futuro hiciera falta, Fase 14 ya trae el
scheduler que podría agregar `DELETE FROM idempotency_keys WHERE created_at < now() - interval
'X days'` a bajo costo — se deja como nota de trabajo futuro, no como tarea de esta fase.

**Decisión 10.4.3 — payload distinto con la misma clave devuelve `409 Conflict`, no se ignora ni
se sobreescribe.** Se guarda `request_hash` = SHA-256 hex de
`json.dumps(transaccion.model_dump(mode="json"), sort_keys=True)`. Si llega una clave ya conocida
pero con un hash distinto, es casi con certeza un bug del cliente (ej. la Decisión 10.4.1 del lado
frontend falla y una clave vieja se reusa para una captura lógicamente distinta) — devolver la
transacción vieja silenciosamente escondería el bug; crear una segunda transacción real anularía
el propósito mismo de la idempotencia. Un `409` explícito hace visible el problema donde ocurre.

**Decisión 10.4.4 — la concurrencia real se resuelve con el `UNIQUE(user_id, key)` de la base de
datos, no con un lock aplicativo.** Mismo patrón ya establecido en el proyecto para
`crear_presupuesto` (`docs/specs/fase_08_spec.md` Decisión 3.1, paso 3: `try/except
IntegrityError`) — dos peticiones casi simultáneas con la misma clave: la segunda falla el
`INSERT` de `IdempotencyKey` por el índice único, se hace `rollback()` (que también revierte el
`INSERT` de `Transaction` y el `UPDATE` de saldo de la misma transacción de base de datos, porque
comparten un solo `try` con un solo `commit()`), y se vuelve a consultar la fila que ganó la
carrera para devolver esa transacción.

**Caso borde a resolver explícitamente — la transacción referenciada por una clave puede haber
sido borrada (borrado lógico) desde entonces.** `backend/app/core/database.py:46-51`
(`_filtrar_borrados_logicos`) filtra automáticamente cualquier `SELECT` sobre `Transaction`
(hereda `SoftDeleteMixin`) para excluir filas con `deleted_at` poblado — así que un reintento
tardío con una clave cuya transacción original ya fue borrada por el usuario (`DELETE
/transactions/{id}`, `transactions.py:126-158`) va a encontrar la fila de `IdempotencyKey` pero
**no** la `Transaction` asociada (la consulta la excluye). Comportamiento elegido: devolver `409`
explicando que la transacción original ya no existe, en vez de (a) crear una transacción nueva
silenciosamente (rompe la garantía de idempotencia justo en el caso donde más importa: el usuario
ya actuó sobre el resultado original) o (b) un `404` genérico que sugeriría que la clave en sí es
inválida.

**Archivos a modificar:**
- `backend/app/models/models.py` — agregar la clase `IdempotencyKey` (código arriba).
- `backend/app/api/transactions.py::crear_transaccion` (líneas 20-77):
  ```python
  import hashlib
  import json
  from fastapi import APIRouter, Depends, Header, HTTPException
  from sqlalchemy.exc import IntegrityError

  @router.post("/", response_model=schemas.TransactionResponse)
  def crear_transaccion(
      transaccion: schemas.TransactionCreate,
      db: Session = Depends(get_db),
      current_user: models.User = Depends(get_current_user),
      idempotency_key: str | None = Header(None, alias="Idempotency-Key", max_length=255),
  ):
      request_hash = None
      if idempotency_key:
          request_hash = hashlib.sha256(
              json.dumps(transaccion.model_dump(mode="json"), sort_keys=True).encode()
          ).hexdigest()
          existente = (
              db.query(models.IdempotencyKey)
              .filter(
                  models.IdempotencyKey.user_id == current_user.id,
                  models.IdempotencyKey.key == idempotency_key,
              )
              .first()
          )
          if existente:
              if existente.request_hash != request_hash:
                  raise HTTPException(
                      status_code=409,
                      detail="Esta Idempotency-Key ya se usó con datos distintos.",
                  )
              transaccion_previa = (
                  db.query(models.Transaction)
                  .filter(models.Transaction.id == existente.transaction_id)
                  .first()
              )
              if not transaccion_previa:
                  # La transacción original fue borrada (soft-delete) desde el envío
                  # original — ver caso borde en el spec de Fase 10, ítem 10.4.
                  raise HTTPException(
                      status_code=409,
                      detail="La transacción original de esta Idempotency-Key ya no existe.",
                  )
              return transaccion_previa

      # ... validación de cuenta y categoría sin cambios (líneas 26-48 actuales) ...

      nueva_transaccion = models.Transaction(**transaccion.model_dump(exclude_none=True), user_id=current_user.id)
      nueva_transaccion.currency = cuenta.currency
      delta = transaccion.amount if transaccion.type == "income" else -transaccion.amount

      try:
          db.add(nueva_transaccion)
          db.execute(
              update(models.Account)
              .where(models.Account.id == transaccion.account_id, models.Account.deleted_at.is_(None))
              .values(balance=models.Account.balance + delta)
          )
          if idempotency_key:
              db.flush()  # asigna nueva_transaccion.id antes del commit final
              db.add(models.IdempotencyKey(
                  user_id=current_user.id,
                  key=idempotency_key,
                  request_hash=request_hash,
                  transaction_id=nueva_transaccion.id,
              ))
          db.commit()
          db.refresh(nueva_transaccion)
          return nueva_transaccion
      except IntegrityError:
          db.rollback()
          # Se perdió la carrera: otra petición con la misma clave ya insertó primero.
          existente = (
              db.query(models.IdempotencyKey)
              .filter(models.IdempotencyKey.user_id == current_user.id, models.IdempotencyKey.key == idempotency_key)
              .first()
          )
          if existente:
              return db.query(models.Transaction).filter(models.Transaction.id == existente.transaction_id).first()
          raise HTTPException(status_code=500, detail="Error interno al procesar la transacción contable.") from None
      except Exception:
          db.rollback()
          logger.exception("Error al crear transacción para el usuario %s", current_user.id)
          raise HTTPException(status_code=500, detail="Error interno al procesar la transacción contable.") from None
  ```
  Sin cambios en `TransactionCreate`/`TransactionResponse` (`schemas.py`) — la clave viaja como
  header HTTP, no como campo del body; no agregar un campo `idempotency_key` redundante al
  schema.
- **Migración Alembic nueva**, generada con `alembic revision --autogenerate` tras agregar el
  modelo, `down_revision = "f8c1e5a7d902"` (head actual, la migración de Fase 8) — revisada a
  mano antes de commitear, como exige `CLAUDE.md` para todas las migraciones del proyecto (no son
  100% autogeneradas a ciegas). Contenido esperado: `CREATE TABLE idempotency_keys (...)` +
  `CREATE UNIQUE INDEX uq_idempotency_keys_user_key ON idempotency_keys (user_id, key)`.

**Testing** (agregar a `backend/tests/test_transactions.py`, reusando `client`, `auth_headers`,
`make_account`, `make_category` — hallazgo 10):
- Misma `Idempotency-Key` + payload idéntico enviado dos veces → la segunda respuesta devuelve el
  mismo `id` de transacción que la primera, y el saldo de la cuenta se movió **una sola vez**
  (assert exacto del delta, no duplicado) — es el caso central que motiva todo el ítem.
- Misma clave + payload distinto (ej. `amount` distinto) → la segunda petición devuelve `409`.
- **Sin header `Idempotency-Key`** → comportamiento idéntico al actual, sin ninguna diferencia —
  el test de regresión más importante, porque protege las 439 líneas ya existentes de
  `test_transactions.py`, que nunca envían el header.
- Dos usuarios distintos usando el mismo string literal como clave → ambos tienen éxito de forma
  independiente (el constraint es `(user_id, key)`, no global) — cubre a un cliente descuidado
  que use una clave constante en vez de un UUID real.
- (Opcional, prioridad baja) Simular la carrera real con hilos concurrentes es más valioso que un
  test secuencial, pero más frágil de escribir de forma confiable contra el fixture de SQLite
  `StaticPool` (`conftest.py:24-30`) que usa toda la suite — se recomienda verificación manual en
  staging en vez de un test automatizado obligatorio para esta fase, con el mismo criterio que
  `docs/specs/fase_08_spec.md` ya aplicó al pedir verificación empírica (no solo un test) para el
  comportamiento de `with_loader_criteria` sobre `UPDATE`.

**Estimación:** 1d total en el ROADMAP para todo el ítem 10.4 (backend + frontend) — desglose
recomendado: ~7h backend (tabla, migración, lógica del endpoint, 4 tests) + ~1h frontend (ver
10.4 frontend arriba). El total de 1d se sostiene.

**Criterio de aceptación:**
- Un `POST /api/v1/transactions/` sin header `Idempotency-Key` se comporta exactamente igual que
  hoy (todos los tests existentes de `test_transactions.py` siguen pasando sin modificación).
- Dos `POST` idénticos con la misma clave mueven el saldo de la cuenta una sola vez.
- Dos `POST` con la misma clave y payloads distintos devuelven `409` en el segundo.
- La migración corre limpio sobre una base vacía y sobre la base con el seed de `test@test.com`
  (`backend/app/core/seed.py`).

---

## Resumen de archivos tocados por ítem

| Ítem | Archivos |
|---|---|
| 10.1 ruta principal | `frontend/lib/hooks/useRequireAuth.ts` (nuevo), `frontend/app/(dashboard)/layout.tsx`, `frontend/app/capture/layout.tsx` (nuevo), `frontend/app/capture/page.tsx` (nuevo), `frontend/app/(auth)/login/page.tsx`, `frontend/docs/ARCHITECTURE.md` (doc) |
| 10.2 rediseño 3 toques | `frontend/components/forms/TransactionCaptureForm.tsx` (nuevo), `frontend/components/modals/QuickTransactionModal.tsx` (reescrito a wrapper), `frontend/types/api.ts` |
| 10.3 método de pago | `frontend/components/forms/TransactionCaptureForm.tsx` (mismo archivo de 10.2) |
| 10.5 fallo silencioso | `frontend/components/forms/TransactionCaptureForm.tsx` (mismo archivo de 10.2) |
| 10.4 (frontend) | `frontend/components/forms/TransactionCaptureForm.tsx` (mismo archivo de 10.2); `frontend/lib/api.ts` verificado, sin cambios |
| 10.4 (backend) | `backend/app/models/models.py`, `backend/app/api/transactions.py`, nueva migración Alembic (`backend/alembic/versions/`), `backend/tests/test_transactions.py` |
| Cruzando toda la fase | `backend/docs/API_REFERENCE.md` + `frontend/docs/API_CONTRACT.md` (documentar el header `Idempotency-Key` como contrato compartido, por convención de `CLAUDE.md`) |

---

## Cierre

Este documento no implementa ningún cambio en el repositorio — es el desglose ejecutable de la
sección "Fase 10" de `docs/ROADMAP.md`, con archivos, líneas y decisiones de diseño concretas
para que un frontend-engineer/backend-engineer pueda partir directamente de aquí sin tener que
re-explorar el código para tomar las mismas decisiones. Todos los hallazgos de este documento
(estado real de `payment_method`, ausencia total de idempotencia, ausencia de rate limiting en
`POST /transactions`, ausencia de cualquier patrón de grid de radios en el proyecto, el único
call site del redirect post-login) fueron verificados contra el código real de `backend/` y
`frontend/` el 2026-08-23, no inferidos del texto del ROADMAP. Ningún archivo del repositorio
fuera de `docs/specs/fase_10_spec.md` fue modificado al producir este documento.
