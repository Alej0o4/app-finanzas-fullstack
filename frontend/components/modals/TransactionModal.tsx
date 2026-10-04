'use client';

import { useMemo, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import { useAccounts } from '@/lib/hooks/useAccounts';
import { useCategories } from '@/lib/hooks/useCategories';
import { getApiError } from '@/lib/utils';
import { todayInZone } from '@/lib/dates';
import { useTimezone } from '@/lib/hooks/useTimezone';
import { validateAmountText } from '@/lib/validateAmount';
import { getVisibleCategories } from '@/lib/categoryVisibility';
import ModalShell from '@/components/ui/ModalShell';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import type { CreateTransactionPayload } from '@/types/api';

interface TransactionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  defaultType?: 'income' | 'expense';
  title?: string;
}

export default function TransactionModal({
  isOpen,
  onClose,
  onSuccess,
  defaultType = 'expense',
  title = 'Registrar movimiento',
}: TransactionModalProps) {
  const queryClient = useQueryClient();

  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');
  const [type, setType] = useState<'income' | 'expense'>(defaultType);
  // Fase 34 F4: la fecha inicial es "hoy" en la zona del usuario. `null` = "sin tocar": se deriva
  // en cada render, así el modal (montado todo el tiempo por `FabManager`) no queda con el "hoy"
  // del dispositivo capturado antes de que cargue `/users/me` ni con el de ayer pasada la
  // medianoche. Se manda el string del `<input type="date">` sin convertir (B9).
  const { displayTimezone } = useTimezone();
  const [dateOverride, setDate] = useState<string | null>(null);
  const date = dateOverride ?? todayInZone(displayTimezone);
  const [accountId, setAccountId] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [showAllCategories, setShowAllCategories] = useState(false);
  // Fase 31 F2 (Q6, QA-013/H13): errores de campo — el modal pasa a `noValidate` (antes
  // dependía de los globos nativos del navegador, a diferencia del resto de la app).
  // Fase 33 F9 (Q7, QA-035): `account` se agrega porque `Number('') === 0` llegaba al backend
  // como `account_id: 0` (404 incomprensible) — el mismo bloque de `EditTransactionModal`.
  const [fieldErrors, setFieldErrors] = useState<{
    amount?: string;
    account?: string;
    category?: string;
  }>({});
  const amountRef = useRef<HTMLInputElement>(null);
  const accountRef = useRef<HTMLSelectElement>(null);
  const categoryRef = useRef<HTMLSelectElement>(null);

  const { data: accounts } = useAccounts({ enabled: isOpen });

  const { data: categories } = useCategories({ enabled: isOpen });

  // Fase 33 F9 (Q7, QA-035, US 24/25): con una sola cuenta el modal la trae elegida (un
  // toque menos); con varias sigue en "Selecciona…" para no registrar en la cuenta
  // equivocada. Las cuentas llegan después del primer render (`enabled: isOpen`), así que el
  // valor se ajusta durante el render con el patrón de `settings/page.tsx`: un `useState` que
  // recuerda el valor previo hace el ajuste una sola vez, sin el `setState` en efecto que
  // marca `react-hooks/set-state-in-effect`.
  const [preselectedAccountId, setPreselectedAccountId] = useState<string | null>(null);
  const onlyAccountId = accounts?.length === 1 ? String(accounts[0].id) : null;
  if (onlyAccountId !== preselectedAccountId) {
    setPreselectedAccountId(onlyAccountId);
    if (onlyAccountId !== null && accountId === '') setAccountId(onlyAccountId);
  }

  // Fase 31 F3 (Q10, QA-009, H13): lo que se ve en el <select> es lo que se envía — regla
  // compartida con EditTransactionModal.
  const displayedCategories = useMemo(
    () => getVisibleCategories(categories, type, showAllCategories),
    [categories, type, showAllCategories]
  );

  const createMutation = useMutation({
    mutationFn: async (newTx: CreateTransactionPayload) => {
      const response = await api.post('transactions/', newTx);
      return response.data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() }),
        queryClient.invalidateQueries({ queryKey: ['analytics-cashflow'] }),
        queryClient.invalidateQueries({ queryKey: ['analytics-categories'] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.categoryBreakdown() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.accounts.summary() }),
      ]);

      toast.success('Transacción creada correctamente');
      onSuccess?.();
      onClose();
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  // Fase 31 F3 (Q10, H13): si al cambiar el tipo o al apagar "ver todas" la categoría
  // elegida deja de estar entre las opciones visibles, se resetea a "Selecciona…" — antes
  // el <select> quedaba con un valor fuera de sus <option> y el navegador mostraba la
  // primera en silencio (se enviaba una categoría distinta a la que se veía).
  const resetCategoryIfNotVisible = (nextType: 'income' | 'expense', nextShowAll: boolean) => {
    const nextVisible = getVisibleCategories(categories, nextType, nextShowAll);
    if (categoryId && !nextVisible.some((c) => String(c.id) === categoryId)) {
      setCategoryId('');
    }
  };

  const handleTypeChange = (newType: 'income' | 'expense') => {
    setType(newType);
    resetCategoryIfNotVisible(newType, showAllCategories);
  };

  const handleToggleShowAll = () => {
    const nextShowAll = !showAllCategories;
    setShowAllCategories(nextShowAll);
    resetCategoryIfNotVisible(type, nextShowAll);
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();

    const errors: typeof fieldErrors = {};
    const amountError = validateAmountText(amount);
    if (amountError) errors.amount = amountError;
    if (!accountId) errors.account = 'Elige una cuenta.';
    if (!categoryId) errors.category = 'Elige una categoría.';
    setFieldErrors(errors);

    if (errors.amount) return amountRef.current?.focus();
    if (errors.account) return accountRef.current?.focus();
    if (errors.category) return categoryRef.current?.focus();

    createMutation.mutate({
      description: description.trim() || null,
      amount: Number(amount),
      type,
      date,
      account_id: Number(accountId),
      category_id: Number(categoryId),
    });
  };

  return (
    <ModalShell isOpen={isOpen} onClose={onClose} title={title}>
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div className="flex gap-4">
          <button
            type="button"
            onClick={() => handleTypeChange('expense')}
            className={`flex-1 cursor-pointer rounded-xl border py-2 text-sm font-medium transition-colors ${
              type === 'expense'
                ? 'bg-background border-border text-text'
                : 'text-text-muted hover:text-text border-transparent'
            }`}
          >
            Gasto
          </button>
          <button
            type="button"
            onClick={() => handleTypeChange('income')}
            className={`flex-1 cursor-pointer rounded-xl border py-2 text-sm font-medium transition-colors ${
              type === 'income'
                ? 'bg-primary/10 border-primary/20 text-primary'
                : 'text-text-muted hover:text-text border-transparent'
            }`}
          >
            Ingreso
          </button>
        </div>

        <Input
          ref={amountRef}
          label="Valor"
          type="number"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          error={fieldErrors.amount}
          className="bg-background"
          placeholder="0"
        />

        <Input
          label="Descripción"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          className="bg-background"
          placeholder="Opcional"
        />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Select
            ref={accountRef}
            label="Cuenta"
            required
            value={accountId}
            onChange={(event) => setAccountId(event.target.value)}
            error={fieldErrors.account}
            className="bg-background"
          >
            <option value="" disabled>
              Selecciona...
            </option>
            {accounts?.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name}
              </option>
            ))}
          </Select>
          <div>
            <Select
              ref={categoryRef}
              label="Categoría"
              value={categoryId}
              onChange={(event) => setCategoryId(event.target.value)}
              error={fieldErrors.category}
              className="bg-background"
            >
              <option value="" disabled>
                Selecciona...
              </option>
              {displayedCategories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                  {showAllCategories
                    ? ` (${category.type === 'income' ? 'Ingreso' : 'Gasto'})`
                    : ''}
                </option>
              ))}
            </Select>
            <button
              type="button"
              onClick={handleToggleShowAll}
              className="text-primary/70 hover:text-primary mt-1 text-xs transition-colors"
            >
              {showAllCategories ? '← Solo del tipo' : '+ Mostrar todas las categorías'}
            </button>
          </div>
        </div>

        <Input
          label="Fecha"
          type="date"
          required
          value={date}
          onChange={(event) => setDate(event.target.value)}
          className="bg-background"
        />

        <div className="mt-6 flex gap-3">
          <Button type="button" variant="ghost" onClick={onClose} className="flex-1">
            Cancelar
          </Button>
          <Button
            type="submit"
            variant="primary"
            loading={createMutation.isPending}
            className="flex-1"
          >
            Guardar
          </Button>
        </div>
      </form>
    </ModalShell>
  );
}
