'use client';

import { ArrowRightLeft, ArrowDownRight, ArrowUpRight, Trash2, Pencil, Circle } from 'lucide-react';
import { formatCurrency, formatDate } from '@/lib/utils';
import { useAppConfig } from '@/providers/AppConfigProvider';
import EmptyState from '@/components/ui/EmptyState';
import { useConfirmStore } from '@/store/useConfirmStore';
import CategoryIcon from '@/components/ui/CategoryIcon';
import Button from '@/components/ui/Button';
import type { Account, Category, Transaction } from '@/types/api';

interface TransactionListProps {
  items: Transaction[];
  accounts?: Account[];
  categories?: Category[];
  total: number;
  hasMore: boolean;
  loadingMore: boolean;
  onEdit: (transaction: Transaction) => void;
  onDelete: (id: number) => void;
  onLoadMore: () => void;
}

export default function TransactionList({
  items,
  accounts,
  categories,
  total,
  hasMore,
  loadingMore,
  onEdit,
  onDelete,
  onLoadMore,
}: TransactionListProps) {
  const { config } = useAppConfig();

  return (
    <div className="bg-surface border-border/70 shadow-background/20 overflow-hidden rounded-3xl border shadow-sm">
      {items.length === 0 ? (
        <EmptyState
          icon={<ArrowRightLeft size={48} className="opacity-20" />}
          message="Aún no tienes movimientos registrados."
        />
      ) : (
        <>
          <div className="divide-border/40 divide-y">
            {items.map((tx) => {
              const isExpense = tx.type === 'expense';
              const account = accounts?.find((a) => a.id === tx.account_id);
              const category = categories?.find((c) => c.id === tx.category_id);

              return (
                <div
                  key={tx.id}
                  className="hover:bg-surface-elevated group flex items-center justify-between gap-3 p-3 transition-colors sm:gap-4 sm:p-4 sm:px-6"
                >
                  <div className="flex min-w-0 items-center space-x-3 sm:space-x-4">
                    <div
                      className={`bg-background border-border/60 hidden shrink-0 rounded-full border p-2.5 sm:block ${isExpense ? 'text-text-muted' : 'text-primary'}`}
                    >
                      {isExpense ? <ArrowDownRight size={18} /> : <ArrowUpRight size={18} />}
                    </div>
                    <div className="min-w-0">
                      <p className="text-text truncate text-sm font-medium">{tx.description}</p>
                      <div className="text-text-muted mt-0.5 flex space-x-2 text-xs">
                        <span className="truncate">{account?.name || 'Cuenta eliminada'}</span>
                        <span className="hidden sm:inline">•</span>
                        <span className="hidden items-center gap-1 sm:inline-flex">
                          <CategoryIcon
                            icon={category?.icon}
                            size={12}
                            fallback={<Circle size={12} className="opacity-30" />}
                          />
                          {category?.name || 'Sin categoría'}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex shrink-0 items-center gap-2 sm:gap-6">
                    <div className="text-right">
                      <p
                        className={`font-sans text-sm font-semibold tabular-nums sm:text-base ${isExpense ? 'text-text' : 'text-primary'}`}
                      >
                        {isExpense ? '-' : '+'}
                        {formatCurrency(tx.amount, tx.currency)}
                      </p>
                      <p className="text-text-muted text-[11px] capitalize">
                        {formatDate(tx.date, config.locale)}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 opacity-100 sm:opacity-0 sm:transition-opacity sm:group-hover:opacity-100">
                      <button
                        onClick={() => onEdit(tx)}
                        className="text-text-muted hover:text-text hover:bg-surface-elevated rounded-lg p-2 transition-colors active:scale-95"
                        aria-label="Editar transacción"
                      >
                        <Pencil size={16} />
                      </button>
                      <button
                        onClick={() =>
                          useConfirmStore
                            .getState()
                            .confirm('¿Borrar esta transacción?', () => onDelete(tx.id))
                        }
                        className="text-text-muted hover:text-danger hover:bg-surface-elevated rounded-lg p-2 transition-colors active:scale-95"
                        aria-label="Eliminar transacción"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {hasMore && (
            <div className="border-border/40 flex justify-center border-t py-6">
              <Button
                variant="secondary"
                onClick={onLoadMore}
                disabled={loadingMore}
                loading={loadingMore}
              >
                {loadingMore ? 'Cargando...' : `Cargar más (${items.length} de ${total})`}
              </Button>
            </div>
          )}

          {!hasMore && items.length > 0 && (
            <p className="text-text-muted border-border/40 border-t py-4 text-center text-sm">
              Mostrando todas las {total} transacciones
            </p>
          )}
        </>
      )}
    </div>
  );
}
