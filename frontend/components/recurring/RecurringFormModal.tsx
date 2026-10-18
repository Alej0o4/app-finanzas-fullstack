'use client';

import { useMemo, useState } from 'react';
import { toast } from 'sonner';
import ModalShell from '@/components/ui/ModalShell';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import { FREQUENCY_LABELS, formatDay } from '@/components/recurring/recurringPresentation';
import { useCreateRecurring, useUpdateRecurring } from '@/lib/hooks/useRecurring';
import { useTimezone } from '@/lib/hooks/useTimezone';
import { getVisibleCategories } from '@/lib/categoryVisibility';
import { todayInZone } from '@/lib/dates';
import { getApiError } from '@/lib/utils';
import { validateAmountText } from '@/lib/validateAmount';
import type {
  Account,
  Category,
  CreateRecurringPayload,
  RecurringFrequency,
  RecurringRule,
  RecurringSuggestion,
  UpdateRecurringPayload,
} from '@/types/api';

interface RecurringFormModalProps {
  /** Regla a editar; sin ella el modal crea una nueva. */
  rule?: RecurringRule;
  /** Sugerencia anual que prellena el formulario de alta (D16). Ignorada al editar. */
  suggestion?: RecurringSuggestion;
  accounts: Account[];
  categories: Category[];
  onClose: () => void;
}

