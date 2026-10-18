'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { Archive, ArchiveRestore, ArrowLeft, Minus, Pencil, Plus } from 'lucide-react';
import DeleteFundButton from '@/components/funds/DeleteFundButton';
import FundEntriesList from '@/components/funds/FundEntriesList';
import FundFormModal from '@/components/funds/FundFormModal';
import FundMovementModal from '@/components/funds/FundMovementModal';
import FundProgress from '@/components/funds/FundProgress';
import { KIND_LABELS, PaceChip } from '@/components/funds/fundPresentation';
import Button from '@/components/ui/Button';
import QueryErrorState from '@/components/ui/QueryErrorState';
import Skeleton from '@/components/ui/Skeleton';
import { useAccounts } from '@/lib/hooks/useAccounts';
import { useArchiveFund, useFund } from '@/lib/hooks/useFunds';
import { useTimezone } from '@/lib/hooks/useTimezone';
import { getApiError } from '@/lib/utils';
import { useConfirmStore } from '@/store/useConfirmStore';

type OpenModal = 'contribution' | 'withdrawal' | 'edit' | null;

export default function FundDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { displayTimezone } = useTimezone();
  const { data: fund, isLoading, isError, refetch } = useFund(id);
  const { data: accounts } = useAccounts();
  const archiveMutation = useArchiveFund(id);
  const [modal, setModal] = useState<OpenModal>(null);

  const archive = (shouldArchive: boolean) =>
    archiveMutation.mutate(shouldArchive, {
      onSuccess: () => toast.success(shouldArchive ? 'Sobre archivado' : 'Sobre reactivado'),
      onError: (error) => toast.error(getApiError(error)),
    });

  const backLink = (
    <Link
      href="/funds"
      className="text-text-muted hover:text-text inline-flex items-center gap-1.5 text-sm transition-colors"
    >
      <ArrowLeft size={16} aria-hidden="true" />
      Sobres
    </Link>
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        {backLink}
        <Skeleton className="h-44" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (isError || !fund) {
    return (
      <div className="space-y-6">
        {backLink}
        <QueryErrorState message="No se pudo cargar el sobre." onRetry={() => refetch()} />
      </div>
    );
  }

  const isArchived = fund.status === 'archived';
  const hasBalance = Number(fund.balance) > 0;

  return (
    <div className="space-y-6 pb-10">
      {backLink}

      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div className="min-w-0">
          <h1 className="font-sans text-2xl font-bold tracking-tight break-words sm:text-3xl">
            {fund.name}
          </h1>
          <p className="text-text-muted mt-1 text-xs sm:text-sm">
            {KIND_LABELS[fund.kind]} · {fund.currency}
            {isArchived && ' · Archivado'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {!isArchived && (
            <>
              <Button onClick={() => setModal('contribution')}>
                <Plus size={16} aria-hidden="true" />
                Aportar
              </Button>
              <Button
                variant="secondary"
                onClick={() => setModal('withdrawal')}
                disabled={!hasBalance}
                title={hasBalance ? undefined : 'El sobre no tiene saldo para retirar'}
              >
                <Minus size={16} aria-hidden="true" />
                Retirar
              </Button>
            </>
          )}
          {/* El backend rechaza editar un archivado (409): se desarchiva primero. */}
          {!isArchived && (
            <Button variant="secondary" onClick={() => setModal('edit')}>
              <Pencil size={16} aria-hidden="true" />
              Editar
            </Button>
          )}
          {isArchived ? (
            <Button
              variant="ghost"
              loading={archiveMutation.isPending}
              onClick={() => archive(false)}
            >
              <ArchiveRestore size={16} aria-hidden="true" />
              Desarchivar
            </Button>
          ) : (
            <Button
              variant="ghost"
              loading={archiveMutation.isPending}
              onClick={() =>
                // El backend responde 409 si el saldo no es 0; se avisa antes de intentarlo.
                hasBalance
                  ? toast.error('Retira el saldo del sobre antes de archivarlo.')
                  : useConfirmStore
                      .getState()
                      .confirm(
                        `¿Archivar el sobre "${fund.name}"? Podrás desarchivarlo después.`,
                        () => archive(true),
                        'Archivar'
                      )
              }
            >
              <Archive size={16} aria-hidden="true" />
              Archivar
            </Button>
          )}
          <DeleteFundButton fund={fund} onDeleted={() => router.replace('/funds')} />
        </div>
      </div>

      <div className="border-border bg-surface rounded-2xl border p-4 sm:p-6">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-text-muted text-sm font-medium">Resumen</h2>
          {!isArchived && <PaceChip pace={fund.pace} />}
        </div>
        <FundProgress fund={fund} />
      </div>

      <div className="border-border bg-surface rounded-2xl border p-4 sm:p-6">
        <h2 className="text-text mb-2 font-semibold">Movimientos</h2>
        <FundEntriesList
          entries={fund.entries}
          currency={fund.currency}
          timezone={displayTimezone}
        />
        {fund.entries.length >= 50 && (
          <p className="text-text-muted mt-2 text-xs">Se muestran los 50 más recientes.</p>
        )}
      </div>

      {(modal === 'contribution' || modal === 'withdrawal') && (
        <FundMovementModal fund={fund} mode={modal} onClose={() => setModal(null)} />
      )}
      {modal === 'edit' && accounts && (
        <FundFormModal fund={fund} accounts={accounts} onClose={() => setModal(null)} />
      )}
    </div>
  );
}
