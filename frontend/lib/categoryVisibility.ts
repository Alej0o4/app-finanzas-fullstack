import type { Category } from '@/types/api';

/**
 * Fase 31 F3 (Q10, QA-009, H13): la lista visible en el `<select>` de categoría de
 * `TransactionModal` y `EditTransactionModal` — la única fuente de verdad de "lo que se ve
 * es lo que se envía". Vive en un módulo compartido para que los dos modales no dupliquen
 * la regla y se puedan desincronizar otra vez.
 *
 * - Categorías ocultas ("oculta para mí", Fase 18) no se listan, salvo `currentCategoryId`
 *   (la categoría actual de una transacción en edición) — así el selector nunca arranca
 *   mostrando algo que no está entre las opciones.
 * - Con `showAll` apagado, solo las categorías del `type` del movimiento (más
 *   `currentCategoryId`, aunque sea de la otra naturaleza — un reembolso).
 * - Con `showAll` prendido, todas las categorías visibles (no ocultas), de cualquier tipo.
 */
export function getVisibleCategories(
  categories: Category[] | undefined,
  type: 'income' | 'expense',
  showAll: boolean,
  currentCategoryId?: number
): Category[] {
  return (categories ?? []).filter((category) => {
    const isCurrent = category.id === currentCategoryId;
    // La excepción de "siempre visible" es solo para el filtro de ocultas — el filtro de
    // tipo sigue aplicando (un reembolso ya arranca con el toggle activado, que apaga el
    // filtro de tipo por su cuenta; si el usuario lo apaga a mano, la categoría actual debe
    // poder salir de la lista y disparar el reset, no quedar pegada para siempre).
    if (category.is_hidden && !isCurrent) return false;
    if (showAll) return true;
    return category.type === type;
  });
}
