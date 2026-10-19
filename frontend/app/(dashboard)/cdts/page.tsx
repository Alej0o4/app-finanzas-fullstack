'use client';

import { useState } from 'react';
import { Landmark, Plus } from 'lucide-react';
import CdtCard from '@/components/cdts/CdtCard';
import CdtFormModal from '@/components/cdts/CdtFormModal';
import CdtRedeemModal from '@/components/cdts/CdtRedeemModal';
import { money } from '@/components/recurring/recurringPresentation';
import Button from '@/components/ui/Button';
import EmptyState from '@/components/ui/EmptyState';
import QueryErrorState from '@/components/ui/QueryErrorState';
import Skeleton from '@/components/ui/Skeleton';
import { useCdts } from '@/lib/hooks/useCdts';
import type { Cdt } from '@/types/api';

/** Qué modal está abierto: alta vacía, edición o redención de un CDT. */
type ModalState = { mode: 'create' } | { mode: 'edit'; cdt: Cdt } | { mode: 'redeem'; cdt: Cdt };

export default function CdtsPage() {
  const [modal, setModal] = useState<ModalState | null>(null);
  const { data, isLoading, isError, refetch } = useCdts();

  // La lista ya viene ordenada del servidor (vigentes por vencimiento, redimidos por fecha desc);
  // aquí solo se parte por estado. Los `totals` son de los vigentes y también vienen calculados.
  const active = data?.items.filter((c) => c.status === 'active') ?? [];
  const redeemed = data?.items.filter((c) => c.status === 'redeemed') ?? [];
  const totals = data?.totals ?? [];
  const dueCount = active.filter((c) => c.alert !== 'ok').length;

  return (
    <div className="space-y-8 pb-10">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="font-sans text-2xl font-bold tracking-tight sm:text-3xl">CDT</h1>
          <p className="text-text-muted mt-1 text-xs sm:text-sm">
            Certificados de depósito a término: cuánto rinden hoy, cuándo vencen y cuánto recibirás.
            Suman a tu patrimonio, no a tu disponible.
          </p>
        </div>
        <Button onClick={() => setModal({ mode: 'create' })}>
          <Plus size={16} aria-hidden="true" />
          Nuevo CDT
        </Button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-56" />
          ))}
        </div>
      ) : isError ? (
        <QueryErrorState message="No se pudieron cargar tus CDT." onRetry={() => refetch()} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={<Landmark size={48} className="opacity-20" />}
          message="Aún no tienes CDT."
          description="Registra uno para ver su rendimiento a hoy y recibir el aviso antes de que venza."
          action={
            <Button onClick={() => setModal({ mode: 'create' })}>
              <Plus size={16} aria-hidden="true" />
              Registra tu primer CDT
            </Button>
          }
        />
      ) : (
        <>
          {dueCount > 0 && (
            <p role="status" className="bg-primary/10 text-text rounded-xl p-3 text-sm">
              {dueCount === 1
                ? 'Tienes 1 CDT por vencer o vencido.'
                : `Tienes ${dueCount} CDT por vencer o vencidos.`}{' '}
              Redímelo cuando el banco te pague.
            </p>
          )}

          {totals.length > 0 && (
            <section aria-labelledby="cdt-totals-title" className="space-y-3">
              <h2 id="cdt-totals-title" className="text-text text-lg font-bold">
                Resumen de vigentes
              </h2>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                {totals.map((t) => (
                  <div key={t.currency} className="border-border bg-surface rounded-2xl border p-4">
                    <p className="text-text-muted text-xs">Valor hoy · {t.currency}</p>
                    <p className="text-text mt-1 text-xl font-bold tabular-nums">
                      {money(t.current_value, t.currency)}
                    </p>
                    <dl className="text-text-muted mt-2 space-y-1 text-xs">
                      <div className="flex justify-between gap-2">
                        <dt>Capital</dt>
                        <dd className="text-text tabular-nums">{money(t.principal, t.currency)}</dd>
                      </div>
                      <div className="flex justify-between gap-2">
                        <dt>Rendimiento a hoy</dt>
                        <dd className="text-success tabular-nums">
                          + {money(t.accrued_interest, t.currency)}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-2">
                        <dt>Valor al vencimiento</dt>
                        <dd className="text-text tabular-nums">
                          {money(t.maturity_value, t.currency)}
                        </dd>
                      </div>
                    </dl>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section aria-labelledby="cdt-active-title" className="space-y-3">
            <h2 id="cdt-active-title" className="text-text text-lg font-bold">
              Vigentes
            </h2>
            {active.length === 0 ? (
              <p className="text-text-muted text-sm">No tienes CDT vigentes.</p>
            ) : (
              <ul className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                {active.map((cdt) => (
                  <CdtCard
                    key={cdt.id}
                    cdt={cdt}
                    onEdit={(c) => setModal({ mode: 'edit', cdt: c })}
                    onRedeem={(c) => setModal({ mode: 'redeem', cdt: c })}
                  />
                ))}
              </ul>
            )}
          </section>

          {redeemed.length > 0 && (
            <section aria-labelledby="cdt-redeemed-title" className="space-y-3">
              <h2 id="cdt-redeemed-title" className="text-text text-lg font-bold">
                Redimidos
              </h2>
              <ul className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                {redeemed.map((cdt) => (
                  <CdtCard key={cdt.id} cdt={cdt} onEdit={() => {}} onRedeem={() => {}} />
                ))}
              </ul>
            </section>
          )}
        </>
      )}

      {modal?.mode === 'create' && <CdtFormModal onClose={() => setModal(null)} />}
      {modal?.mode === 'edit' && <CdtFormModal cdt={modal.cdt} onClose={() => setModal(null)} />}
      {modal?.mode === 'redeem' && (
        <CdtRedeemModal cdt={modal.cdt} onClose={() => setModal(null)} />
      )}
    </div>
  );
}
