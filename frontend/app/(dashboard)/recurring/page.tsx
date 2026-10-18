'use client';

import { useState } from 'react';
import { Plus, Repeat } from 'lucide-react';
import PendingRecurringSection from '@/components/recurring/PendingRecurringSection';
import RecurringCalendarSection from '@/components/recurring/RecurringCalendarSection';
import RecurringFormModal from '@/components/recurring/RecurringFormModal';
import RecurringRuleCard from '@/components/recurring/RecurringRuleCard';
import RecurringSuggestionsSection from '@/components/recurring/RecurringSuggestionsSection';
import Button from '@/components/ui/Button';
import EmptyState from '@/components/ui/EmptyState';
import QueryErrorState from '@/components/ui/QueryErrorState';
import Skeleton from '@/components/ui/Skeleton';
import { useAccounts } from '@/lib/hooks/useAccounts';
import { useCategories } from '@/lib/hooks/useCategories';
import { useRecurringRules } from '@/lib/hooks/useRecurring';
import type { RecurringRule, RecurringSuggestion } from '@/types/api';

/** Qué formulario está abierto: alta vacía, alta desde una sugerencia o edición de una regla. */
type FormState =
  | { mode: 'create' }
  | { mode: 'suggestion'; suggestion: RecurringSuggestion }
  | { mode: 'edit'; rule: RecurringRule };

export default function RecurringPage() {
  const [form, setForm] = useState<FormState | null>(null);
  const { data: rules, isLoading, isError, refetch } = useRecurringRules();
  const { data: accounts } = useAccounts();
  const { data: categories } = useCategories();
  const canOpenForm = Boolean(accounts?.length && categories);

  return (
    <div className="space-y-8 pb-10">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="font-sans text-2xl font-bold tracking-tight sm:text-3xl">Recurrentes</h1>
          <p className="text-text-muted mt-1 text-xs sm:text-sm">
            Arriendo, salario, suscripciones y cargos anuales: Oikos te propone cada ocurrencia y tú
            la confirmas.
          </p>
        </div>
        <Button onClick={() => setForm({ mode: 'create' })} disabled={!canOpenForm}>
          <Plus size={16} aria-hidden="true" />
          Nueva regla
        </Button>
      </div>

      {accounts && accounts.length === 0 && (
        <p className="text-text-muted text-sm">
          Primero crea una cuenta: cada regla registra sus movimientos en una cuenta.
        </p>
      )}

      <PendingRecurringSection />

      <section aria-labelledby="recurring-rules-title" className="space-y-3">
        <h2 id="recurring-rules-title" className="text-text text-lg font-bold">
          Reglas
        </h2>
        {isLoading ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-40" />
            ))}
          </div>
        ) : isError ? (
          <QueryErrorState message="No se pudieron cargar tus reglas." onRetry={() => refetch()} />
        ) : !rules || rules.length === 0 ? (
          <EmptyState
            icon={<Repeat size={48} className="opacity-20" />}
            message="Aún no tienes reglas recurrentes."
            description="Crea una para no teclear cada mes lo que siempre se repite."
            action={
              canOpenForm ? (
                <Button onClick={() => setForm({ mode: 'create' })}>
                  <Plus size={16} aria-hidden="true" />
                  Crea tu primera regla
                </Button>
              ) : undefined
            }
          />
        ) : (
          <ul className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {rules.map((rule) => (
              <RecurringRuleCard
                key={rule.id}
                rule={rule}
                onEdit={(r) => setForm({ mode: 'edit', rule: r })}
              />
            ))}
          </ul>
        )}
      </section>

      <RecurringCalendarSection />

      <RecurringSuggestionsSection
        disabled={!canOpenForm}
        onAccept={(suggestion) => setForm({ mode: 'suggestion', suggestion })}
      />

      {form && accounts && categories && (
        <RecurringFormModal
          rule={form.mode === 'edit' ? form.rule : undefined}
          suggestion={form.mode === 'suggestion' ? form.suggestion : undefined}
          accounts={accounts}
          categories={categories}
          onClose={() => setForm(null)}
        />
      )}
    </div>
  );
}
