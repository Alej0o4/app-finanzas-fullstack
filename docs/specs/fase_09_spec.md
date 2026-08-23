# Spec — Fase 9: Accesibilidad y componentes base de UI

> Plan de implementación detallado para los 10 items de Fase 9 del [ROADMAP](../ROADMAP.md).
> Fuente de verdad de alcance: `docs/ROADMAP.md` (sección "Fase 9 — Accesibilidad y
> componentes base de UI", líneas ~162-205), a su vez basada en la auditoría de diseño del
> 2026-08-23 (Web Interface Guidelines + skill `redesign-existing-projects`). Este documento no
> cambia el alcance ahí definido — lo desglosa en tareas ejecutables, con archivos concretos,
> pasos, dependencias y decisiones de diseño.
>
> **No implementa nada.** Es el hand-off para quien vaya a codear (frontend-engineer). A
> diferencia de `docs/specs/fase_07_spec.md` y `docs/specs/fase_08_spec.md`, Fase 9 es
> **puramente frontend** — no hay ningún endpoint, modelo ni migración involucrados. La sección
> "Tareas de Backend" se deja explícita más abajo, vacía, por consistencia estructural con el
> resto de specs de fase.

Estado del repo en el momento de escribir esto (2026-08-23): Fase 8 está mergeada a `main`
(commit `521ea1e`) — modelo de datos del nuevo MVP completo (`monthly_income`, `payment_method`,
presupuestos recurrentes, categorías ampliadas, cuenta por defecto al registrarse, `updated_at`
+ borrado lógico). Fase 9 no depende de nada de Fase 8 en términos de datos — es un bloqueador
puramente de UI para las Fases 10 (captura en 3 toques) y 11 (dashboard de flujo mensual), que
van a construir pantallas nuevas apoyadas en `Button`, `Input`, `Select` y `ModalShell`. El
objetivo de este documento es que esas dos fases hereden componentes base ya corregidos, no que
descubran los mismos bugs de foco/label/animación al construir la UI nueva.

---

## Hallazgos de exploración que corrigen/precisan el ROADMAP

El ROADMAP describe los 10 hallazgos de la auditoría en una frase cada uno. Verificado contra
el código real (`frontend/`), con matices que conviene dejar explícitos antes de implementar:

1. **`tailwindcss-animate` efectivamente no está instalado — confirmado, con una precisión
   importante sobre *cómo* arreglarlo.** `frontend/package.json` solo tiene `tailwindcss": "^4"`
   y `prettier-plugin-tailwindcss` — ningún plugin de animación. `frontend/app/globals.css` no
   tiene ningún `@keyframes` propio. Pero el proyecto está en **Tailwind v4**, que usa
   configuración CSS-first (`@theme` en `globals.css`, ya usado para los tokens de color) en vez
   de un `tailwind.config.js` con plugins JS. `tailwindcss-animate` es un plugin diseñado para
   Tailwind v3 (JS config) — instalarlo a ciegas en un proyecto v4 puede no engancharse
   correctamente o requerir el paquete equivalente v4 (`tw-animate-css`). La recomendación
   concreta (ítem 9.5 abajo) es **no instalar ningún plugin**: definir los `@keyframes` y las
   utilidades `animate-*` directamente en `globals.css` vía el mecanismo nativo de Tailwind v4
   (namespace `--animate-*` dentro de `@theme`), exactamente el mismo patrón CSS-first que ya
   usa este archivo para colores — consistente con la convención existente, sin dependencia
   nueva.

2. **La animación rota no es idéntica en `ModalShell` y `FloatingActionButton` — precisión
   menor.** `ModalShell.tsx:18` solo tiene `animate-in fade-in duration-200` (sin
   `slide-in-from-bottom-2`); `FloatingActionButton.tsx:18` sí tiene las tres clases
   (`animate-in fade-in slide-in-from-bottom-2 duration-200`). No cambia el diagnóstico (ambas
   igual de rotas, ninguna anima nada hoy), pero si se implementan keyframes distintos para
   "aparecer centrado" (modal) vs. "deslizar desde abajo" (menú del FAB), hace falta definir dos
   animaciones, no una.

3. **`ChartControlsPopover.tsx:32` es en efecto el único patrón correcto de `aria-label` en todo
   el proyecto — confirmado por grep exhaustivo, con un matiz: no es el único caso ya resuelto.**
   `app/(dashboard)/layout.tsx:48` (botón hamburguesa móvil, `<Menu>` de lucide-react) también
   tiene `aria-label="Abrir menú"` ya correcto. Son los únicos 2 `aria-label` de todo
   `frontend/` (`grep -rn "aria-label" --include="*.tsx"` devuelve exactamente estas dos
   líneas). Importa para el alcance del ítem 9.3: el botón hamburguesa de `layout.tsx` **no**
   necesita tocarse; el botón de colapsar/expandir del propio `Sidebar.tsx` (líneas 95-107,
   un botón distinto, para desktop) **sí** — no tiene ni `aria-label` ni `title`.

4. **La mayoría de los botones icon-only no están completamente sin etiqueta — tienen `title`,
   que no es equivalente a `aria-label`.** Confirmado con `grep -rn 'title="'`: los botones de
   editar/eliminar cuenta (`accounts/page.tsx:232,243`), editar/eliminar categoría
   (`categories/page.tsx:187,198`), destacar cuenta (`accounts/page.tsx:221`, `title` dinámico),
   tema (`ThemeToggle.tsx:100`, `title` dinámico) y logout (`Sidebar.tsx:180,198`) sí tienen
   `title`. `title` **es** técnicamente parte del cálculo de nombre accesible cuando no hay
   `aria-label`/`aria-labelledby`/texto visible (HTML-AAM, último recurso), así que estos casos
   no están 100% "mudos" para un lector de pantalla — pero `title` es un mecanismo poco fiable
   (soporte inconsistente entre lectores de pantalla, sin tooltip en touch, delay largo en
   desktop) y **no sustituye** a `aria-label` según las Web Interface Guidelines que motivaron la
   auditoría. El subconjunto sin **ninguna** etiqueta (ni `title` ni `aria-label`) es más grave y
   más largo de lo que sugiere el ROADMAP: editar/eliminar presupuesto
   (`budgets/page.tsx:185-202`), editar/eliminar transacción en las 3 vistas donde aparece
   (`transactions/page.tsx:419-436`, `accounts/[id]/page.tsx:235-250`,
   `categories/[id]/page.tsx:220-235`), el botón "volver" en las 2 vistas de detalle
   (`accounts/[id]/page.tsx:161-163`, `categories/[id]/page.tsx:161-163`), el cierre de
   `ModalShell` (línea 21-26) y el toggle del FAB (`FloatingActionButton.tsx:22-32`). Inventario
   completo con conteo en la sección 9.3.

5. **`ConfirmDialog.tsx` no está construido sobre `ModalShell.tsx` — son dos implementaciones de
   modal independientes.** El ROADMAP los agrupa en el mismo ítem ("Cierre por Escape +
   `overscroll-behavior: contain` en `ModalShell` y `ConfirmDialog`"), lo cual es correcto como
   alcance, pero conviene que quien implemente sepa que **no** alcanza con arreglar
   `ModalShell.tsx` y esperar que `ConfirmDialog.tsx` (que tiene su propio backdrop, su propio
   contenedor y ningún `useEffect` de teclado) herede el fix. Ver Decisión 9.4.1 sobre extraer
   un hook compartido en vez de duplicar la lógica de Escape en los dos archivos.

6. **`transition-all` aparece en más lugares de los que lista el ROADMAP.** El ROADMAP menciona
   `Sidebar`, `Button`, `FloatingActionButton`, `(dashboard)/layout.tsx` y "los formularios de
   edición manual" — todos confirmados. Pero el grep (`grep -rn "transition-all"`) encuentra
   además `components/charts/BudgetRing.tsx:75` y `components/ui/SummaryCard.tsx:15`, no
   mencionados explícitamente. Son 13 ocurrencias en 7 archivos en total (detalle en 9.6), no
   solo los 4 nombrados. No cambia la estimación (sigue siendo un find-and-replace mecánico) pero
   sí el inventario de archivos a tocar.

7. **`prefers-reduced-motion`, `overscroll-behavior` y `active:` están en cero, confirmado sin
   excepciones.** `grep -rn "prefers-reduced-motion\|overscroll\|active:"` sobre todo
   `frontend/` no devuelve ningún resultado. El hallazgo del ROADMAP es exacto, no hay ningún
   caso ya resuelto que excluir del alcance.

8. **Los 4 formularios de auth (`login`, `register`, `forgot-password`, `reset-password`) están
   confirmados sin `autocomplete` en ningún `<Input>` y sin `aria-live` en ningún bloque de
   error/éxito.** Un matiz sobre `forgot-password/page.tsx` y `reset-password/page.tsx`: el
   mensaje de éxito/error no siempre es un banner inline — en varios casos la página reemplaza
   **todo el formulario** por un panel distinto vía early return (`ForgotPasswordPage` líneas
   29-50 tras éxito; `InvalidLinkPanel` en `reset-password/page.tsx` líneas 28-58 tras token
   inválido). Esos casos no son "mensajes de error/éxito" en el sentido estricto del ítem 9.9
   (que apunta a los `<div>` de banner), pero un lector de pantalla tampoco los anuncia
   automáticamente al no haber cambio de ruta ni movimiento de foco — se deja anotado como mejora
   relacionada, fuera del alcance estricto de este ítem (ver 9.9 "Nota relacionada").

9. **Ni `Input.tsx` ni `Select.tsx` tienen ningún `id` generado, en ningún call site.**
   `grep -rn "id=\|htmlFor"` sobre ambos componentes no devuelve nada, y ningún consumidor de
   `<Input>`/`<Select>` en todo el proyecto pasa un `id` propio (`grep` sobre los call sites
   tampoco encuentra ninguno). Esto simplifica el ítem 9.2: no hay que preocuparse por colisión
   con IDs manuales existentes — se puede generar el `id` automáticamente con `useId()` (React
   `19.2.4`, confirmado en `package.json`, ya soporta el hook) sin ningún caso de borde.

---

## Orden de ejecución recomendado

La dependencia real entre tareas, no la importancia percibida (todas son 🟡 UX/accesibilidad,
ninguna es 🔴 bloqueador de producto — la urgencia real es "antes de que Fase 10/11 construyan
sobre estos componentes", no "hoy mismo"):

```
1. focus-visible en Button/Input/Select (9.1)         ── sin dependencias; toca los 3 archivos
                                                            base que todo lo demás usa; hacerla
                                                            primero evita retrabajo si otra tarea
                                                            también toca las mismas clases focus:
2. Label htmlFor/id en Input/Select (9.2)              ── mismo archivo que (1); agruparlas en el
                                                            mismo PR reduce el número de veces que
                                                            se tocan Input.tsx/Select.tsx
3. ModalShell + ConfirmDialog: Escape +
   overscroll-behavior (9.4)                            ── independiente de (1)/(2); recomendado
                                                            junto con (4) porque ambas tocan
                                                            ModalShell.tsx y conviene un solo PR
4. ModalShell + FAB: fix de animación de entrada (9.5)  ── mismo archivo (ModalShell.tsx) que (3);
                                                            hacerlas juntas evita dos diffs
                                                            superpuestos sobre las mismas líneas
5. aria-label + aria-expanded en botones icon-only (9.3)── independiente de (1)-(4); mecánico,
                                                            ~21 ubicaciones en 9 archivos
6. Reemplazar transition-all (9.6)                      ── independiente; toca Sidebar, Button,
                                                            FAB, layout.tsx, BudgetRing,
                                                            SummaryCard y los filtros de
                                                            transactions/page.tsx
7. prefers-reduced-motion (9.7)                         ── depende de (4) y (6): tiene que
                                                            envolver animaciones/transiciones que
                                                            ya sean reales — implementarla antes
                                                            dejaría media queries gateando clases
                                                            (animate-in) que hoy no hacen nada
8. active: (pressed) en botones/tarjetas (9.10)         ── recomendado después de (5): varios de
                                                            los mismos elementos (botones
                                                            icon-only) se tocan en ambas tareas;
                                                            hacerlo en el mismo pase evita reabrir
                                                            los mismos archivos dos veces
9. autocomplete + aria-live en los 4 forms de auth
   (9.8 + 9.9)                                           ── totalmente independiente del resto;
                                                            mismos 4 archivos para ambos ítems,
                                                            agrupar en un solo PR; puede hacerse en
                                                            paralelo con cualquiera de los
                                                            anteriores por otro agente/persona
```

Los pasos 1-2 y 3-4 están agrupados porque **tocan los mismos archivos** (`Input.tsx`/
`Select.tsx` y `ModalShell.tsx` respectivamente) — no por urgencia relativa. El paso 9
(formularios de auth) es la única rama del árbol sin ninguna dependencia con el resto: puede
implementarse en paralelo desde el día 1 si hay más de un agente/persona disponible.

Estimación total heredada del ROADMAP: 2h + 3h + 8h + 3h + 2h + 3h + 4h + 2h + 2h + 3h = **32h
(~4 días de trabajo de 8h)**. Ninguna estimación individual se ajusta al alza — la exploración
confirma que cada ítem es del tamaño que describe el ROADMAP (ver hallazgos arriba); donde el
inventario resultó más largo de lo esperado (9.3, 9.6) el trabajo por ubicación es mecánico
(una línea de JSX), así que el conteo mayor no cambia la estimación en horas.

---

## Tareas de Frontend

### 9.1 — `focus-visible` en vez de `focus` en `Button`/`Input`/`Select`

**Problema confirmado:** las tres clases de anillo de foco (`focus:ring-2 focus:outline-none`,
más `focus:ring-primary/50` como color) se activan con **cualquier** foco, incluido un click de
mouse — no solo navegación por teclado. Confirmado en:
- `frontend/components/ui/Button.tsx:41`
- `frontend/components/ui/Input.tsx:17` (más `focus:border-primary/50` en la línea 20)
- `frontend/components/ui/Select.tsx:17` (más `focus:border-primary/50` en la línea 20)

**Decisión 9.1.1 — solo el anillo (`ring`) pasa a `focus-visible:`, el cambio de color de borde
se queda en `focus:`.** El anillo es el elemento visualmente agresivo que no debería aparecer en
un click de mouse; el cambio sutil de color de borde en `Input`/`Select` (`focus:border-primary/50`)
es una señal de estado normal y aceptable tanto para mouse como para teclado — no hace falta
gatearlo. Aplicar `focus-visible:` a *todo* generaría inconsistencia (el borde cambiaría de color
con teclado pero no con mouse, mientras el resto de la app no distingue eso en ningún otro
control).

**Pasos:**
1. `Button.tsx:41` — reemplazar `focus:ring-primary/50 ... focus:ring-2 focus:outline-none` por
   `focus-visible:ring-primary/50 focus-visible:ring-2 focus-visible:outline-none`.
2. `Input.tsx:17` — mismo reemplazo para `focus:ring-primary/50 ... focus:ring-2
   focus:outline-none`; dejar `focus:border-primary/50` (línea 20) sin tocar.
3. `Select.tsx:17` — mismo reemplazo; dejar `focus:border-primary/50` (línea 20) sin tocar.

**Estimación:** 2h (heredada del ROADMAP, confirmada — cambio mecánico en 3 archivos).

**Criterio de aceptación:**
- Hacer click con mouse en un botón/input/select: no debe aparecer el anillo de color.
- Navegar con `Tab` hasta el mismo control: el anillo **debe** aparecer.
- Verificación manual con teclado en las 3 pantallas que más usan estos controles hoy:
  `login`, `accounts/page.tsx` (formularios en modal), `budgets/page.tsx`.

---

### 9.2 — Asociar `<label>` con su control (`htmlFor`/`id`) en `Input.tsx` y `Select.tsx`

**Problema confirmado:** en ambos componentes el `<label>` es un elemento hermano del
`<input>`/`<select>` sin ninguna relación programática — ni `htmlFor` en el label ni `id` en el
control (`Input.tsx:14-23`, `Select.tsx:14-25`). Clickear el texto del label no enfoca el campo;
un lector de pantalla que llega al control no anuncia su nombre.

**Decisión 9.2.1 — generar el `id` con `useId()`, sin exigir que cada call site pase uno
manualmente.** Confirmado que ningún consumidor de `<Input>`/`<Select>` en todo el proyecto pasa
`id` hoy (hallazgo 9 arriba) — no hay riesgo de colisión ni de romper un caso existente.
`Input`/`Select` deben, no obstante, respetar un `id` explícito si algún call site futuro lo
pasa (formularios que necesiten enlazar con `aria-describedby` externo, por ejemplo), usando
`props.id ?? generatedId` en vez de generar uno siempre e ignorar el que venga en `rest`.

**Pasos (`Input.tsx`):**
1. Importar `useId` de React.
2. Dentro del componente: `const generatedId = useId(); const inputId = rest.id ?? generatedId;`
3. `<label htmlFor={inputId} ...>` (línea 14).
4. `<input id={inputId} ref={ref} ... />` (línea 15) — cuidado con el orden de spread: `{...rest}`
   ya incluye `rest.id` si el caller lo pasó, así que `id={inputId}` debe ir **después** de
   `{...rest}` en el JSX para no ser sobrescrito (o extraer `id` explícitamente de `rest` en la
   desestructuración de props para no duplicarlo).

**Pasos (`Select.tsx`):** mismo patrón, `<label htmlFor={selectId}>` (línea 14),
`<select id={selectId}>` (línea 15).

**Estimación:** 3h (heredada del ROADMAP — el tiempo extra frente a 9.1 es por el cuidado con el
orden de props/spread y la verificación con lector de pantalla).

**Criterio de aceptación:**
- Click en el texto del label enfoca el input/select correspondiente, en cada formulario que usa
  estos componentes (login, register, todos los modales de `accounts/`, `categories/`,
  `budgets/`, `transactions/`).
- Con NVDA/VoiceOver activo, al hacer foco en un campo se anuncia su label (ej. "Correo
  Electrónico, editar texto").
- No hay dos elementos con el mismo `id` en la misma página (verificar en una pantalla con
  múltiples inputs, ej. el modal de edición de transacción con 6 campos).

---

### 9.3 — `aria-label` (y `aria-expanded` donde aplica) en todos los botones icon-only

**Inventario confirmado** (21 ubicaciones sin `aria-label`, en 9 archivos — ver hallazgo 4
arriba para la distinción entre "sin nada" y "solo `title`"):

| Archivo | Líneas | Botón | Estado actual |
|---|---|---|---|
| `components/Sidebar.tsx` | 95-107 | Colapsar/expandir sidebar (desktop) | Sin nada |
| `components/Sidebar.tsx` | 177-183, 195-201 | Cerrar sesión (×2 variantes) | `title="Cerrar sesión"` |
| `components/ThemeToggle.tsx` | 97-103 | Cambiar tema | `title` dinámico |
| `components/ui/ModalShell.tsx` | 21-26 | Cerrar modal (X) | Sin nada |
| `components/FloatingActionButton.tsx` | 22-32 | Abrir/cerrar menú del FAB | Sin nada |
| `app/(dashboard)/accounts/page.tsx` | 210-224 | Destacar cuenta | `title` dinámico |
| `app/(dashboard)/accounts/page.tsx` | 225-235 | Editar cuenta | `title="Editar cuenta"` |
| `app/(dashboard)/accounts/page.tsx` | 236-246 | Eliminar cuenta | `title="Eliminar cuenta"` |
| `app/(dashboard)/categories/page.tsx` | 180-190 | Editar categoría | `title="Editar categoría"` |
| `app/(dashboard)/categories/page.tsx` | 191-201 | Eliminar categoría | `title="Eliminar categoría"` |
| `app/(dashboard)/budgets/page.tsx` | 185-190 | Editar presupuesto | Sin nada |
| `app/(dashboard)/budgets/page.tsx` | 191-202 | Eliminar presupuesto | Sin nada |
| `app/(dashboard)/transactions/page.tsx` | 419-424 | Editar transacción | Sin nada |
| `app/(dashboard)/transactions/page.tsx` | 425-436 | Eliminar transacción | Sin nada |
| `app/(dashboard)/accounts/[id]/page.tsx` | 161-163 | Volver | Sin nada |
| `app/(dashboard)/accounts/[id]/page.tsx` | 235-240 | Editar transacción | Sin nada |
| `app/(dashboard)/accounts/[id]/page.tsx` | 241-250 | Eliminar transacción | Sin nada |
| `app/(dashboard)/categories/[id]/page.tsx` | 161-163 | Volver | Sin nada |
| `app/(dashboard)/categories/[id]/page.tsx` | 220-225 | Editar transacción | Sin nada |
| `app/(dashboard)/categories/[id]/page.tsx` | 226-235 | Eliminar transacción | Sin nada |

**Ya correctos, no tocar:** `app/(dashboard)/layout.tsx:48` (hamburguesa móvil,
`aria-label="Abrir menú"`) y `components/ChartControlsPopover.tsx:32`
(`aria-label="Configurar visualización"`) — usar este último como plantilla, tal como indica el
ROADMAP.

**Decisión 9.3.1 — agregar `aria-expanded` a los 3 botones que abren/cierran algo, no solo
`aria-label`.** `aria-label` por sí solo no comunica si un menú/panel está abierto o cerrado.
Aplica a: el toggle del sidebar (`Sidebar.tsx:95-107`, controla `isSidebarOpen`), el toggle del
FAB (`FloatingActionButton.tsx:22-32`, prop `isOpen` ya existe) y, aunque no está en el
inventario de "sin `aria-label`" porque ya lo tiene, `ChartControlsPopover.tsx:28-35` (prop
`open` ya existe) — se corrige de paso porque es la plantilla que el ROADMAP pide usar como
ejemplo; dejarla incompleta la vuelve un mal ejemplo a copiar en Fase 10/11. Costo marginal: la
lógica de estado abierto/cerrado ya existe en los 3 casos, solo falta el atributo
`aria-expanded={estado}`.

**Pasos:** para cada fila de la tabla, agregar `aria-label="<texto descriptivo en español>"` al
`<button>` (ej. `aria-label="Editar cuenta"`, `aria-label="Eliminar transacción"`,
`aria-label="Volver"`, `aria-label="Cerrar"` para el X de `ModalShell`, `aria-label="Registrar
movimiento"` o similar para el FAB). Donde ya exista `title`, mantenerlo (no hace daño, sigue
siendo el tooltip visual en desktop) y agregar `aria-label` con el mismo texto. Para los 3 casos
de la Decisión 9.3.1, agregar además `aria-expanded={isOpen}` (o el nombre de variable local
equivalente en cada componente).

**Estimación:** 1d (heredada del ROADMAP — 21 ubicaciones confirmadas, consistente con la
estimación "~20" del ROADMAP; cada cambio es una línea de JSX, el tiempo está en revisar cada
pantalla con lector de pantalla, no en escribir el código).

**Criterio de aceptación:**
- Con NVDA/VoiceOver, tabular por cada una de las 21 ubicaciones y confirmar que se anuncia un
  nombre descriptivo (no "botón" a secas ni el nombre del ícono SVG).
- Los 3 botones de disclosure (sidebar, FAB, `ChartControlsPopover`) anuncian "expandido"/
  "contraído" al abrir/cerrar.
- `layout.tsx:48` y `ChartControlsPopover.tsx:32` no cambian de comportamiento (ya correctos,
  el segundo solo gana `aria-expanded`).

---

### 9.4 — Cierre por Escape + `overscroll-behavior: contain` en `ModalShell` y `ConfirmDialog`

**Problema confirmado:** ninguno de los dos componentes escucha `Escape` (`grep` sobre
`Escape|keydown|onKeyDown` en todo `frontend/` no devuelve nada) ni tiene `overscroll-behavior`
en su contenedor scrolleable. En `ModalShell.tsx`, hacer scroll dentro del modal cuando su
contenido excede `max-h-[90vh]` (línea 18) puede seguir "atravesando" al scroll del body detrás.

**Decisión 9.4.1 — extraer un hook compartido `useEscapeToClose` en vez de duplicar la lógica en
los dos componentes.** `ModalShell` y `ConfirmDialog` son implementaciones independientes
(hallazgo 5 arriba) que van a necesitar exactamente el mismo comportamiento: escuchar `keydown`
en `document` solo mientras el modal está abierto, y llamar a `onClose`/`cancel` en `Escape`.
Ya existe el directorio `frontend/lib/hooks/` con 2 hooks (`useUserPreferences.ts`,
`useCurrentUser.ts`) — es el lugar natural para un tercero. Escribirlo dos veces (uno por
componente) es exactamente el tipo de duplicación mecánica que, si Fase 10/11 agregan un tercer
tipo de modal, se copiaría una vez más. El hook es pequeño (10-15 líneas) y de un solo propósito
— no es la capa de servicios/abstracción que `CLAUDE.md` marca como prematura, es una extracción
puntual para 2 (pronto 3) call sites idénticos.

```ts
// frontend/lib/hooks/useEscapeToClose.ts
export function useEscapeToClose(isOpen: boolean, onClose: () => void) {
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);
}
```

**Pasos:**
1. Crear `frontend/lib/hooks/useEscapeToClose.ts` (código arriba).
2. `ModalShell.tsx`: `useEscapeToClose(isOpen, onClose);` dentro del componente (después del
   `if (!isOpen) return null;` no funciona porque los hooks no pueden ser condicionales — llamar
   el hook *antes* del early return, y que el propio hook chequee `isOpen` internamente como en
   el snippet de arriba).
3. `ConfirmDialog.tsx`: `useEscapeToClose(isOpen, cancel);` mismo patrón (usa `cancel` de
   `useConfirmStore` como "cierre").
4. `overscroll-behavior: contain` — agregar la clase Tailwind nativa `overscroll-contain`
   (utilidad core, no requiere plugin) al contenedor con `overflow-y-auto` de `ModalShell.tsx`
   (línea 18) y al contenedor de `ConfirmDialog.tsx` (línea 13, aunque este no tiene overflow
   propio hoy — igual conviene por si el mensaje crece).

**Estimación:** 3h (heredada del ROADMAP — incluye escribir el hook, aplicarlo en 2 componentes,
y probar que no interfiere con otros listeners de `Escape` que pudiera agregar el navegador,
ej. cerrar un `<select>` nativo abierto).

**Criterio de aceptación:**
- Abrir cualquier modal (ej. "Editar cuenta") y presionar `Escape`: se cierra.
- Abrir `ConfirmDialog` (ej. intentar borrar una transacción) y presionar `Escape`: se cierra sin
  ejecutar la acción de confirmación.
- Con el modal abierto y contenido que excede el alto visible, hacer scroll hasta el final del
  contenido del modal: el scroll no debe "escapar" hacia el body de fondo.
- Verificar que `Escape` sigue cerrando un `<select>` nativo abierto sin disparar además el
  cierre del modal que lo contiene (si un `Select` está dentro de un modal).

---

### 9.5 — Arreglar la animación de entrada rota de `ModalShell`/`FloatingActionButton`

**Problema confirmado:** `ModalShell.tsx:18` usa `animate-in fade-in duration-200` y
`FloatingActionButton.tsx:18` usa `animate-in fade-in slide-in-from-bottom-2 duration-200` (ver
hallazgo 2 sobre la diferencia entre ambos). Ninguna de esas clases existe — ni como utilidad
core de Tailwind v4 ni como plugin instalado (hallazgo 1) — así que hoy ambos elementos aparecen
de golpe, sin transición.

**Decisión 9.5.1 — definir las animaciones directamente en `globals.css` con el mecanismo nativo
de Tailwind v4 (`--animate-*` en `@theme`), no instalar un plugin.** Consistente con el hallazgo
1: el archivo ya define tokens de tema (colores) con `@theme` — agregar las animaciones ahí sigue
la misma convención CSS-first en vez de introducir una dependencia nueva para 2 casos de uso.

```css
/* frontend/app/globals.css, dentro o junto al bloque @theme existente */
@theme {
  /* ...tokens de color existentes... */
  --animate-fade-in: fade-in 0.2s ease-out;
  --animate-slide-in-bottom: slide-in-bottom 0.2s ease-out;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slide-in-bottom {
  from { opacity: 0; transform: translateY(0.5rem); }
  to { opacity: 1; transform: translateY(0); }
}
```
Esto genera las utilidades `animate-fade-in` y `animate-slide-in-bottom` automáticamente (el
namespace `--animate-*` de `@theme` es el mecanismo documentado de Tailwind v4 para utilidades de
animación custom). **Validar la sintaxis exacta contra la versión instalada al implementar** —
no se ejecutó el build en la elaboración de este documento; si el namespace `--animate-*` no
genera la utilidad esperada en la versión exacta de `tailwindcss@^4` instalada, la alternativa de
respaldo es una clase manual (`@layer utilities { .animate-fade-in { animation: fade-in 0.2s
ease-out; } }`), igual de válida y sin dependencias.

**Pasos:**
1. Agregar el bloque de arriba a `globals.css`.
2. `ModalShell.tsx:18` — reemplazar `animate-in fade-in duration-200` por `animate-fade-in`.
3. `FloatingActionButton.tsx:18` — reemplazar `animate-in fade-in slide-in-from-bottom-2
   duration-200` por `animate-fade-in animate-slide-in-bottom` (o combinar ambos keyframes en
   una sola animación si se prefiere un solo `animation-name`).

**Estimación:** 2h (heredada del ROADMAP).

**Criterio de aceptación:**
- Abrir cualquier modal: el fondo/contenido hace fade-in visible (no aparece de golpe).
- Abrir el menú del FAB: el panel hace fade-in + slide-in-from-bottom visible.
- Verificar en DevTools que la clase `animate-fade-in` (o el nombre final elegido) efectivamente
  aplica una regla `animation` computada, no una clase sin efecto (repetir la verificación que
  detectó el bug original).

---

### 9.6 — Reemplazar `transition-all` por propiedades explícitas

**Inventario confirmado** (13 ocurrencias en 7 archivos — 2 no mencionadas en el texto del
ROADMAP, marcadas abajo):

| Archivo | Línea(s) | Elemento |
|---|---|---|
| `components/Sidebar.tsx` | 83, 123, 145 | Contenedor `<aside>`, link de nav activo, tooltip flotante |
| `components/ui/Button.tsx` | 41 | Botón base (todas las variantes) |
| `components/FloatingActionButton.tsx` | 25 | Botón circular del FAB |
| `app/(dashboard)/layout.tsx` | 40 | Contenedor principal (padding al colapsar sidebar) |
| `app/(dashboard)/transactions/page.tsx` | 507, 519, 532, 552, 577 | Inputs/selects de filtro (markup manual, no usan `Input`/`Select`) |
| `components/charts/BudgetRing.tsx` | 75 | *(no mencionado en el ROADMAP)* Anillo de progreso SVG |
| `components/ui/SummaryCard.tsx` | 15 | *(no mencionado en el ROADMAP)* Tarjeta de resumen (ya usa `hover:scale`) |

**Pasos:** por cada ocurrencia, identificar qué propiedades realmente cambian y listarlas
explícitamente en vez de `transition-all`:
- `Sidebar.tsx:83` → `transition-[width]` (el ancho es lo que anima al colapsar) más
  `duration-300 ease-in-out` ya presentes.
- `Sidebar.tsx:123` → `transition-colors` (bg/text del link activo).
- `Sidebar.tsx:145` → `transition-[transform,opacity]` (el tooltip escala con `scale-0` →
  `scale-100`).
- `Button.tsx:41` → `transition-colors` (los 4 `variantStyles` solo cambian `bg`/`text`/`border`
  vía `hover:`).
- `FloatingActionButton.tsx:25` → `transition-[transform,box-shadow,background-color]` (rota,
  cambia sombra y color de fondo al abrir/cerrar).
- `layout.tsx:40` → `transition-[padding]`.
- `transactions/page.tsx` (5 ocurrencias) → `transition-colors` (mismo patrón que
  `Input`/`Select`, ya que estos inputs de filtro replican su estilo a mano en vez de reusar los
  componentes — no se recomienda unificarlos con `Input`/`Select` dentro de este ítem, es un
  cambio de alcance mayor no pedido por el ROADMAP; se deja anotado como oportunidad de
  refactor para una fase de limpieza posterior, no de Fase 9).
- `BudgetRing.tsx:75` → `transition-[stroke-dashoffset]` (es un `<circle>` SVG animando su
  progreso).
- `SummaryCard.tsx:15` → `transition-transform` (el único cambio real es el `hover:scale`).

**Estimación:** 3h (heredada del ROADMAP — 13 ocurrencias mecánicas, el tiempo está en verificar
visualmente que ninguna transición implícita se pierde).

**Criterio de aceptación:**
- Cada elemento sigue animando exactamente lo mismo que antes (verificación visual, no debe
  haber diferencia perceptible salvo mejor rendimiento).
- DevTools → Performance: al hacer hover/toggle sobre cualquiera de estos elementos, Chrome no
  reporta recalculo de propiedades no relacionadas con la transición declarada.

---

### 9.7 — `prefers-reduced-motion`

**Problema confirmado:** cero ocurrencias en todo el proyecto (hallazgo 7), pese a que
`globals.css:70-77` aplica una transición global de color/fondo/borde a **todos** los elementos
(`*, *::before, *::after`), y varios componentes usan `animate-pulse` (`Skeleton.tsx`),
`animate-spin` (spinner de carga en `Button.tsx:45`) y `hover:scale` (`SummaryCard.tsx`, y tras
9.6 también el resto de transiciones explícitas).

**Decisión 9.7.1 — gatear la transición global y las animaciones decorativas, pero no el
`animate-spin` del spinner de carga.** Un spinner de carga es una señal funcional de "esto está
procesando", no decoración — quitarlo con `prefers-reduced-motion: reduce` dejaría al usuario sin
ninguna indicación de que un botón está cargando. Las Web Interface Guidelines (y WCAG 2.3.3 a
nivel AAA) apuntan a reducir movimiento *no esencial*; el spinner es esencial. Si se quiere ser
más conservador, la alternativa es mantener el giro pero eliminar cualquier posible aceleración/
efecto adicional — no aplica hoy porque el spinner no tiene nada más que el giro.

**Pasos:**
1. `globals.css`, envolver la transición global (líneas 65-78) en
   `@media (prefers-reduced-motion: no-preference) { ... }`.
2. Agregar un bloque `@media (prefers-reduced-motion: reduce)` que neutralice explícitamente
   `animate-pulse`, `hover:scale` y las animaciones nuevas de 9.5 (`animate-fade-in`,
   `animate-slide-in-bottom`) reduciendo su `animation-duration`/`transition-duration` a un valor
   casi nulo (patrón estándar: `animation-duration: 0.01ms !important; transition-duration:
   0.01ms !important;` aplicado a `*` salvo `animate-spin`, para no tener que enumerar cada
   componente individualmente):
   ```css
   @media (prefers-reduced-motion: reduce) {
     *:not(.animate-spin),
     *:not(.animate-spin)::before,
     *:not(.animate-spin)::after {
       animation-duration: 0.01ms !important;
       animation-iteration-count: 1 !important;
       transition-duration: 0.01ms !important;
       scroll-behavior: auto !important;
     }
   }
   ```

**Estimación:** 4h (heredada del ROADMAP — el tiempo extra frente a otros ítems de CSS es por
probar en un entorno real con "reducir movimiento" activado, que requiere cambiar configuración
de SO/navegador, no solo DevTools).

**Criterio de aceptación:**
- Activar "Reducir movimiento" en el SO (macOS: Accesibilidad → Pantalla; Windows: Configuración
  → Accesibilidad → Efectos visuales; o emular con `prefers-reduced-motion` en DevTools →
  Rendering) y verificar: el fade-in de modales es instantáneo, el `hover:scale` de
  `SummaryCard` no escala, la transición de colores global no se percibe — pero el spinner de
  carga de `Button` sigue girando.
- Sin la preferencia activada, todo el comportamiento (incluyendo 9.5 y 9.6) sigue igual que
  antes de este ítem.

---

### 9.8 — `autocomplete` en los formularios de autenticación

**Problema confirmado:** ningún `<Input>` en los 4 formularios tiene `autocomplete`. Archivos y
campos:
- `app/(auth)/login/page.tsx:94-102` (email), `105-113` (password).
- `app/(auth)/register/page.tsx:85-93` (nombre), `95-103` (email), `105-114` (password),
  `116-124` (confirmar password).
- `app/(auth)/forgot-password/page.tsx:76-84` (email).
- `app/(auth)/reset-password/page.tsx:129-138` (nueva password), `140-148` (confirmar password).

**Pasos:** agregar el atributo correspondiente a cada `<Input>` (se propaga vía `...rest` de
`InputProps`, no requiere ningún cambio en `Input.tsx`):
- Email en login/register/forgot-password → `autoComplete="email"`.
- Password en login → `autoComplete="current-password"`.
- Password/confirmar en register y reset-password (contraseña **nueva**, no la actual) →
  `autoComplete="new-password"` en ambos campos.
- Nombre completo en register → `autoComplete="name"`.

**Estimación:** 2h (heredada del ROADMAP).

**Criterio de aceptación:**
- El gestor de contraseñas del navegador ofrece autocompletar/guardar credenciales en login y
  register con los valores correctos en cada campo (no confunde "nueva contraseña" con
  "contraseña actual").
- Ningún campo de contraseña nueva sugiere autocompletar con una contraseña guardada existente
  (comportamiento esperado de `new-password`).

---

### 9.9 — `aria-live="polite"` en los mensajes de error/éxito de los 4 formularios de auth

**Problema confirmado:** los banners de error/éxito de los 4 formularios (`login/page.tsx:72-90`,
`register/page.tsx:78-82`, `forgot-password/page.tsx:68-72`, `reset-password/page.tsx:120-125`)
son `<div>` condicionales sin ningún atributo `aria-live`/`role`. Un usuario de lector de
pantalla que dispara un error de validación no se entera salvo que navegue manualmente hasta
encontrar el mensaje.

**Decisión 9.9.1 — usar `role="status" aria-live="polite"` uniformemente, tal como pide el
ROADMAP, con una advertencia sobre la fiabilidad del patrón actual (montaje condicional).** El
ROADMAP pide específicamente `polite` (no `assertive`/`role="alert"`, que sería lo más común para
errores según WCAG) — se respeta esa elección explícita en vez de sustituirla, para no
introducir un criterio distinto sin que el ROADMAP lo haya decidido. Advertencia técnica: hoy
estos `<div>` se montan y desmontan condicionalmente (`{error && <div ...>}`) — el patrón más
fiable para `aria-live` es tener el contenedor **siempre presente** en el DOM (vacío por
defecto) y solo cambiar su texto, porque algunas combinaciones de navegador/lector de pantalla
no anuncian de forma consistente una región `aria-live` que aparece y ya trae contenido en el
mismo render. El patrón condicional actual funciona razonablemente bien en NVDA/VoiceOver/JAWS
recientes, así que no es necesario reescribir la estructura de los 4 formularios para este
ítem — se dejan los `<div>` condicionales tal como están, solo se les agrega el atributo — pero
si en la verificación manual (ver criterio de aceptación) algún lector de pantalla no anuncia el
mensaje, la solución de respaldo es montar el contenedor vacío desde el inicio.

**Pasos:** agregar `role="status" aria-live="polite" aria-atomic="true"` a cada uno de los 5
`<div>` de banner (login tiene 3: registro exitoso, reset exitoso, error; los otros 3 formularios
tienen 1 cada uno).

**Nota relacionada (fuera de alcance estricto de este ítem, ver hallazgo 8):** los paneles de
página completa (`ForgotPasswordPage` tras éxito, `InvalidLinkPanel` en `reset-password`) no son
banners inline y no quedan cubiertos por este cambio — quien implemente puede opcionalmente
mover el foco al `<h1>` de esos paneles al montarlos (`ref` + `.focus()` con `tabIndex={-1}`)
como mejora adicional, pero no es parte de la estimación de 2h de este ítem.

**Estimación:** 2h (heredada del ROADMAP).

**Criterio de aceptación:**
- Con NVDA/VoiceOver activo, provocar un error de validación (ej. contraseñas que no coinciden
  en register) y confirmar que el mensaje se anuncia sin que el usuario tenga que navegar hasta
  él manualmente.
- Repetir para el mensaje de éxito de login (`?registered=true`) y de `forgot-password`.
- Si algún lector de pantalla no anuncia el mensaje en la verificación manual, aplicar el
  respaldo descrito en la Decisión 9.9.1 (contenedor siempre montado) antes de dar el ítem por
  cerrado.

---

### 9.10 — Estado `active:` (pressed) en botones y tarjetas clicables

**Problema confirmado:** cero clases `active:` en todo el proyecto (hallazgo 7). Hay `hover:` en
prácticamente todos los elementos interactivos, pero ningún feedback visual de "esto se está
presionando ahora mismo" — relevante sobre todo en touch (donde no existe `hover`) y para
feedback táctil general.

**Alcance recomendado** (no es necesario ni pedido "todo hover: necesita un active:" — priorizar
los elementos con mayor superficie de uso):
1. `components/ui/Button.tsx` — agregar `active:` a los 4 `variantStyles` (línea 16-22). Un solo
   cambio cubre todos los usos de `Button` en la app (es el componente con más leverage de todo
   este documento). Sugerido: `active:scale-[0.98]` combinado con un oscurecimiento leve
   (`active:brightness-95` para `primary`/`secondary`, ya existe `hover:brightness-110` en
   `primary` como referencia de patrón).
2. Los ~21 botones icon-only ya tocados en 9.3 (mismo pase, evita reabrir los mismos 9 archivos
   una tercera vez) — `active:scale-95` o `active:bg-surface-elevated` según el caso.
3. Tarjetas clicables envueltas en `Link` con `hover:scale` ya existente:
   `components/ui/SummaryCard.tsx:15` (agregar `active:scale-100` o similar, considerando que ya
   tiene `max-sm:hover:scale-100` para mobile — ver que no colisionen), y las tarjetas de cuenta/
   categoría en `accounts/page.tsx`/`categories/page.tsx` (el `<Link>` que envuelve cada tarjeta,
   no los botones de acción internos que ya se cubren en el punto 2).
4. Los links de navegación del sidebar (`Sidebar.tsx:117-149`) — `active:bg-surface` o similar,
   distinto del estado `isActive` (ruta actual) que ya usa `bg-primary`.

**Estimación:** 3h (heredada del ROADMAP — el alcance recomendado prioriza `Button.tsx` como el
cambio de mayor cobertura, dejando el resto del tiempo para las tarjetas y el sidebar).

**Criterio de aceptación:**
- En un dispositivo táctil (o emulación touch de DevTools), tocar y mantener presionado cualquier
  botón/tarjeta del alcance: debe verse un cambio visual inmediato (escala/color) mientras se
  mantiene presionado, no solo al soltar.
- El estado `active:` no debe persistir después de soltar (verificar que no queda "pegado" en
  navegadores donde `:active` a veces se comporta distinto en mobile Safari).
- No debe haber conflicto visual entre `active:` y el estado `isActive` (ruta actual) del sidebar
  — deben poder distinguirse ambos casos si coinciden.

---

## Tareas de Backend

Sin tareas de backend en esta fase — Fase 9 es una corrección de accesibilidad y hábitos de CSS
puramente en `frontend/`, sin ningún endpoint, modelo o migración involucrado. Ver Fase 10
(captura en 3 toques) y Fase 11 (dashboard de flujo mensual) en `docs/ROADMAP.md` para el
trabajo de backend que sí corresponde a las fases siguientes (idempotencia de `POST
/transactions`, corrección de los 3 bugs multi-moneda, `actualizar_transaccion` no actualiza
`currency`).

---

## Resumen de archivos tocados por ítem

| Ítem | Archivos |
|---|---|
| 9.1 focus-visible | `Button.tsx`, `Input.tsx`, `Select.tsx` |
| 9.2 label htmlFor/id | `Input.tsx`, `Select.tsx` |
| 9.3 aria-label icon-only | `Sidebar.tsx`, `ThemeToggle.tsx`, `ModalShell.tsx`, `FloatingActionButton.tsx`, `ChartControlsPopover.tsx`, `accounts/page.tsx`, `categories/page.tsx`, `budgets/page.tsx`, `transactions/page.tsx`, `accounts/[id]/page.tsx`, `categories/[id]/page.tsx` |
| 9.4 Escape + overscroll | `lib/hooks/useEscapeToClose.ts` (nuevo), `ModalShell.tsx`, `ConfirmDialog.tsx` |
| 9.5 animación de entrada | `globals.css`, `ModalShell.tsx`, `FloatingActionButton.tsx` |
| 9.6 transition-all | `Sidebar.tsx`, `Button.tsx`, `FloatingActionButton.tsx`, `layout.tsx`, `transactions/page.tsx`, `BudgetRing.tsx`, `SummaryCard.tsx` |
| 9.7 prefers-reduced-motion | `globals.css` |
| 9.8 autocomplete | `login/page.tsx`, `register/page.tsx`, `forgot-password/page.tsx`, `reset-password/page.tsx` |
| 9.9 aria-live | `login/page.tsx`, `register/page.tsx`, `forgot-password/page.tsx`, `reset-password/page.tsx` |
| 9.10 active: | `Button.tsx`, más los archivos de 9.3, `SummaryCard.tsx`, `accounts/page.tsx`, `categories/page.tsx`, `Sidebar.tsx` |

---

## Cierre

Este documento no implementa ningún cambio en el repositorio — es el desglose ejecutable de la
sección "Fase 9" de `docs/ROADMAP.md`, con archivos, líneas y decisiones de diseño concretas
para que un frontend-engineer pueda partir directamente de aquí sin tener que re-explorar el
código para tomar las mismas decisiones. Todos los hallazgos de este documento (conteos de
ocurrencias, líneas exactas, estado de `tailwindcss-animate`) fueron verificados contra el código
real de `frontend/` el 2026-08-23, no inferidos del texto del ROADMAP. Ningún archivo del
repositorio fuera de `docs/specs/fase_09_spec.md` fue modificado al producir este documento.
