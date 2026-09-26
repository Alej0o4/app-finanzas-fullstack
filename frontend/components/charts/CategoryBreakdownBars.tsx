'use client';

import { AlertCircle, Wallet } from 'lucide-react';
import type { CategoryDistributionItem } from '@/types/api';
import CategoryIcon from '@/components/ui/CategoryIcon';
import EmptyState from '@/components/ui/EmptyState';
import Skeleton from '@/components/ui/Skeleton';
import Button from '@/components/ui/Button';
import { formatCurrency } from '@/lib/utils';
import { useAppConfig } from '@/providers/AppConfigProvider';

interface CategoryBreakdownBarsProps {
  data: CategoryDistributionItem[] | undefined;
  isLoading: boolean;
  /** Fase 24 §24.1: distingue "falló la query" de "no hay gastos todavía". */
  isError?: boolean;
  /** Fase 24 §24.1: refetch de la query de category-distribution del caller. */
  onRetry?: () => void;
  /** Moneda para formatear los montos. Si se omite, cae a la preferida global (retrocompatible
   *  con el dashboard, Fase 17 §17.1 — la vista por cuenta pasa la moneda real de la cuenta). */
  currency?: string;
  /** Fase 29 §F5.4: el dashboard navega por mes, así que su mensaje de "sin gastos" nombra el
   *  mes visible. Si se omite queda el texto genérico (vista por cuenta, sin período). */
  emptyMessage?: string;
}

/**
 * Desglose de gastos del mes en curso por categoría, en barras horizontales proporcionales
 * al gasto máximo (Fase 11 §11.4).
 *
 * Vista de solo lectura: recibe datos ya calculados y ordenados por el backend
 * (GET /dashboard/category-distribution ordena descendente — no se reordena aquí) y no tiene
 * controles de filtro propios; esos viven en Analítica (CategoryDonutChart).
 */
export default function CategoryBreakdownBars({
  data,
  isLoading,
  isError = false,
  onRetry,
  currency,
  emptyMessage,
}: CategoryBreakdownBarsProps) {
  const { config } = useAppConfig();
  const rows = data ?? [];

  // El backend solo devuelve categorías con gasto agregado > 0; el piso en 1 evita
  // división por cero si algún día llega una fila con total 0.
  const maxTotal = Math.max(...rows.map((row) => Number(row.total)), 1);

  return (
    <div className="bg-surface border-border/70 shadow-background/20 rounded-2xl border p-6 shadow-sm">
      {isError ? (
        <EmptyState
          icon={<AlertCircle size={48} className="opacity-20" />}
          message="No se pudo cargar el desglose por categoría."
          action={
            <Button variant="secondary" size="sm" onClick={() => onRetry?.()}>
              Reintentar
            </Button>
          }
        />
      ) : isLoading ? (
        <div className="space-y-5">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="space-y-2">
              <div className="flex items-center justify-between">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-20" />
              </div>
              <Skeleton className="h-2 w-full rounded-full" />
            </div>
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<Wallet size={48} className="opacity-20" />}
          message={emptyMessage ?? 'No hay gastos registrados este mes.'}
          description="El desglose por categoría aparecerá cuando registres movimientos."
        />
      ) : (
        <ul className="space-y-5">
          {rows.map((item) => (
            <li key={item.category_id}>
              <div className="mb-1.5 flex items-center justify-between gap-3">
                <span className="flex min-w-0 items-center gap-2">
                  {/* Fase 24 §24.4: el contrato ahora incluye category_icon; el fallback solo
                      cubre categorías sin ícono asignado (icon: null), no todas. */}
                  <CategoryIcon
                    icon={item.category_icon}
                    fallback={<Wallet size={16} className="text-text-muted" />}
                  />
                  <span className="text-text truncate text-sm font-medium">
                    {item.category_name}
                  </span>
                </span>
                <span className="text-text shrink-0 text-sm font-semibold tabular-nums">
                  {formatCurrency(Number(item.total), currency ?? config.currency)}
                </span>
              </div>
              <div className="bg-surface-elevated h-2 w-full overflow-hidden rounded-full">
                <div
                  className="bg-primary h-full rounded-full"
                  style={{ width: `${(Number(item.total) / maxTotal) * 100}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