/** Se monta solo mientras está abierto, así el estado arranca siempre desde la regla actual. */
export default function RecurringFormModal({
  rule,
  suggestion,
  accounts,
  categories,
  onClose,
}: RecurringFormModalProps) {
  const isEdit = rule !== undefined;
  const { displayTimezone } = useTimezone();
  const today = todayInZone(displayTimezone);

  const createMutation = useCreateRecurring();
  const updateMutation = useUpdateRecurring(rule?.id ?? 0);
  const isPending = createMutation.isPending || updateMutation.isPending;

  const [name, setName] = useState(rule?.name ?? suggestion?.name ?? '');
  const [type, setType] = useState<'income' | 'expense'>(rule?.type ?? 'expense');
  const [amount, setAmount] = useState(
    rule ? String(Number(rule.amount)) : suggestion ? String(Number(suggestion.amount)) : ''
  );
  // Si la cuenta/categoría de la regla se borró, el id ya no es una opción: se pide elegir otra.
  const [accountId, setAccountId] = useState(
    rule
      ? rule.account_missing
        ? ''
        : String(rule.account_id)
      : suggestion
        ? String(suggestion.account_id)
        : ''
  );
  const [categoryId, setCategoryId] = useState(
    rule
      ? rule.category_missing
        ? ''
        : String(rule.category_id)
      : suggestion
        ? String(suggestion.category_id)
        : ''
  );
  const [frequency, setFrequency] = useState<RecurringFrequency>(
    rule?.frequency ?? (suggestion ? 'yearly' : 'monthly')
  );
  const [startDate, setStartDate] = useState(
    rule?.start_date ?? suggestion?.suggested_start_date ?? today
  );
  const [errors, setErrors] = useState<{
    name?: string;
    amount?: string;
    account?: string;
    category?: string;
    date?: string;
    form?: string;
  }>({});

  // La categoría actual (o la sugerida) siempre es una opción, aunque sea del otro tipo
  // (reembolsos por categoría cruzada, Fase 31).
  const currentCategoryId = rule?.category_id ?? suggestion?.category_id;
  const visibleCategories = useMemo(
    () => getVisibleCategories(categories, type, false, currentCategoryId),
    [categories, type, currentCategoryId]
  );
  const selectedAccount = accounts.find((a) => String(a.id) === accountId);
  const currency = selectedAccount?.currency ?? rule?.currency ?? suggestion?.currency;

  const handleTypeChange = (next: 'income' | 'expense') => {
    setType(next);
    // Si la categoría elegida deja de estar entre las opciones, se vuelve a pedir.
    const stillVisible = getVisibleCategories(categories, next, false, currentCategoryId).some(
      (c) => String(c.id) === categoryId
    );
    if (!stillVisible) setCategoryId('');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isPending) return;

    const next: typeof errors = {};
    const trimmed = name.trim();
    if (!trimmed) next.name = 'Ponle un nombre a la regla.';
    const amountError = validateAmountText(amount);
    if (amountError) next.amount = amountError;
    if (!accountId) next.account = 'Elige la cuenta.';
    if (!categoryId) next.category = 'Elige la categoría.';
    if (!isEdit && !startDate) next.date = 'Indica la fecha de la primera ocurrencia.';
    setErrors(next);
    if (Object.keys(next).length > 0) return;

    const onError = (error: unknown) => {
      const message = getApiError(error);
      // El 422 de `start_date` (más de un año atrás o muy futura) es del campo fecha.
      if (!isEdit && /start_date|fecha|año/i.test(message)) setErrors({ date: message });
      else setErrors({ form: message });
    };

    if (isEdit) {
      const payload: UpdateRecurringPayload = {};
      if (trimmed !== rule.name) payload.name = trimmed;
      if (Number(amount) !== Number(rule.amount)) payload.amount = Number(amount);
      if (Number(accountId) !== rule.account_id) payload.account_id = Number(accountId);
      if (Number(categoryId) !== rule.category_id) payload.category_id = Number(categoryId);
      if (Object.keys(payload).length === 0) return onClose();
      updateMutation.mutate(payload, {
        onSuccess: () => {
          toast.success('Regla actualizada');
          onClose();
        },
        onError,
      });
      return;
    }

    const payload: CreateRecurringPayload = {
      name: trimmed,
      type,
      amount: Number(amount),
      account_id: Number(accountId),
      category_id: Number(categoryId),
      frequency,
      start_date: startDate,
    };
    createMutation.mutate(payload, {
      onSuccess: () => {
        toast.success('Regla creada');
        onClose();
      },
      onError,
    });
  };

  return (
    <ModalShell isOpen onClose={onClose} title={isEdit ? 'Editar regla' : 'Nueva regla recurrente'}>
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {suggestion && !isEdit && (
          <p className="bg-primary/10 text-text rounded-xl p-2.5 text-xs">
            Prellenado con tu cargo anual de {formatDay(suggestion.last_date)}. Revisa los datos y
            crea la regla.
          </p>
        )}

        <Input
          label="Nombre"
          value={name}
          maxLength={100}
          onChange={(e) => setName(e.target.value)}
          error={errors.name}
          placeholder="Ej. Arriendo, Netflix, Seguro del carro"
          className="bg-background"
        />

        {isEdit ? (
          <p className="text-text-muted text-sm">
            Tipo: {rule.type === 'income' ? 'Ingreso' : 'Gasto'} ·{' '}
            {FREQUENCY_LABELS[rule.frequency]} · desde {formatDay(rule.start_date)}
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Select
              label="Tipo"
              value={type}
              onChange={(e) => handleTypeChange(e.target.value as 'income' | 'expense')}
              className="bg-background"
            >
              <option value="expense">Gasto</option>
              <option value="income">Ingreso</option>
            </Select>
            <Select
              label="Frecuencia"
              value={frequency}
              onChange={(e) => setFrequency(e.target.value as RecurringFrequency)}
              className="bg-background"
            >
              {(Object.keys(FREQUENCY_LABELS) as RecurringFrequency[]).map((f) => (
                <option key={f} value={f}>
                  {FREQUENCY_LABELS[f]}
                </option>
              ))}
            </Select>
          </div>
        )}

        <Input
          label={currency ? `Monto (${currency})` : 'Monto'}
          type="number"
          inputMode="decimal"
          min={0}
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          error={errors.amount}
          className="bg-background"
        />

        <Select
          label="Cuenta"
          value={accountId}
          onChange={(e) => setAccountId(e.target.value)}
          error={errors.account}
          className="bg-background"
        >
          <option value="" disabled>
            Selecciona...
          </option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} ({a.currency})
            </option>
          ))}
        </Select>
        {isEdit && rule.account_missing && (
          <p role="alert" className="text-danger -mt-2 text-xs">
            La cuenta original se borró: elige otra para que la regla vuelva a proponer.
          </p>
        )}

        <Select
          label="Categoría"
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
          error={errors.category}
          className="bg-background"
        >
          <option value="" disabled>
            Selecciona...
          </option>
          {visibleCategories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
        {isEdit && rule.category_missing && (
          <p role="alert" className="text-danger -mt-2 text-xs">
            La categoría original se borró: elige otra para que la regla vuelva a proponer.
          </p>
        )}

        {!isEdit && (
          <Input
            label="Primera ocurrencia"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            error={errors.date}
            className="bg-background"
          />
        )}

        {errors.form && (
          <p role="alert" className="text-danger text-sm">
            {errors.form}
          </p>
        )}

        <div className="mt-6 flex gap-3">
          <Button type="button" variant="ghost" onClick={onClose} className="flex-1">
            Cancelar
          </Button>
          <Button type="submit" loading={isPending} className="flex-1">
            {isEdit ? 'Guardar' : 'Crear regla'}
          </Button>
        </div>
      </form>
    </ModalShell>
  );
}
