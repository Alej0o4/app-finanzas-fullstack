# Tareas Pendientes — Frontend Oikos

> Archivo de sesión para agentes autónomos. Cada tarea tiene checkbox `- [ ]`. Al completarla, cambiar a `- [x]`.

---

## Cómo usar este archivo

Cuando inicies una nueva sesión con un agente, incluye esta instrucción en tu prompt:

```
Lee /home/alejo/proyecto-finanzas/frontend/SESSION_TASKS.md para ver las tareas 
pendientes. Trabaja en orden de prioridad (P0 primero). Al completar cada tarea, 
marca el checkbox como [x] en el archivo. Al final de la sesión, haz un resumen 
de lo completado y lo que queda.
```

---

## P0 — Crítico (arquitectura)

### P0.1 — Crear directorio `frontend/types/` con interfaces compartidas

- [x] Crear `frontend/types/api.ts` con todas las interfaces de API
- [x] Alinear cada campo con los schemas Pydantic del backend (`backend/app/schemas/schemas.py`):
  - `Account` → incluir `id`, `name`, `type`, `balance`, `user_id`
  - `Transaction` → incluir `id`, `amount`, `type`, `description`, `date`, `account_id`, `category_id`, `user_id`
  - `Category` → incluir `id`, `name`, `type`, `user_id: number | null`
  - `Budget` → incluir `id`, `category_id`, `amount_limit`, `month`, `year`, `user_id`
  - `BudgetProgress` → incluir `budget_id`, `category_name`, `amount_limit`, `spent`, `percentage`
  - `DashboardSummary` → incluir `total_balance`, `monthly_income`, `monthly_expense`
  - `CashflowItem`, `CategoryDistributionItem` → tipos de analytics
  - Payloads: `CreateTransactionPayload`, `UpdateTransactionPayload`, `CreateAccountPayload`, `BudgetPayload`
- [x] Reemplazar todas las interfaces inline en pages y components por imports del nuevo archivo
- [x] Eliminar `interface UpdateTransactionPayload` duplicada en `accounts/[id]/page.tsx` y `categories/[id]/page.tsx`
- [x] Verificar que `tsc` no tire errores

**Archivos a modificar:**
- `app/(dashboard)/page.tsx`
- `app/(dashboard)/accounts/page.tsx`
- `app/(dashboard)/accounts/[id]/page.tsx`
- `app/(dashboard)/transactions/page.tsx`
- `app/(dashboard)/categories/page.tsx`
- `app/(dashboard)/categories/[id]/page.tsx`
- `app/(dashboard)/budgets/page.tsx`
- `app/(dashboard)/analytics/page.tsx`
- `components/modals/TransactionModal.tsx`
- `components/charts/BudgetRing.tsx`
- `lib/hooks/useCurrentUser.ts`

---

### P0.2 — UI System: extraer componentes base reutilizables

- [x] Crear `components/ui/ModalShell.tsx`
  - Props: `isOpen`, `onClose`, `title`, `children`
  - Encapsular: `fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200` + wrapper interno
- [x] Crear `components/ui/Button.tsx`
  - Variantes: `primary`, `secondary`, `danger`, `ghost`
  - Props: `variant`, `size`, `loading`, `disabled`, `children`, `onClick`, `type`
  - Soportar `isPending` con Loader2 automático
- [x] Crear `components/ui/Input.tsx`
  - Props: `label`, `error`, `type`, `...rest`
  - Incluir label flotante o superior con estilo unificado
- [x] Crear `components/ui/Select.tsx`
  - Igual que Input pero para selects
- [x] Crear `components/ui/Label.tsx` (wrapper de label con estilo compartido)
- [x] Crear `components/ui/EmptyState.tsx`
  - Props: `icon`, `message`, `description?`
  - Encapsular `p-12 text-center flex flex-col items-center text-text-muted`
- [x] Crear `components/ui/SummaryCard.tsx`
  - Props: `label`, `value`, `trend?`, `color?`
  - Reemplazar las 3 cards del dashboard
- [x] Refactorizar todos los pages para usar estos componentes
- [ ] **Bonus:** Agregar `variants` a Button con `tv()` o clsx para mantenerlo limpio

**Archivos a modificar:**
- `app/(dashboard)/page.tsx` (summary cards, empty states)
- `app/(dashboard)/accounts/page.tsx` (modal ×2, buttons, inputs, empty state)
- `app/(dashboard)/accounts/[id]/page.tsx` (modal, inputs, empty state)
- `app/(dashboard)/transactions/page.tsx` (buttons, inputs, empty state)
- `app/(dashboard)/categories/page.tsx` (modal ×2, buttons, inputs, empty state)
- `app/(dashboard)/categories/[id]/page.tsx` (modal, inputs, empty state)
- `app/(dashboard)/budgets/page.tsx` (modal, buttons, inputs, empty state)
- `components/modals/TransactionModal.tsx` (inputs, buttons)

