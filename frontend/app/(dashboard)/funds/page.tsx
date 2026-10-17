'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Mail, Plus } from 'lucide-react';
import FundCard from '@/components/funds/FundCard';
import FundFormModal from '@/components/funds/FundFormModal';
import Button from '@/components/ui/Button';
import EmptyState from '@/components/ui/EmptyState';
import QueryErrorState from '@/components/ui/QueryErrorState';
import Skeleton from '@/components/ui/Skeleton';
import Switch from '@/components/ui/Switch';
import { useAccounts } from '@/lib/hooks/useAccounts';
import { useFunds } from '@/lib/hooks/useFunds';

export default function FundsPage() {
  const router = useRouter();
  const [includeArchived, setIncludeArchived] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const { data: funds, isLoading, isError, refetch } = useFunds({ includeArchived });
  const { data: accounts } = useAccounts();

  const openCreate = () => setIsCreating(true);

  return (
    <div className="space-y-6 pb-10">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="font-sans text-2xl font-bold tracking-tight sm:text-3xl">Sobres</h1>
          <p className="text-text-muted mt-1 text-xs sm:text-sm">
            Aparta dinero para lo que ya tiene destino: gastos anuales, emergencias y metas.
          </p>
        </div>
        <Button onClick={openCreate} disabled={!accounts?.length}>
          <Plus size={16} aria-hidden="true" />
          Nuevo sobre
        </Button>
      </div>

      <Switch
        label="Mostrar archivados"
        checked={includeArchived}
        onChange={(e) => setIncludeArchived(e.target.checked)}
      />

      {accounts && accounts.length === 0 && (
        <p className="text-text-muted text-sm">
          Primero crea una cuenta: cada sobre aparta dinero de una cuenta.
        </p>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-44" />
          ))}
        </div>
      ) : isError ? (
        <QueryErrorState message="No se pudieron cargar tus sobres." onRetry={() => refetch()} />
      ) : !funds || funds.length === 0 ? (
        <EmptyState
          icon={<Mail size={48} className="opacity-20" />}
          message={includeArchived ? 'No tienes sobres.' : 'Aún no tienes sobres.'}
          description="Un sobre aparta plata de una cuenta para que no la cuentes como disponible."
          action={
            accounts?.length ? (
              <Button onClick={openCreate}>
                <Plus size={16} aria-hidden="true" />
                Crea tu primer sobre
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {funds.map((fund) => (
            <FundCard key={fund.id} fund={fund} />
          ))}
        </div>
      )}

      {isCreating && accounts && (
        <FundFormModal
          accounts={accounts}
          onClose={() => setIsCreating(false)}
          onCreated={(fund) => router.push(`/funds/${fund.id}`)}
        />
      )}
    </div>
  );
}
