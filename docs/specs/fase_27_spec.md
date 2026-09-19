# Fase 27 — Modularidad frontend: descomponer `transactions/page.tsx`

**Estado**: planeada 2026-09-19, deuda ya señalada en `docs/TODO.md` 🟢 y en la auditoría
2026-09-19 (`CODE_REVIEW.md` §2.1, §2.3): 646 líneas, sobre el umbral de alerta de 500 líneas del
checklist de estructura, subiendo desde 380 en julio.

## Objetivo

Extraer subcomponentes de `frontend/app/(dashboard)/transactions/page.tsx` sin cambiar
comportamiento ni estilos — refactor puro de modularidad, no una feature.

## Alcance

Tres piezas claramente separables por responsabilidad:

1. **`TransactionFilters`** — chips de preset de fecha, inputs de fecha inicial/final, selects de
   cuenta/categoría, botón "Limpiar filtros". Recibe el estado de filtros y los setters como
   props; no conoce la URL directamente (esa sincronización se queda en la página, vía
   `useQueryParamState`/`useQueryParamsBatch`).
2. **`TransactionList`** (incluye el row individual y el footer de paginación/"cargar más") —
   recibe `items`, `accounts`, `categories`, `hasMore`, `loadingMore`, y los callbacks
   `onEdit`/`onDelete`/`onLoadMore`.
3. **`EditTransactionModal`** — el modal de edición completo (form, validación por campo con
   foco automático, botones). Sigue el patrón ya usado por `components/modals/TransactionModal.tsx`
   — nombre de archivo: `components/modals/EditTransactionModal.tsx`.

Carpeta nueva `frontend/components/transactions/` para `TransactionFilters.tsx` y
`TransactionList.tsx` (no hay precedente de carpeta por dominio en `components/`, pero tampoco
encajan en `forms/` ni `modals/`).

`TransactionsPageContent` queda como orquestador: estado de filtros (URL-synced), paginación,
mutaciones (`deleteMutation`/`updateMutation` con sus invalidaciones), y composición de los tres
subcomponentes.

## Fuera de alcance

- Cambiar el comportamiento de filtros, paginación o edición.
- Cambiar el markup/clases Tailwind visualmente — el refactor debe ser invisible para el usuario.
- Los comentarios explicativos existentes (Fase 12 §12.1, §12.8.3; Fase 13 §13.6) se mueven junto
  con el código al que se refieren, no se borran.

## Verificación

- `pnpm lint` limpio.
- `pnpm build` sin errores de tipo (no hay typecheck dedicado en este repo, ver `CLAUDE.md`).
- Prueba manual: filtros (presets + fechas + cuenta + categoría + limpiar), paginación
  ("cargar más"), editar transacción (incluida validación con foco), borrar transacción con
  confirmación.