---

## P1 — Alta (UX / data fetching)

### P1.1 — Success toasts en mutaciones

- [x] Agregar `toast.success("Cuenta creada correctamente")` en `accounts/page.tsx` → `createAccountMutation.onSuccess`
- [x] Agregar `toast.success("Cuenta actualizada")` en `accounts/page.tsx` → `updateAccountMutation.onSuccess`
- [x] Agregar `toast.success("Cuenta eliminada")` en `accounts/page.tsx` → `deleteAccountMutation.onSuccess`
- [x] Agregar `toast.success("Categoría creada")` en `categories/page.tsx` → `createCategoryMutation.onSuccess`
- [x] Agregar `toast.success("Categoría actualizada")` en `categories/page.tsx` → `updateCategoryMutation.onSuccess`
- [x] Agregar `toast.success("Categoría eliminada")` en `categories/page.tsx` → `deleteCategoryMutation.onSuccess`
- [x] Agregar `toast.success("Presupuesto guardado")` en `budgets/page.tsx` → `saveMutation.onSuccess`
- [x] Agregar `toast.success("Presupuesto eliminado")` en `budgets/page.tsx` → `deleteMutation.onSuccess`
- [x] Agregar `toast.success("Transacción creada")` en `components/modals/TransactionModal.tsx` → `createMutation.onSuccess`
- [x] Agregar `toast.success("Transacción actualizada")` en `accounts/[id]/page.tsx` y `categories/[id]/page.tsx` → `updateMutation.onSuccess`
- [x] Agregar `toast.success("Transacción eliminada")` en `transactions/page.tsx`, `accounts/[id]/page.tsx`, `categories/[id]/page.tsx` → `deleteMutation.onSuccess`

---

### P1.2 — Dashboard con skeleton loading

- [x] Reemplazar el spinner full-page del dashboard por skeletons individuales por sección
- [x] Crear componente `components/ui/Skeleton.tsx` con `className` prop para reutilizar
- [x] Skeleton para summary cards: rectángulo `h-32 rounded-2xl bg-surface-elevated animate-pulse`
- [x] Skeleton para budget rings: 4 círculos + texto animados
- [x] Skeleton para transacciones recientes: 5 filas animadas
- [x] Cada skeleton debe tener el mismo tamaño que el contenido real para evitar layout shift
- [x] Usar `bg-surface-elevated animate-pulse` como token de diseño

**Archivo a modificar:** `app/(dashboard)/page.tsx`

---

### P1.3 — Helper `getApiError()`

- [x] Crear función `getApiError(error: unknown): string` en `lib/utils.ts`
- [x] Extraer el patrón repetido:
  ```typescript
  const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
  ```
- [x] Reemplazar en todos los `onError` de mutaciones (8+ ocurrencias)

---

### P1.4 — Query Key Factory

- [x] Crear `lib/queryKeys.ts` con funciones fábrica
- [x] Reemplazar todos los strings `queryKey` en pages y componentes

---

## P2 — Media (rendimiento / UX avanzada)

### P2.1 — Remover `refetchOnMount: "always"` en Analytics

- [x] En `analytics/page.tsx` líneas 129 y 144, cambiar a comportamiento default (`"if-stale"`) o eliminar la prop
- [x] El staleTime global de 60s ya protege, no necesita refuerzo

---

### P2.2 — Optimistic updates en creación de transacciones

- [ ] En `TransactionModal.tsx`, usar `queryClient.setQueryData` en `onMutate` para insertar la nueva transacción localmente antes de que responda el server
- [ ] Usar `onSettled` para invalidar y refrescar desde el server
- [ ] Manejar `onError` con rollback si falla la mutación

---

### P2.3 — Logout siempre visible en sidebar colapsada

- [x] En `Sidebar.tsx`, el botón de logout tiene `isSidebarOpen ? "block" : "hidden"` (línea 109)
- [x] Cambiar a que siempre muestre el icono, ocultando solo el texto cuando está colapsado
- [x] Misma lógica que los nav items: icon siempre visible, texto condicional

---

## P3 — Bajo (futuras iteraciones)

- [ ] Paginación en feed de transacciones (offset/limit)
- [ ] Zod schemas para validación runtime de respuestas API
- [ ] ConfirmDialog con texto contextual (no siempre "Eliminar")
- [ ] Dirty-check en formularios (alertar al cancelar con datos)
- [ ] Botón "Hoy" en filtros de analytics
- [ ] Animación de salida en listas al eliminar (Framer Motion o CSS transitions)

---

## Progreso

| Prioridad | Total | Completadas |
|-----------|-------|-------------|
| P0        | 2     | 2           |
| P1        | 4     | 4           |
| P2        | 3     | 2           |
| P3        | 6     | 0           |
| **Total** | **15**| **8**       |
