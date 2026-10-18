'use client';

import Link from 'next/link';
import { ChevronRight, Repeat } from 'lucide-react';
import { usePendingRecurring } from '@/lib/hooks/useRecurring';

/**
 * Fase 37 F5: aviso del dashboard "Tienes N recurrentes por confirmar". Solo aparece si N > 0;
 * mientras carga o si falla no ocupa lugar (el detalle y el reintento viven en /recurring).
 * N es el conteo de ocurrencias que devuelve el backend, no se calcula aquí.
 */
export default function PendingRecurringCard() {
  const { data: pending } = usePendingRecurring();
  const count = pending?.length ?? 0;
  if (count === 0) return null;

  return (
    <Link
      href="/recurring"
      className="border-primary/30 bg-primary/10 hover:bg-primary/15 focus-visible:ring-primary/50 flex items-center justify-between gap-3 rounded-2xl border p-4 transition-colors focus-visible:ring-2 focus-visible:outline-none"
    >
      <span className="flex items-center gap-3">
        <Repeat size={20} className="text-primary shrink-0" aria-hidden="true" />
        <span className="text-text text-sm font-medium">
          Tienes {count} {count === 1 ? 'recurrente' : 'recurrentes'} por confirmar
        </span>
      </span>
      <span className="text-primary inline-flex shrink-0 items-center gap-1 text-sm font-medium">
        Revisar
        <ChevronRight size={14} aria-hidden="true" />
      </span>
    </Link>
  );
}
