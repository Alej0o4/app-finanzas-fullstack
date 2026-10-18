'use client';

import Link from 'next/link';
import { ChevronRight, Landmark } from 'lucide-react';
import { useCdts } from '@/lib/hooks/useCdts';

/**
 * Fase 38 F4: aviso del dashboard "N CDT por vencer". Cuenta los vigentes con alerta `due_soon` o
 * `matured` que ya calcula el backend. Mientras carga o si falla no ocupa lugar (el detalle y el
 * reintento viven en /cdts).
 */
export default function DueCdtCard() {
  const { data } = useCdts();
  const count = data?.items.filter((c) => c.status === 'active' && c.alert !== 'ok').length ?? 0;
  if (count === 0) return null;

  return (
    <Link
      href="/cdts"
      className="border-primary/30 bg-primary/10 hover:bg-primary/15 focus-visible:ring-primary/50 flex items-center justify-between gap-3 rounded-2xl border p-4 transition-colors focus-visible:ring-2 focus-visible:outline-none"
    >
      <span className="flex items-center gap-3">
        <Landmark size={20} className="text-primary shrink-0" aria-hidden="true" />
        <span className="text-text text-sm font-medium">
          {count} {count === 1 ? 'CDT por vencer o vencido' : 'CDT por vencer o vencidos'}
        </span>
      </span>
      <span className="text-primary inline-flex shrink-0 items-center gap-1 text-sm font-medium">
        Revisar
        <ChevronRight size={14} aria-hidden="true" />
      </span>
    </Link>
  );
}
