# Spec — Fase 12: Pulido visual y omisiones estratégicas

> Plan de implementación detallado para los 10 ítems de Fase 12 del [ROADMAP](../ROADMAP.md).
> Fuente de verdad de alcance: `docs/ROADMAP.md` (sección "Fase 12 — Pulido visual y omisiones
> estratégicas"). Este documento no cambia el alcance ahí definido — lo desglosa en tareas
> ejecutables, con archivos concretos, líneas, decisiones de diseño numeradas y una estimación de
> horas revisada contra el código real.
>
> **No implementa nada.** Es el hand-off para quien vaya a codear (backend-engineer /
> frontend-engineer). Ningún archivo del repositorio fuera de
> `docs/specs/fase_12_spec.md` fue modificado al producir este documento.

Estado del repo en el momento de escribir esto (2026-09-05): Fases 7–11 están completas y
mergeadas — cimientos multi-usuario, modelo de datos del nuevo MVP, accesibilidad base (Fase 9),
captura en 3 toques (Fase 10) y el dashboard de flujo mensual (Fase 11, con `SummaryCard`,
`BudgetRing` y `CategoryBreakdownBars` ya construidos). La Fase 12 del ROADMAP describe el estado
de la UI en términos generales ("toda tarjeta usa el mismo patrón...", "hoy solo hay 2 ejemplos
correctos de sombra tintada...") sin línea de código de respaldo. La exploración de abajo confirma
algunos de esos enunciados literalmente, precisa otros (el patrón real es más irregular de lo que
el ROADMAP describe) y encuentra un hallazgo central que cambia el enfoque del ítem más grande de
la fase (§12.8): la pieza que el ROADMAP pide construir ya existe en el código y nunca se conectó.

Este documento asume el mismo criterio de "aditivo, no reemplazo" que Fase 9/10/11 ya establecieron
y evita proponer infraestructura nueva (librerías de validación, sistemas de theming de sombra) para
un problema que se resuelve extendiendo lo que ya está construido.

---

## Hallazgos de exploración que corrigen/precisan el ROADMAP

1. **Los filtros de Transacciones no usan `localStorage` hoy — solo `useState`, sin ninguna
   persistencia.** `frontend/app/(dashboard)/transactions/page.tsx:80-84`: `startDate`, `endDate`,
   `categoryFilter`, `accountFilter`, `datePreset` son `useState` planos. La lectura literal del
   ROADMAP ("viven en `useState`/`localStorage`") describe correctamente el síntoma para
   Transacciones (se pierden al recargar) pero por una causa distinta a la que sugiere: aquí nunca
   hubo intento de persistencia, ni siquiera local.

2. **Los filtros de Analítica sí usan `localStorage`, vía un hook compartido no mencionado por el
   ROADMAP.** `frontend/app/(dashboard)/analytics/page.tsx:71-84` usa `usePersistedState`
   (`frontend/hooks/usePersistedState.ts:5-28`) para `barPeriod`, `seriesMode`, `donutPeriod`,
   `categoryType` y `netMode` — 5 claves (`analytics-barPeriod`, etc.). Esto sí sobrevive a un
   recargado de página en el mismo navegador, pero no resuelve "compartir el link": el estado vive
   en el `localStorage` del dispositivo, no en la URL, así que un link copiado a otra persona (o a
   una pestaña de incógnito) siempre abre con los valores por defecto. `hiddenCategories` (línea 85,
   un `Set` de categorías ocultadas en la leyenda del donut) es la única pieza de estado de filtro
   que ya está en `useState` puro sin persistencia — y así debe quedarse (ver Decisión 12.1.3).

3. **Ninguna de las dos páginas está hoy envuelta en `<Suspense>` — requisito no opcional de
   Next.js App Router para usar `useSearchParams()`.** Ni `transactions/page.tsx` ni
   `analytics/page.tsx` importan `useSearchParams` hoy (grep confirmado, cero resultados). Para
   sincronizar filtros con la URL hace falta ese hook, y Next.js falla el build
   ("`useSearchParams() should be wrapped in a suspense boundary`") si el componente que lo llama no
   está envuelto. El propio proyecto ya resuelve este mismo requisito en dos lugares:
   `frontend/app/(auth)/login/page.tsx:166-172` y `frontend/app/(auth)/reset-password/page.tsx:193-
   199` separan un componente interno (`LoginForm`, `ResetPasswordForm`) del `export default`, que
   solo envuelve en `<Suspense>`. §12.1 reutiliza ese patrón exacto, no uno nuevo.

4. **El patrón "toda tarjeta usa `border + shadow-sm + bg-surface`" que describe el ROADMAP no es
   el estado real — es más irregular, y en un sentido preciso, más disciplinado de lo que suena.**
   Verificado con `grep -rn "shadow-"` en todo `frontend/` (ver detalle abajo). Los componentes
   nuevos de Fase 11 (`components/ui/SummaryCard.tsx:25-28`, `components/charts/BudgetRing.tsx:46`,
   `components/charts/CategoryBreakdownBars.tsx:33`) y las tarjetas de "ítem de lista" repetido
   (`app/(dashboard)/accounts/page.tsx:216`, `app/(dashboard)/budgets/page.tsx:159`,
   `app/(dashboard)/categories/page.tsx:156`) **no tienen ningún `shadow-*`** — solo
   `border + bg-surface` (+ `hover:border-primary/30` en las de lista). `shadow-sm` aparece
   únicamente en "contenedores de lista" (el panel de filtros y el wrapper de la tabla en
   `transactions/page.tsx:264,362`, el wrapper de transacciones recientes en
   `app/(dashboard)/page.tsx:285`, los wrappers de historial en `accounts/[id]/page.tsx:193` y
   `categories/[id]/page.tsx:184`, y los wrappers de gráfico en `CashflowChart.tsx:80` y
   `CategoryDonutChart.tsx:114`). Es decir: **la distinción contenedor-vs-ítem que el ROADMAP pide
   crear (§12.2) ya existe de facto** en casi todo el proyecto — el hueco real es más pequeño de lo
   que sugiere la lectura literal: `CategoryBreakdownBars.tsx:33` es la única pieza que, siendo
   funcionalmente un contenedor de lista igual que los otros seis, no siguió el patrón (llegó sin
   `shadow-sm` en Fase 11). Ver Decisión 12.2.1.

5. **Los "2 ejemplos correctos" de sombra tintada que cita el ROADMAP existen, pero uno de los dos
   valores citados es impreciso.** `components/Sidebar.tsx:88` usa exactamente
   `shadow-primary/10` como dice el ROADMAP. Pero `components/FloatingActionButton.tsx:28` usa
   `shadow-primary/20 hover:shadow-primary/30` — no `/10`. No cambia el diagnóstico (ambos tiñen
   con `primary`, ninguno usa el negro por defecto de Tailwind) pero si alguien fuera a copiar
   literalmente "`/10`" como el valor de referencia para replicar en otros lados, reproduciría un
   valor que no corresponde a ninguno de los dos ejemplos reales.

6. **`app/globals.css` no define ningún token de sombra** (`grep -n "shadow" app/globals.css`
   devuelve cero resultados) — todas las `shadow-sm/md/lg/xl/2xl` sin sufijo de color usan el negro
   semitransparente por defecto de Tailwind. En el tema oscuro (`--color-background: #0b1220`,
   `app/globals.css:6`, casi negro) una sombra negra por defecto es casi invisible — el problema que
   describe el ROADMAP es real, pero solo se manifiesta en modo oscuro: en el tema claro
   (`--color-background: #f8fafc`, línea 60, casi blanco) el tinte propuesto por el ítem 3
   ("tintar con el color de fondo") tendrá un efecto visualmente casi nulo, porque el fondo ya es
   casi blanco. Se documenta como limitación conocida en vez de prometer una mejora pareja en ambos
   temas (ver Decisión 12.3.1).

7. **El estado de carga real no es "Skeleton en el dashboard, `Loader2` en el resto" — es más
   mixto.** `app/(dashboard)/accounts/page.tsx` usa **ambos** patrones en el mismo archivo: el
   listado principal de cuentas hace un *early return* con `Loader2` si `isLoading`
   (líneas 173-176), pero el bloque de saldos totales (`loadingBalances`, línea 198) ya usa
   `<Skeleton>` desde Fase 11. `CategoryBreakdownBars.tsx:34-44` también ya usa `Skeleton` (con la
   forma de las barras). El inventario real de páginas con el *early-return* `Loader2` que sí hay
   que convertir es **7 archivos**, no los 4 que el ROADMAP nombra explícitamamente
   ("Transacciones, Cuentas, Presupuestos y Categorías"): `transactions/page.tsx:240-246`,
   `budgets/page.tsx:125-128` (aprox.), `categories/page.tsx:125-128` (aprox.),
   `accounts/page.tsx:173-176` (el early-return principal, no el bloque ya corregido),
   `accounts/[id]/page.tsx:155-158`, `categories/[id]/page.tsx:153-157` y
   `analytics/page.tsx:163-169` — las últimas tres no las nombra el ROADMAP pero comparten
   exactamente el mismo patrón y la misma pantalla de detalle que sí menciona ("Cuentas"). Fuera de
   alcance a propósito: `app/(auth)/verify-email/page.tsx`'s `Loader2` (verificación de un token
   al montar, sin contenido de lista que anticipar) y el `Loader2` interno de
   `components/ui/Button.tsx:48` (spinner de envío de un botón, no carga de página) — ver Decisión
   12.4.2.

8. **`app/favicon.ico` es el default de Next.js y los 5 SVG de scaffold están confirmados sin
   ninguna referencia en el código.** `file app/favicon.ico` → "MS Windows icon resource" genérico
   de 25.9 KB (el placeholder que Next.js genera al hacer `create-next-app`, sin ningún ícono de
   marca). `grep -rn "next.svg|vercel.svg|globe.svg|file.svg|window.svg"` en todo `frontend/`
   (excluyendo `node_modules`) devuelve cero resultados — los 5 archivos en `public/` no los importa
   ni referencia ningún componente.

9. **`app/not-found.tsx` no existe** (`find app -iname "*not-found*"` no devuelve nada) — una ruta
   inexistente cae hoy en el 404 genérico de Next.js, sin ningún elemento visual de Oikos.

10. **No hay ningún skip-link, y el único `<main>` del árbol de layouts vive en el shell
    autenticado.** `app/layout.tsx` (layout raíz) no tiene ningún `<main>` ni landmark — es solo
    `<body><AppConfigProvider><QueryProvider>{children}...`. `app/(auth)/layout.tsx` tampoco tiene
    `<main>` (es una tarjeta centrada sin navegación). El único `<main>` existente está en
    `app/(dashboard)/layout.tsx:47`, sin `id`. Esto no es un problema — es la confirmación de que el
    skip-link **solo tiene sentido en el shell del dashboard**: es el único layout con navegación
    lateral (`Sidebar`, con 6 enlaces + toggle + tema + logout, ~9 elementos enfocables) que precede
    al contenido en el DOM. `(auth)` y `app/capture/page.tsx` no tienen nada que saltar.

11. **`Input` y `Select` ya soportan un prop `error?: string` con estilo de borde/mensaje
    incorporado — y no lo usa ningún formulario del proyecto.** Confirmado en
    `components/ui/Input.tsx:5-31` y `components/ui/Select.tsx:5-33`: ambos aceptan `error`, y
    cuando está presente aplican `border-danger/50 focus-visible:ring-danger/50` al control y
    renderizan `<span className="text-danger text-xs">{error}</span>` debajo. `grep -rn "error={"
    --include="*.tsx"` en todo `frontend/` devuelve **cero resultados**. Este es el hallazgo central
    de todo el documento: el ROADMAP describe §12.8 como si hubiera que construir validación por
    campo desde cero ("Hoy los formularios solo tienen un banner de error genérico y validación
    nativa `required`"), pero la pieza visual ya existe desde Fase 9 y simplemente nunca se conectó
    a ningún `onSubmit`. §12.8 es un trabajo de **integración**, no de construcción de un componente
    nuevo. Ver Decisión 12.8.1.

12. **La validación nativa (`required`, `minLength`, `type="email"`) ya hace foco en el primer
    campo inválido — el hueco real no es "falta de foco", es la falta de estilo propio y de reglas
    que el navegador no puede validar.** Confirmado por el comportamiento estándar de HTML5
    constraint validation: si un `<form>` no tiene `noValidate`, el navegador bloquea el `submit`
    (el `onSubmit` de React ni siquiera se ejecuta) y hace foco + muestra un globo nativo en el
    primer campo `required`/`minLength`/`type` inválido, antes de que corra cualquier JS. Los 4
    formularios de auth y los 3 modales CRUD (`accounts/page.tsx:297,328,365`,
    `categories/page.tsx:226,275`, `budgets/page.tsx:229,247,257`) dependen hoy de este mecanismo
    para "campo vacío". El gap real, verificado, es doble: (a) el globo nativo del navegador es
    visualmente inconsistente entre navegadores y no respeta la paleta oscura fintech del proyecto
    (`frontend/docs/UI_SYSTEM.md`: "no introducir... layouts genéricos"); y (b) reglas que el
    navegador **no puede** validar por sí solo — contraseñas que no coinciden
    (`register/page.tsx:25-29`, `reset-password/page.tsx:97-99`, ya validadas a mano pero mostradas
    en el banner genérico, no por campo), montos que deben ser `> 0` (ningún formulario CRUD valida
    esto hoy, solo `required`, que acepta `0` o `-5` como "no vacío"). §12.8 debe resolver ambos, no
    solo el segundo.

13. **El modal de edición manual de `transactions/page.tsx` usa `<input>`/`<select>` crudos, no
    `Input`/`Select` — deuda ya documentada en el ROADMAP, no un hallazgo nuevo, pero directamente
    relevante para el alcance de §12.8.** Confirmado en `transactions/page.tsx:502-577` (5 controles
    crudos con `focus:` en vez de `focus-visible:` y sin `id`/`htmlFor` consistente). El propio
    `docs/ROADMAP.md`, sección "Pendientes heredados de fases anteriores", ya registra esto como
    diferido a propósito de Fase 9 ("vale la pena resolverlo migrando ese modal a los componentes
    `Input`/`Select` compartidos"). No se puede aplicar el prop `error` de `Input`/`Select` a un
    `<input>` crudo — así que §12.8, al tocar exactamente este modal para agregarle validación por
    campo, es el momento natural de resolver la migración pendiente en la misma pasada en vez de
    validar sobre markup que de todos modos hay que reemplazar después. Ver Decisión 12.8.2.

14. **`tabular-nums` no aparece en ningún punto del proyecto** (`grep -rn "tabular-nums"` en
    `frontend/`, cero resultados, ni en `.tsx` ni en `globals.css`) — coincide con la lectura
    literal del ROADMAP, sin matices.

15. **No existe ninguna página ni enlace relacionado con privacidad o términos, y no hay ningún
    `<footer>` en el shell autenticado.** `grep -rln "privacidad|terminos|términos|privacy|terms"`
    en `frontend/` devuelve cero resultados. `app/(dashboard)/layout.tsx` no tiene ningún elemento
    `<footer>` — el ROADMAP no especifica dónde deben vivir estos enlaces, así que §12.10 debe
    decidir la ubicación además del contenido (ver Decisión 12.10.1).

---

## Orden de ejecución recomendado

A diferencia de Fase 11 (varios bugs de backend con dependencias claras), casi todos los ítems de
Fase 12 son 100% frontend y técnicamente independientes entre sí — el ROADMAP mismo lo trata como
una lista plana. La dependencia real que existe es de **archivos compartidos**, no de lógica: varios
ítems tocan el mismo archivo en regiones distintas, y secuenciarlos reduce fricción de merge sin que
ninguno bloquee técnicamente a otro.

```
Grupo A — Independientes puros, sin ningún archivo compartido con el resto de la fase.
  En paralelo desde el día 1:
  · §12.5 Favicon + limpieza de assets       (frontend/app/favicon.ico, frontend/public/*.svg)
  · §12.6 Página 404                          (app/not-found.tsx, nuevo)
  · §12.7 Skip-link                           (app/(dashboard)/layout.tsx)
  · §12.10 Enlaces legales                    (app/legal/**, nuevo — más un footer en Sidebar.tsx)

Grupo B — Jerarquía visual, mismo lote de archivos, secuenciar internamente.
  Independiente de A, C y D. En paralelo con todos ellos desde el día 1:
  1. §12.2 Diferenciar tarjetas (decide qué se eleva: SummaryCard.tsx, dashboard/page.tsx,
     accounts/page.tsx, CategoryBreakdownBars.tsx)
  2. §12.3 Tintar sombras (aplica sobre los mismos archivos de (1) más ~8 archivos adicionales
     no tocados por (1) — hacerlo después evita decidir el tinte dos veces sobre el mismo
     componente)
  3. §12.9 tabular-nums (mismo lote de archivos de montos que (1)/(2) — bundlear en la misma
     sesión es más barato que 3 pasadas separadas sobre SummaryCard.tsx/BudgetRing.tsx)

Grupo C — Filtros en URL.
  · §12.1 URL-sync — crea el hook nuevo primero (frontend/hooks/useQueryParamState.ts, sin
    dependencias), luego lo aplica a transactions/page.tsx y analytics/page.tsx (reestructura
    completa: Suspense + reemplazo de useState/usePersistedState).

Grupo D — Loading states.
  · §12.4 — de los 7 archivos reales (hallazgo 7), 5 son independientes de todo lo demás y
    pueden hacerse en paralelo desde el día 1: budgets/page.tsx, categories/page.tsx,
    accounts/page.tsx, accounts/[id]/page.tsx, categories/[id]/page.tsx.
  · Los 2 restantes (transactions/page.tsx, analytics/page.tsx) comparten archivo con el
    Grupo C — conviene aplicarles el cambio de Skeleton DESPUÉS de que el Grupo C termine su
    reestructuración de esos dos archivos, para no reescribir el mismo bloque dos veces.

Grupo E — Validación por campo.
  · §12.8 — las partes independientes (login, register, forgot-password, reset-password,
    TransactionCaptureForm.tsx) no comparten archivo con nada más y pueden empezar el día 1.
  · Las partes que sí comparten archivo con el Grupo D (transactions/page.tsx — incluye la
    migración del modal de edición del hallazgo 13 —, budgets/page.tsx, categories/page.tsx,
    accounts/page.tsx) conviene hacerlas DESPUÉS de que el Grupo D termine su swap de Skeleton en
    esos mismos archivos, por la misma razón de reducir pasadas redundantes sobre el mismo diff.
```

Ningún ítem bloquea técnicamente a otro — las únicas dependencias son de archivo compartido, no de
diseño ni de datos. Los Grupos A, B, C y las partes independientes de D/E pueden repartirse entre
varios agentes/personas desde el día 1, igual que el criterio ya usado en `docs/specs/fase_09_spec.md`,
`fase_10_spec.md` y `fase_11_spec.md`.

**Estimación total heredada del ROADMAP:** 1d + 4h + 2h + 4h + 2h + 3h + 1h + 1d + 2h + 4h =
8h + 4h + 2h + 4h + 2h + 3h + 1h + 8h + 2h + 4h = **38h (~4.75 días de 8h)**.

**Ajuste tras la exploración de código**, ítem por ítem (justificación completa en cada sección):

| Ítem | ROADMAP | Ajustado | Motivo |
|---|---|---|---|
| §12.1 URL-sync | 8h | 10h | Hook nuevo + envolver 2 páginas en `Suspense` + migrar 10 piezas de estado + decisión de abandonar `localStorage` en Analítica |
| §12.2 Diferenciar tarjetas | 4h | 4h | Sin cambio — el hallazgo 4 muestra que el alcance real es **menor** de lo que sugiere la lectura literal (la mayoría de tarjetas ya está bien) |
| §12.3 Tintar sombras | 2h | 3h | ~15 ubicaciones reales en ~12 archivos (hallazgo 5/6), apretado en 2h pero absorbible en la misma sesión que §12.2 |
| §12.4 Unificar loading | 4h | 6h | 7 archivos reales, no 4 (hallazgo 7) |
| §12.5 Favicon | 2h | 2h | Sin cambio |
| §12.6 Página 404 | 3h | 3h | Sin cambio |
| §12.7 Skip-link | 1h | 1h | Sin cambio — alcance confirmado mínimo (un archivo) |
| §12.8 Validación por campo | 8h | 14h | 9 archivos reales, incluida la migración pendiente del modal de edición de transacciones (hallazgo 13) y el trabajo de reemplazar/complementar validación nativa (hallazgo 12) |
| §12.9 `tabular-nums` | 2h | 2h | Sin cambio |
| §12.10 Enlaces legales | 4h | 4h | Sin cambio (el contenido legal real queda fuera del alcance de este documento) |
| **Total** | **38h** | **49h (~6.1 días de 8h)** | |

El mayor ajuste es §12.8: la lectura literal del ROADMAP subestima cuántos formularios hay que tocar
y no cuenta la migración de markup crudo que el propio ROADMAP ya tenía pendiente en otra sección.

---

## 12.1 URL-sync de filtros en Transacciones y Analítica

### Frontend

**Decisión 12.1.1 — un hook compartido nuevo, `useQueryParamState`, no extender
`usePersistedState`.** Ambos resuelven "que el filtro sobreviva a algo", pero a cosas distintas
(recargar vs. compartir un link) y con mecanismos incompatibles (localStorage vs. URL). Forzar un
solo hook con un flag `source: 'url' | 'localStorage'` complicaría una pieza que hoy es simple en
ambos casos. Nuevo archivo, mismo directorio que `usePersistedState.ts`:

```ts
// frontend/hooks/useQueryParamState.ts
'use client';

import { useCallback } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';

/**
 * Sincroniza un valor de string con un query param de la URL vía router.replace
 * (shallow, sin recargar ni apilar historial por cada cambio). El valor por defecto
 * nunca se escribe en la URL — una URL sin el param equivale a "usa el default".
 *
 * Requiere que el componente que lo usa esté envuelto en <Suspense> (mismo requisito
 * de Next.js App Router que ya aplica a useSearchParams en login/page.tsx y
 * reset-password/page.tsx).
 */
export function useQueryParamState(
  key: string,
  defaultValue: string
): [string, (value: string) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const value = searchParams.get(key) ?? defaultValue;

  const setValue = useCallback(
    (next: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (next === defaultValue || next === '') {
        params.delete(key);
      } else {
        params.set(key, next);
      }
      const query = params.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [key, defaultValue, pathname, router, searchParams]
  );

  return [value, setValue];
}
```

`router.replace` (no `push`) a propósito: cada cambio de filtro no debe apilar una entrada nueva en
el historial del navegador — si lo hiciera, el botón "atrás" navegaría filtro por filtro en vez de
volver a la página anterior, un comportamiento sorprendente que el propio ROADMAP no pide. Se
documenta como decisión explícita, no un descuido.

**Decisión 12.1.2 — Analítica migra por completo de `usePersistedState` a
`useQueryParamState`, sin mantener ambos.** Mantener las dos fuentes (localStorage como fallback si
no hay query param) generaría un tercer estado posible ("¿qué gana, la URL o el localStorage?") sin
ningún beneficio: si el usuario visita `/analytics` sin parámetros, welcome de vuelta a los valores
por defecto es exactamente el comportamiento esperado de un link limpio — no una regresión. Se
documenta como trade-off explícito: Analítica deja de recordar la última vista entre sesiones sin
compartir el link; gana la capacidad de compartir/marcar una vista exacta.

**Decisión 12.1.3 — `skip` (paginación) y `hiddenCategories` (leyenda del donut) se quedan en
`useState` local, sin tocar.** `skip` es un detalle de scroll infinito, no una selección que valga
compartir; `hiddenCategories` es un `Set` arbitrario sin utilidad de "link compartible". El ROADMAP
no los menciona y no hay ninguna razón nueva para incluirlos.

**Decisión 12.1.4 — envolver ambas páginas en `<Suspense>`, mismo patrón que
`login/page.tsx`/`reset-password/page.tsx` (hallazgo 3).**

**Archivos a modificar:**
- `frontend/hooks/useQueryParamState.ts` (nuevo, arriba).
- `frontend/app/(dashboard)/transactions/page.tsx`:
  - Renombrar el cuerpo actual del componente a `TransactionsPageContent` y exportar:
    ```tsx
    export default function TransactionsPage() {
      return (
        <Suspense fallback={<Skeleton className="h-96 rounded-2xl" />}>
          <TransactionsPageContent />
        </Suspense>
      );
    }
    ```
  - Reemplazar los 5 `useState` de filtro (líneas 80-84) por
    `useQueryParamState('start', '')`, `useQueryParamState('end', '')`,
    `useQueryParamState('category', 'all')`, `useQueryParamState('account', 'all')`,
    `useQueryParamState('preset', 'all')`. `resetPagination`/`applyPreset`/`clearFilters` (líneas
    101-165) no cambian de forma, solo de dónde viene el setter.
- `frontend/app/(dashboard)/analytics/page.tsx`:
  - Mismo wrapper `<Suspense>` (renombrar a `AnalyticsPageContent`).
  - Reemplazar los 5 `usePersistedState` (líneas 71-84) por `useQueryParamState` con las mismas
    claves cortas de query param (`bar`, `series`, `donut`, `type`, `neto`) — `neto` se guarda como
    `'true'`/`'false'` string y se compara `=== 'true'` en el resto del componente (no requiere un
    hook booleano separado).
  - Quitar el import de `usePersistedState` (deja de usarse en este archivo; `usePersistedState.ts`
    no se borra — sigue siendo un hook genérico disponible si algún otro caso futuro lo necesita).
- `frontend/docs/STATE_AND_FETCHING.md`: documentar el nuevo patrón junto a los ya existentes
  ("Estado local" → agregar una subsección "Filtros en URL" con `useQueryParamState`, distinta de
  `usePersistedState`, igual que Fase 11 documentó `dashboard-category-breakdown`/`accounts-summary`
  al agregarlas).

**Testing:** sin suite de frontend (`docs/TODO.md`: automatizarlo "solo si el proyecto crece").
Verificación manual: recargar `/transactions` con filtros aplicados los conserva; copiar la URL con
`?category=3&preset=month` en una pestaña nueva reproduce exactamente esa vista; limpiar filtros
(`clearFilters`) deja la URL sin query string; en Analítica, cambiar `donutPeriod` no reescribe
`barPeriod` en la URL si no cambió (cada `useQueryParamState` solo toca su propia clave).

**Criterio de aceptación:**
- Recargar cualquiera de las dos páginas con filtros activos los conserva.
- Un link con query params reproduce la vista exacta en cualquier navegador/sesión, sin depender de
  `localStorage`.
- El estado por defecto de ambas páginas produce una URL sin query string.
- `docs/TODO.md`: sin entrada nueva — este ítem no introduce deuda, cierra la que describía el
  ROADMAP.

---

## 12.2 Diferenciar visualmente las tarjetas

### Frontend

**Decisión 12.2.1 — no agregar sombra a toda tarjeta; cerrar el único hueco real del patrón
contenedor-vs-ítem que ya existe (hallazgo 4).** La lectura literal del ROADMAP ("toda tarjeta usa
el mismo patrón... sin distinción") no describe el código real: los "ítems de lista" (cuentas,
presupuestos, categorías, `BudgetRing`, `SummaryCard`) ya están sin sombra, y los "contenedores"
(wrappers de listado, paneles de filtro, gráficos) ya la tienen (`shadow-sm`). El trabajo real de
este ítem es: (a) cerrar el único contenedor que se quedó sin `shadow-sm` por ser nuevo de Fase 11
(`CategoryBreakdownBars.tsx:33`), y (b) dar una elevación **mayor** (no solo `shadow-sm`, que ya es
"nivel contenedor") a las 1-2 tarjetas que de verdad son la pieza jerárquicamente más importante de
su pantalla — la card "Balance del mes" del dashboard y las cards "Balance Total" de `accounts/`.

**Decisión 12.2.2 — extender `SummaryCard` con una prop `elevated?: boolean`, independiente de
`size`.** `SummaryCard` ya tiene `size?: 'md' | 'lg'` (Fase 11, `components/ui/SummaryCard.tsx:11`),
usada hoy solo por la card "Balance del mes" (`app/(dashboard)/page.tsx:147`). Las cards "Balance
Total" de `accounts/page.tsx:201-208` deben elevarse **sin** crecer de tamaño (siguen siendo
`size="md"`, conviven en una grilla con varias monedas) — de ahí que `elevated` sea un prop nuevo y
no una inferencia de `size === 'lg'`.

```tsx
// components/ui/SummaryCard.tsx — diff
interface SummaryCardProps {
  label: string;
  value?: string;
  children?: ReactNode;
  trend?: 'up' | 'down';
  color?: string;
  size?: 'md' | 'lg';
  /** Eleva la card sobre sus pares para comunicar jerarquía (Fase 12 §12.2). Default false. */
  elevated?: boolean;
}

export default function SummaryCard({
  label, value, children, trend, color, size = 'md', elevated = false,
}: SummaryCardProps) {
  ...
  return (
    <div
      className={`border-border bg-surface rounded-2xl border transition-transform duration-200 hover:scale-[1.02] active:scale-100 max-sm:hover:scale-100 sm:hover:scale-[1.02] ${
        color ? 'border-l-4' : ''
      } ${isLarge ? 'p-5 sm:p-7' : 'p-4'} ${elevated ? 'shadow-sm' : ''}`}
      ...
```

(El tinte de esa `shadow-sm` se aplica en §12.3, en la misma pasada — ver Decisión 12.3.2.)

**Archivos a modificar:**
- `frontend/components/ui/SummaryCard.tsx` — prop `elevated` (arriba).
- `frontend/app/(dashboard)/page.tsx:147` — `<SummaryCard label="Balance del mes" size="lg"
  elevated ...>`.
- `frontend/app/(dashboard)/accounts/page.tsx:201,207` — ambos `<SummaryCard label="Balance
  Total">` (el de la lista y el del estado vacío) reciben `elevated`.
- `frontend/components/charts/CategoryBreakdownBars.tsx:33` — agregar `shadow-sm` al contenedor,
  igualándolo al resto de wrappers de lista (hallazgo 4).

**Decisión 12.2.3 — las tarjetas de ítem repetido (cuentas, presupuestos, categorías,
`BudgetRing`) se quedan sin sombra, a propósito.** Son N elementos iguales en una grilla; agregar
sombra a cada una competiría entre sí en vez de comunicar jerarquía (el objetivo explícito del
ROADMAP: "elevación solo donde comunica jerarquía"). El `hover:border-primary/30` + `active:scale`
que ya tienen (Fase 9) sigue siendo la señal de interactividad correcta para ítems de lista. Se
documenta para que nadie, leyendo el ROADMAP de forma literal, agregue sombra ahí por error.

**Testing:** manual. Confirmar que "Balance del mes" y "Balance Total" se perciben visualmente por
encima de sus vecinas (Ingresos/Gastos del mes; tarjetas de cuenta individuales) sin que ninguna
tarjeta de listado (cuentas, presupuestos, categorías, `BudgetRing`) haya ganado sombra.

**Criterio de aceptación:**
- `SummaryCard` acepta `elevated` sin romper ningún consumidor existente que no lo pase (default
  `false`, mismo aspecto que hoy).
- Las cards "Balance del mes" y "Balance Total" tienen una elevación visible que sus pares no
  tienen.
- Ninguna tarjeta de ítem repetido (cuenta, presupuesto, categoría, `BudgetRing`) cambia de estilo.

---

## 12.3 Tintar las sombras restantes con el color de fondo/acento

### Frontend

**Decisión 12.3.1 — tinte único y reutilizable: `shadow-background/NN` para sombras neutras,
sin tocar las que ya tiñen con `primary`.** El ROADMAP pide extender el criterio de
`shadow-primary/10` (Sidebar) y `shadow-primary/20`/`/30` (FAB, hallazgo 5) al resto — pero esos dos
casos son elementos con `bg-primary` (acento), no aplica igual a modales/popovers/tooltips neutros.
Para esos, se usa el token de fondo ya existente (`--color-background`, `app/globals.css:6/60`) vía
la utilidad de sombra coloreada de Tailwind v4 (`shadow-{color}/{opacity}`), mismo mecanismo que ya
usa el proyecto, aplicado a un color distinto. **Limitación documentada (hallazgo 6):** en tema
claro el efecto es casi imperceptible (`background` es casi blanco) — se acepta porque el problema
original tampoco es visible en tema claro; no se over-diseña una solución específica por tema para
un efecto puramente cosmético.

**Decisión 12.3.2 — aplicar en la misma pasada que §12.2, porque hay solape de archivos.**
`SummaryCard.tsx` y `CategoryBreakdownBars.tsx` reciben su `shadow-sm` nuevo en §12.2; tiñen ese
mismo `shadow-sm` aquí en vez de en dos commits separados.

**Ubicaciones concretas a tintar** (verificadas por archivo:línea, hallazgo 4/5):

| Archivo:línea | Clase actual | Clase nueva |
|---|---|---|
| `components/ui/ModalShell.tsx:21` | `shadow-2xl` | `shadow-2xl shadow-background/40` |
| `components/ui/ConfirmDialog.tsx:16` | `shadow-2xl` | `shadow-2xl shadow-background/40` |
| `components/FloatingActionButton.tsx:18` (panel) | `shadow-2xl` | `shadow-2xl shadow-background/40` |
| `components/ChartControlsPopover.tsx:39` | `shadow-xl` | `shadow-xl shadow-background/40` |
| `components/Sidebar.tsx:108` (tooltip) | `shadow-xl` | `shadow-xl shadow-background/40` |
| `components/CategoryDonutChart.tsx:218` (tooltip) | `shadow-lg` | `shadow-lg shadow-background/30` |
| `app/(dashboard)/layout.tsx:41` (hamburguesa móvil) | `shadow-md` | `shadow-md shadow-background/30` |
| 6 paneles de auth (`login`, `register`, `forgot-password`×2, `reset-password`×3, `verify-email`, `capture/page.tsx`) | `shadow-2xl` | `shadow-2xl shadow-background/40` |
| `transactions/page.tsx:264,362`, `page.tsx:285` (dashboard), `accounts/[id]/page.tsx:193`, `categories/[id]/page.tsx:184`, `CashflowChart.tsx:80`, `CategoryDonutChart.tsx:114` | `shadow-sm` | `shadow-sm shadow-background/20` |
| `SummaryCard.tsx` (nuevo, §12.2), `CategoryBreakdownBars.tsx` (nuevo, §12.2) | `shadow-sm` (agregado en §12.2) | `shadow-sm shadow-background/20` directamente al agregarlo |

**Sin cambios (ya tiñen correctamente):** `Sidebar.tsx:88` (`shadow-primary/10`),
`FloatingActionButton.tsx:28` (`shadow-primary/20 hover:shadow-primary/30`, corrección del hallazgo
5 respecto al valor que cita el ROADMAP).

**Testing:** manual, en ambos temas (claro/oscuro — el `ThemeToggle` ya existe). Confirmar que en
tema oscuro las sombras de modales/popovers se perciben mejor que el negro por defecto; confirmar
que en tema claro no hay ninguna regresión visible (el cambio debe ser neutro ahí, no negativo).

**Criterio de aceptación:**
- Ninguna sombra del proyecto usa el negro por defecto de Tailwind sin tinte, salvo que se
  documente por qué (no debería quedar ninguna tras este ítem).
- Los dos ejemplos ya correctos (`Sidebar`, FAB) no cambian.

---

## 12.4 Unificar estados de carga

### Frontend

**Decisión 12.4.1 — reemplazar el *early-return* `Loader2` centrado por un `<Skeleton>` con la
forma del contenido final, en los 7 archivos confirmados (hallazgo 7), no solo los 4 que nombra el
ROADMAP.**

**Diff de referencia — `transactions/page.tsx:240-246`:**

```tsx
// Antes
if (loadingInitial) {
  return (
    <div className="text-text-muted flex items-center gap-2 p-8">
      <Loader2 className="animate-spin" /> Cargando movimientos...
    </div>
  );
}

// Después
if (loadingInitial) {
  return (
    <div className="space-y-6">
      <Skeleton className="h-10 w-64 rounded-xl" />
      <Skeleton className="h-40 rounded-2xl" />
      <Skeleton className="h-96 rounded-3xl" />
    </div>
  );
}
```

(Tres bloques porque la página real tiene: encabezado, panel de filtros, tabla — mismo criterio que
`dashboard/page.tsx:144-145,191-195` ya usa: un `<Skeleton>` por bloque estructural, no un único
rectángulo genérico.)

**Diff de referencia — `budgets/page.tsx` (~línea 126) y `categories/page.tsx` (~línea 126),
mismo patrón, adaptado a su propia grilla:**

```tsx
if (loadingBudgets) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-32 rounded-2xl" />
      ))}
    </div>
  );
}
```

Mismo patrón para `accounts/page.tsx:173-176` (reemplaza el early-return del listado principal —
**no** el bloque `loadingBalances` de la línea 198, que ya usa `Skeleton` desde Fase 11 y no se
toca), `accounts/[id]/page.tsx:155-158` y `categories/[id]/page.tsx:153-157` (forma de detalle:
encabezado + historial), y `analytics/page.tsx:163-169` (dos bloques lado a lado, mismo grid que el
contenido real).

**Decisión 12.4.2 — `verify-email/page.tsx` y el `Loader2` interno de `Button.tsx` quedan fuera de
alcance, a propósito (hallazgo 7).** `verify-email` resuelve una request única al montar sin
contenido de lista que anticipar (un spinner centrado sigue siendo la señal correcta para "estoy
verificando tu enlace", no hay "forma" que un Skeleton pueda anticipar). El `Loader2` de
`Button.tsx:48` es el spinner de un botón en envío, un caso completamente distinto (acción puntual,
no carga de página) que ningún otro ítem de esta fase toca.

**Archivos a modificar:** `transactions/page.tsx`, `budgets/page.tsx`, `categories/page.tsx`,
`accounts/page.tsx` (solo el early-return principal), `accounts/[id]/page.tsx`,
`categories/[id]/page.tsx`, `analytics/page.tsx`. Ningún archivo requiere importar nada nuevo —
`Skeleton` ya existe (`components/ui/Skeleton.tsx`) y ya se importa en 3 de los 7.

**Testing:** manual. Confirmar que el alto aproximado de cada `Skeleton` no genera un salto de
layout perceptible cuando el contenido real reemplaza el placeholder; confirmar que no queda ningún
`Loader2` usado como *early-return* de página completa en los 7 archivos (sí puede seguir existiendo
dentro de un `Button` o de `verify-email`, por Decisión 12.4.2).

**Criterio de aceptación:**
- Los 7 archivos usan `Skeleton` con forma reconocible del contenido en vez de un spinner centrado
  genérico.
- `verify-email/page.tsx` y `Button.tsx` no cambian.

---

## 12.5 Favicon de marca + limpieza de assets de scaffold

### Frontend

**Decisión 12.5.1 — reemplazar el binario, no generar un nuevo componente ni tocar
`metadata`.** Next.js App Router detecta automáticamente `app/favicon.ico` sin necesidad de
declararlo en `metadata.icons` (`app/layout.tsx:15-18` no lo declara hoy y funciona igual, solo con
el ícono default) — no hace falta ningún cambio de código en `layout.tsx`, solo reemplazar el
archivo binario. La generación del ícono en sí (a partir del glifo `Wallet` de `lucide-react` que ya
usan las cabeceras de `login`/`register`/`forgot-password`, u otro diseño de marca) es un artefacto
de diseño, no de código — queda fuera de lo que este documento puede especificar en texto; se
documenta el requisito para quien lo produzca.

**Archivos a modificar:**
- `frontend/app/favicon.ico` — reemplazar el binario (confirmado hoy: ícono default de Next.js,
  25.9 KB, hallazgo 8).
- Eliminar `frontend/public/next.svg`, `vercel.svg`, `globe.svg`, `file.svg`, `window.svg`
  (confirmado sin referencias, hallazgo 8).

**Testing:** manual — verificar en la pestaña del navegador que el ícono cambió; `pnpm build` sigue
limpio tras borrar los 5 SVG (no debería fallar, ya que ninguno se importa).

**Criterio de aceptación:**
- El favicon ya no es el default de Next.js.
- `public/` no contiene ningún asset de scaffold sin usar.

---

## 12.6 Página 404 propia

### Frontend

**Decisión 12.6.1 — `app/not-found.tsx` a nivel raíz, con el mismo lenguaje visual ya usado 8+
veces en el proyecto (tarjeta centrada `bg-surface border-border/70 rounded-3xl border shadow-2xl`),
no un patrón nuevo.** Consistente con `frontend/docs/UI_SYSTEM.md` ("si una pantalla necesita un
nuevo patrón visual, documentarlo aquí antes de replicarlo") — aquí no hace falta ningún patrón
nuevo, se reutiliza el que ya usan `login`, `register`, `forgot-password`, `reset-password`,
`verify-email` y `capture/page.tsx`.

**Nota de alcance, explícita:** un `app/not-found.tsx` a nivel raíz renderiza dentro del layout raíz
(`app/layout.tsx`), **no** dentro de `(dashboard)/layout.tsx` — un usuario autenticado que navega a
una URL inexistente dentro del dashboard (ej. `/accounts/xyz` mal escrito) verá esta página sin el
sidebar, no una versión "dentro del shell". Un 404 anidado que preserve el sidebar
(`app/(dashboard)/not-found.tsx`) es una mejora razonable pero **no es lo que pide el ROADMAP**
("`app/not-found.tsx`" a secas) — se deja fuera de alcance a propósito, mismo criterio que
Decisión 10.1.4/11.7.1 de fases anteriores (no comprometerse con alcance no pedido); si en el uso
real resulta molesto, es una tarea de una hora para una fase futura.

**Archivo a crear:** `frontend/app/not-found.tsx`.

```tsx
import Link from 'next/link';
import { Compass } from 'lucide-react';
import Button from '@/components/ui/Button';

export default function NotFound() {
  return (
    <div className="bg-background flex min-h-screen items-center justify-center p-4">
      <div className="bg-surface border-border/70 w-full max-w-md rounded-3xl border p-8 text-center shadow-2xl shadow-background/40">
        <div className="bg-primary/10 text-primary mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full">
          <Compass size={24} />
        </div>
        <h1 className="text-text font-sans text-2xl font-bold tracking-tight">
          Página no encontrada
        </h1>
        <p className="text-text-muted mt-2 text-sm">
          La página que buscas no existe o cambió de dirección.
        </p>
        <Link href="/" className="mt-6 block">
          <Button type="button" variant="primary" size="lg" className="w-full">
            Volver al dashboard
          </Button>
        </Link>
      </div>
    </div>
  );
}
```

(Un usuario no autenticado que llegue aquí y pulse "Volver al dashboard" es redirigido a `/login`
por `useRequireAuth` al montar `(dashboard)/layout.tsx` — no hace falta lógica de auth propia en
esta página.)

**Testing:** manual — navegar a una ruta inexistente (`/no-existe`) muestra esta página; el botón
navega correctamente en ambos casos (con y sin sesión activa).

**Criterio de aceptación:**
- Cualquier ruta no definida muestra esta página en vez del 404 genérico de Next.js.
- Visualmente coherente con el resto de pantallas de estado (auth, capture).

---

## 12.7 Skip-link para navegación por teclado

### Frontend

**Decisión 12.7.1 — solo en el shell autenticado (hallazgo 10), con `id="main-content"` en el
`<main>` ya existente.**

**Archivo a modificar:** `frontend/app/(dashboard)/layout.tsx`.

```tsx
return (
  <div className="bg-background min-h-screen">
    <a
      href="#main-content"
      className="bg-primary text-background focus-visible:ring-primary/50 sr-only rounded-lg px-4 py-2 text-sm font-medium focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus-visible:ring-2 focus-visible:outline-none"
    >
      Saltar al contenido principal
    </a>
    <Sidebar />
    <ConfirmDialog />
    <FabManager />

    <div className={...}>
      <button ...>{/* hamburguesa móvil, sin cambios */}</button>

      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto w-full max-w-[1600px] min-w-0 flex-1 overflow-x-hidden p-4 sm:p-8 lg:p-12"
      >
        {children}
      </main>
    </div>
  </div>
);
```

`tabIndex={-1}` en `<main>` es necesario para que el salto de foco funcione de forma consistente
entre navegadores al activar un ancla `href="#id"` hacia un elemento que normalmente no es
enfocable (`<main>` no lo es por defecto).

**Testing:** manual con teclado — al cargar `/` (o cualquier ruta del dashboard) y presionar `Tab`
una vez, el primer elemento enfocado debe ser el skip-link (visible solo entonces); `Enter` mueve el
foco a `<main>`, saltando los ~9 elementos enfocables del sidebar.

**Criterio de aceptación:**
- El skip-link es el primer elemento enfocable del shell autenticado.
- Es invisible hasta recibir foco de teclado.
- Activarlo mueve el foco a `<main>`.
- `(auth)` y `/capture` no cambian (no tienen nada que saltar, hallazgo 10).

---

## 12.8 Validación de formularios por campo, con foco en el primer error

### Frontend

**Decisión 12.8.1 — conectar el prop `error` que `Input`/`Select` ya tienen (hallazgo 11), no
construir un motor de validación ni adoptar una librería nueva (`react-hook-form`, `zod`).** El
alcance que dimensiona el ROADMAP (1 día) y el principio de "no sobre-diseñar" del proyecto excluyen
una reescritura de 9 formularios sobre una dependencia nueva para un problema que se resuelve con lo
que ya existe: cada formulario mantiene un `useState<Record<string, string>>({})` de errores,
calculado en el momento del submit (no on-change — evita penalizar mientras el usuario escribe, y
evita el trabajo adicional de debouncing), y hace foco vía `ref` en el primer campo con error —
mismo mecanismo que Fase 10 ya introdujo en `TransactionCaptureForm.tsx:100-121`, aplicado ahora
por campo en vez de por `toast` genérico.

**Decisión 12.8.2 — usar `noValidate` en los `<form>` que reciben esta validación, para tomar
control total del estilo del error (hallazgo 12).** Sin `noValidate`, el navegador sigue mostrando
su propio globo de validación nativo para `required`/`minLength`/`type="email"` **antes** de que
corra el `onSubmit` de React — inconsistente entre navegadores y ajeno a la paleta oscura fintech
del proyecto. Con `noValidate`, el formulario debe reimplementar en JS las mismas reglas que el
navegador cubría (`campo vacío`, `longitud mínima`, `formato de email` — este último vía una regex
simple, no una librería) — es el motivo principal del ajuste de horas de este ítem (ver tabla en
"Orden de ejecución recomendado").

**Diff de referencia — `register/page.tsx` (Grupo 1, formularios de auth):**

```tsx
// Antes (líneas 13-35): solo un `error: string | null` global
const [error, setError] = useState<string | null>(null);
...
if (password !== confirmPassword) {
  setError('Las contraseñas no coinciden.');
  setIsLoading(false);
  return;
}
if (password.length < 10) {
  setError('La contraseña debe tener al menos 10 caracteres.');
  setIsLoading(false);
  return;
}

// Después
const [fieldErrors, setFieldErrors] = useState<{
  fullName?: string; email?: string; password?: string; confirmPassword?: string;
}>({});
const fullNameRef = useRef<HTMLInputElement>(null);
const emailRef = useRef<HTMLInputElement>(null);
const passwordRef = useRef<HTMLInputElement>(null);
const confirmRef = useRef<HTMLInputElement>(null);

const handleRegister = async (e: React.FormEvent) => {
  e.preventDefault();
  setError(null);

  const errors: typeof fieldErrors = {};
  if (!fullName.trim()) errors.fullName = 'Ingresa tu nombre completo.';
  if (!/^\S+@\S+\.\S+$/.test(email)) errors.email = 'Ingresa un correo válido.';
  if (password.length < 10) errors.password = 'Debe tener al menos 10 caracteres.';
  if (password !== confirmPassword) errors.confirmPassword = 'Las contraseñas no coinciden.';
  setFieldErrors(errors);

  if (errors.fullName) return fullNameRef.current?.focus();
  if (errors.email) return emailRef.current?.focus();
  if (errors.password) return passwordRef.current?.focus();
  if (errors.confirmPassword) return confirmRef.current?.focus();

  setIsLoading(true);
  try {
    await api.post('users/', { full_name: fullName, email, password });
    router.push('/login?registered=true');
  } catch (err: unknown) {
    // Errores de servidor (email ya registrado, etc.) se quedan en el banner genérico —
    // no pertenecen inequívocamente a un campo específico.
    ...
  } finally {
    setIsLoading(false);
  }
};
```

```tsx
<form onSubmit={handleRegister} className="space-y-4" noValidate>
  <Input ref={fullNameRef} label="Nombre Completo" error={fieldErrors.fullName} ... />
  <Input ref={emailRef} label="Correo Electrónico" error={fieldErrors.email} ... />
  <Input ref={passwordRef} label="Contraseña" error={fieldErrors.password} ... />
  <Input ref={confirmRef} label="Confirmar Contraseña" error={fieldErrors.confirmPassword} ... />
  ...
</form>
```

Mismo patrón, con sus propios campos, para `login/page.tsx` (email/password vacíos),
`forgot-password/page.tsx` (email), `reset-password/page.tsx` (password/confirmPassword — ya tiene
la comparación manual en `formError`, líneas 97-99, se migra a `fieldErrors.confirmPassword`). El
banner genérico (`role="status" aria-live="polite"`, Fase 9 §9.9) **no se elimina** — sigue
mostrando los errores de servidor, que no son atribuibles a un campo específico por diseño de
seguridad (ej. "credenciales inválidas" no distingue email de password).

**Diff de referencia — `budgets/page.tsx` (Grupo 2, modales CRUD, hallazgo 12):**

```tsx
const [fieldErrors, setFieldErrors] = useState<{ categoryId?: string; amount?: string }>({});
const categoryRef = useRef<HTMLSelectElement>(null);
const amountRef = useRef<HTMLInputElement>(null);

const handleSubmit = (e: React.FormEvent) => {
  e.preventDefault();
  const [yearStr, monthStr] = monthYear.split('-');

  const errors: typeof fieldErrors = {};
  if (!categoryId) errors.categoryId = 'Elige una categoría.';
  const parsedAmount = Number(amount);
  if (!amount || Number.isNaN(parsedAmount) || parsedAmount <= 0) {
    errors.amount = 'Ingresa un monto mayor a cero.';
  }
  setFieldErrors(errors);
  if (errors.categoryId) return categoryRef.current?.focus();
  if (errors.amount) return amountRef.current?.focus();

  saveMutation.mutate({
    category_id: Number(categoryId),
    amount_limit: parsedAmount,
    month: Number(monthStr),
    year: Number(yearStr),
    is_recurring: isRecurring,
  });
};
```

Mismo patrón, adaptado a sus propios campos, para `accounts/page.tsx` (nombre de cuenta vacío,
`initialBalance` negativo) y `categories/page.tsx` (nombre vacío) — en ambos casos el código de
creación/edición ya está oculto detrás de `CUSTOM_CATEGORY_EDITING_ENABLED = false` para categorías
(Fase 11 §11.6); la validación se agrega igual, para cuando el flag vuelva a `true`.

**Diff de referencia — `TransactionCaptureForm.tsx` (Grupo 3):**

Reemplaza el `toast.error` genérico de `handleSubmit` (líneas 100-121) por `fieldErrors` +
`error={fieldErrors.amount}` en el `<Input>` de monto (línea 166) y un mensaje bajo el `<fieldset>`
de categorías (línea 196-221, no puede usar el prop `error` de `Input`/`Select` porque no es ninguno
de los dos — se agrega un `<p className="text-danger text-xs mt-2">{fieldErrors.category}</p>`,
mismo estilo visual que ya usan `Input`/`Select` para sus errores, por consistencia).

**Decisión 12.8.3 — migrar el modal de edición de `transactions/page.tsx` a `Input`/`Select`
como parte de este ítem (hallazgo 13), cerrando la deuda que el propio `docs/ROADMAP.md` ya tenía
pendiente.** Las líneas 502-577 (5 controles crudos) se reemplazan por `<Input>`/`<Select>` con
`error` — mismo patrón de validación que el resto de este ítem (`categoryId`/`accountId` vacíos,
`amount <= 0`). Esto resuelve en la misma pasada la entrada de "Pendientes heredados de fases
anteriores" del ROADMAP sobre este modal específico.

**Archivos a modificar:** `app/(auth)/login/page.tsx`, `app/(auth)/register/page.tsx`,
`app/(auth)/forgot-password/page.tsx`, `app/(auth)/reset-password/page.tsx`,
`components/forms/TransactionCaptureForm.tsx`, `app/(dashboard)/accounts/page.tsx`,
`app/(dashboard)/categories/page.tsx`, `app/(dashboard)/budgets/page.tsx`,
`app/(dashboard)/transactions/page.tsx` (modal de edición, migrado a `Input`/`Select`).

**Testing:** manual (sin suite de frontend). Por cada formulario: enviar con un campo inválido debe
mostrar el borde/mensaje `danger` bajo ese campo específico y mover el foco ahí; enviar con todos los
campos válidos debe proceder a la mutación sin mostrar ningún error; los errores de servidor (auth) y
de mutación (`toast`, CRUD) deben seguir funcionando exactamente igual que hoy.

**Criterio de aceptación:**
- Ningún formulario del listado depende únicamente del globo de validación nativo del navegador.
- El primer campo inválido recibe foco visible y un mensaje de error propio del sistema de diseño.
- El modal de edición de `transactions/page.tsx` usa `Input`/`Select` compartidos, no markup crudo.
- `docs/ROADMAP.md`, "Pendientes heredados de fases anteriores": marcar como resuelta la entrada
  sobre el modal de edición de transacciones.

---

## 12.9 `tabular-nums` en cifras

### Frontend

**Decisión 12.9.1 — aplicar la utilidad nativa de Tailwind (`tabular-nums`, sin configuración
adicional) a los montos que aparecen en columnas o cambian dinámicamente, no a cualquier texto con
un número.** Sitios concretos (hallazgo 14 — cero uso previo):

- `components/ui/SummaryCard.tsx:37,44-50` (el monto principal).
- `components/charts/BudgetRing.tsx:58-60` (porcentaje) y `:97-106` (spent/budget).
- `components/charts/CategoryBreakdownBars.tsx:65-67`.
- Columnas de listas: `app/(dashboard)/transactions/page.tsx:406-411`,
  `app/(dashboard)/page.tsx:322-327` (transacciones recientes), `app/(dashboard)/accounts/page.tsx:
  238`, `app/(dashboard)/accounts/[id]/page.tsx:186,233`,
  `app/(dashboard)/categories/[id]/page.tsx:218`, `app/(dashboard)/budgets/page.tsx:212`.

**Fuera de alcance, documentado:** los `tickFormatter`/tooltips de Recharts
(`CashflowChart.tsx`, `CategoryDonutChart.tsx`) renderizan texto dentro de SVG generado por la
librería — aplicar una clase Tailwind ahí requiere pasar `className` a través de las props internas
de Recharts, un trabajo desproporcionado para las 2h asignadas a este ítem. Se documenta como no
cubierto en vez de forzarlo.

**Archivos a modificar:** los 9 listados arriba — cada edición es agregar `tabular-nums` a la
clase existente del elemento que renderiza el monto, sin ningún otro cambio.

**Testing:** manual — comparar una lista con montos de distinto número de dígitos (ej.
`transactions/page.tsx`, mezclando montos de 4 y 7 cifras) antes/después; los dígitos deben alinearse
en ancho fijo.

**Criterio de aceptación:**
- Los 9 sitios listados usan `tabular-nums`.
- Ningún gráfico de Recharts cambia (fuera de alcance, documentado).

---

## 12.10 Enlaces legales (privacidad/términos) en el shell autenticado

### Frontend

**Decisión 12.10.1 — footer mínimo dentro de `Sidebar.tsx`, no un `<footer>` nuevo en el
layout.** `(dashboard)/layout.tsx` no tiene hoy ningún `<footer>` (hallazgo 15); agregar uno nuevo
que conviva con `<main>` competiría por espacio en pantallas de poca altura. El bloque de
perfil/logout que ya existe al final de `Sidebar.tsx` (líneas 168-218) es la zona "de servicio" del
shell — es donde ya vive lo que no es navegación primaria (tema, logout). Los enlaces se ocultan
cuando el sidebar está colapsado (mismo criterio que el resto de ese bloque, que también oculta
texto colapsado) — no llevan tooltip propio, a diferencia de los ítems de navegación, porque no son
wayfinding primario.

**Decisión 12.10.2 — dos páginas públicas nuevas, fuera de `(auth)` y `(dashboard)`.** No
requieren sesión (deben poder visitarse sin login, como cualquier página legal real) ni el patrón de
tarjeta centrada de `(auth)` (pensado para formularios cortos, no para texto largo de lectura). Un
layout propio, minimal, sin sidebar:

```tsx
// frontend/app/legal/layout.tsx
export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-background min-h-screen">
      <div className="mx-auto max-w-2xl px-4 py-12 sm:px-6">{children}</div>
    </div>
  );
}
```

`frontend/app/legal/privacidad/page.tsx` y `frontend/app/legal/terminos/page.tsx`: contenido
placeholder estructurado (secciones: qué datos se recogen, para qué se usan, contacto) — la
redacción legal real (revisión de cumplimiento) queda fuera del alcance de este documento de
arquitectura, igual que el propio ROADMAP no pide una revisión legal formal, solo que el enlace
exista y no sea un 404.

**Archivo a modificar:** `components/Sidebar.tsx` — agregar, dentro del bloque de perfil (línea
168 en adelante), dos `<Link>` pequeños a `/legal/privacidad` y `/legal/terminos`, ocultos cuando
`!isSidebarOpen`.

**Archivos a crear:** `frontend/app/legal/layout.tsx`, `frontend/app/legal/privacidad/page.tsx`,
`frontend/app/legal/terminos/page.tsx`.

**Testing:** manual — los enlaces navegan desde el sidebar expandido; las páginas cargan sin
requerir sesión activa (probar en una pestaña sin `jwt_token` en `localStorage` — deben renderizar
igual, a diferencia de cualquier ruta bajo `(dashboard)`, que redirige a `/login` vía
`useRequireAuth`).

**Criterio de aceptación:**
- `/legal/privacidad` y `/legal/terminos` existen y son accesibles sin sesión.
- El sidebar enlaza a ambas cuando está expandido.
- Ninguna ruta de `(dashboard)` ni su guard de auth se ve afectada.

---

## Fuera de alcance de este documento

**Reemplazo de Lucide por otra librería de iconos** (ítem opcional del ROADMAP): el propio ROADMAP
lo marca "opcional, no bloqueante" y estima un cambio de ~20 archivos por un beneficio
"principalmente estético". Este documento no le dedica una sección numerada por la misma razón que
el ROADMAP lo deja en backlog — no hay ningún hallazgo de código que cambie esa evaluación.

---

## Resumen de archivos tocados por ítem

| Ítem | Archivos |
|---|---|
| 12.1 URL-sync | `hooks/useQueryParamState.ts` (nuevo), `app/(dashboard)/transactions/page.tsx`, `app/(dashboard)/analytics/page.tsx`, `docs/STATE_AND_FETCHING.md` |
| 12.2 Diferenciar tarjetas | `components/ui/SummaryCard.tsx`, `app/(dashboard)/page.tsx`, `app/(dashboard)/accounts/page.tsx`, `components/charts/CategoryBreakdownBars.tsx` |
| 12.3 Tintar sombras | `components/ui/ModalShell.tsx`, `components/ui/ConfirmDialog.tsx`, `components/FloatingActionButton.tsx`, `components/ChartControlsPopover.tsx`, `components/Sidebar.tsx` (tooltip), `components/CategoryDonutChart.tsx`, `app/(dashboard)/layout.tsx`, 6 páginas de `(auth)` + `capture/page.tsx`, `transactions/page.tsx`, `app/(dashboard)/page.tsx`, `accounts/[id]/page.tsx`, `categories/[id]/page.tsx`, `CashflowChart.tsx` |
| 12.4 Unificar loading | `transactions/page.tsx`, `budgets/page.tsx`, `categories/page.tsx`, `accounts/page.tsx`, `accounts/[id]/page.tsx`, `categories/[id]/page.tsx`, `analytics/page.tsx` |
| 12.5 Favicon | `app/favicon.ico`, `public/*.svg` (borrar 5) |
| 12.6 Página 404 | `app/not-found.tsx` (nuevo) |
| 12.7 Skip-link | `app/(dashboard)/layout.tsx` |
| 12.8 Validación por campo | `app/(auth)/login/page.tsx`, `app/(auth)/register/page.tsx`, `app/(auth)/forgot-password/page.tsx`, `app/(auth)/reset-password/page.tsx`, `components/forms/TransactionCaptureForm.tsx`, `app/(dashboard)/accounts/page.tsx`, `app/(dashboard)/categories/page.tsx`, `app/(dashboard)/budgets/page.tsx`, `app/(dashboard)/transactions/page.tsx` (modal de edición) |
| 12.9 `tabular-nums` | `SummaryCard.tsx`, `BudgetRing.tsx`, `CategoryBreakdownBars.tsx`, `transactions/page.tsx`, `app/(dashboard)/page.tsx`, `accounts/page.tsx`, `accounts/[id]/page.tsx`, `categories/[id]/page.tsx`, `budgets/page.tsx` |
| 12.10 Enlaces legales | `components/Sidebar.tsx`, `app/legal/layout.tsx` (nuevo), `app/legal/privacidad/page.tsx` (nuevo), `app/legal/terminos/page.tsx` (nuevo) |
| Cruzando toda la fase | Ninguno de los 10 ítems toca `backend/` — confirmado en cada sección; no aplica la regla de `CLAUDE.md` sobre actualizar `API_REFERENCE.md`/`API_CONTRACT.md` en la misma pasada porque ningún contrato de API cambia |

---

## Cierre

Este documento no implementa ningún cambio en el repositorio — es el desglose ejecutable de la
sección "Fase 12" de `docs/ROADMAP.md`, con archivos, líneas y decisiones de diseño concretas para
que un frontend-engineer pueda partir directamente de aquí sin tener que re-explorar el código para
tomar las mismas decisiones. Todos los hallazgos de este documento (el estado real, más irregular de
lo que sugiere la lectura literal del ROADMAP, del patrón de sombras y tarjetas; el inventario
correcto de páginas con `Loader2` de página completa; la ausencia confirmada de `not-found.tsx`,
skip-link, `tabular-nums` y enlaces legales; y, sobre todo, que `Input`/`Select` ya exponen un prop
`error` sin ningún consumidor) fueron verificados contra el código real de `frontend/` el
2026-09-05, no inferidos del texto del ROADMAP. Ningún archivo del repositorio fuera de
`docs/specs/fase_12_spec.md` fue modificado al producir este documento.
