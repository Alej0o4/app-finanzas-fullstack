'use client';

import { useMemo, useRef, useState } from 'react';
import ModalShell from '@/components/ui/ModalShell';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import { validateAmountText } from '@/lib/validateAmount';
import { getVisibleCategories } from '@/lib/categoryVisibility';
import { dayInZone, todayInZone } from '@/lib/dates';
import { useTimezone } from '@/lib/hooks/useTimezone';
import type { Account, Category, Transaction, UpdateTransactionPayload } from '@/types/api';

interface EditTransactionModalProps {
  isOpen: boolean;
  transaction: Transaction;
  accounts?: Account[];
  categories?: Category[];
  isSaving: boolean;
  onClose: () => void;
  onSave: (payload: UpdateTransactionPayload) => void;
}

export default function EditTransactionModal({
  isOpen,
  transaction,
  accounts,
  categories,
  isSaving,
  onClose,
  onSave,
}: EditTransactionModalProps) {
  const [editDescription, setEditDescription] = useState(transaction.description || '');
  const [editAmount, setEditAmount] = useState(String(transaction.amount));
  const [editType, setEditType] = useState(transaction.type);
  // Fase 34 F4: el campo muestra el día del instante **en la zona del usuario** (`Intl`, nunca
  // `split('T')[0]`, que daría el día UTC). `initialDate` queda fijo para detectar si el usuario
  // cambió la fecha: solo entonces se manda (B9).
  const { displayTimezone } = useTimezone();
  const [initialDate] = useState(
    () =>
      (transaction.date && dayInZone(transaction.date, displayTimezone)) ||
      todayInZone(displayTimezone)
  );
  const [editDate, setEditDate] = useState(initialDate);
  const [editAccountId, setEditAccountId] = useState(String(transaction.account_id));
  const [editCategoryId, setEditCategoryId] = useState(String(transaction.category_id));
  // Fase 31 F3 (Q10, QA-009, H13): el toggle arranca activado si la categoría original de
  // la transacción es de la otra naturaleza que su tipo (un reembolso) — así el selector no
  // arranca en "Selecciona…" perdiendo la categoría real. `categories` puede llegar
  // `undefined` en el primer render; el toggle arranca apagado en ese caso, igual que hoy.
  const [showAllCategories, setShowAllCategories] = useState(() => {
    const originalCategory = categories?.find((c) => c.id === transaction.category_id);
    return originalCategory !== undefined && originalCategory.type !== transaction.type;
  });
  // Fase 12 §12.8.3: errores por campo (no globo nativo del navegador) + foco en el primero.
  const [editErrors, setEditErrors] = useState<{
    amount?: string;
    accountId?: string;
    categoryId?: string;
    date?: string;
  }>({});
  const editAmountRef = useRef<HTMLInputElement>(null);
  const editAccountRef = useRef<HTMLSelectElement>(null);
  const editCategoryRef = useRef<HTMLSelectElement>(null);
  const editDateRef = useRef<HTMLInputElement>(null);

  // Fase 31 F3: lo que se ve en el <select> es lo que se envía — regla compartida con
  // TransactionModal. La categoría original de la transacción (`transaction.category_id`)
  // siempre aparece aunque esté oculta, para no arrancar el selector en blanco.
  const displayedCategories = useMemo(
    () => getVisibleCategories(categories, editType, showAllCategories, transaction.category_id),
    [categories, editType, showAllCategories, transaction.category_id]
  );

  // Fase 31 F3 (H13): si al cambiar el tipo o al apagar el toggle la categoría elegida deja
  // de estar entre las opciones visibles, se resetea a "Selecciona…" — mismo mecanismo que
  // TransactionModal, para que el <select> nunca quede con un valor fuera de sus <option>.
  const resetCategoryIfNotVisible = (nextType: 'income' | 'expense', nextShowAll: boolean) => {
    const nextVisible = getVisibleCategories(
      categories,
      nextType,
      nextShowAll,
      transaction.category_id
    );
    setEditCategoryId((current) =>
      current && !nextVisible.some((c) => String(c.id) === current) ? '' : current
    );
  };

  const handleTypeChange = (newType: 'income' | 'expense') => {
    setEditType(newType);
    resetCategoryIfNotVisible(newType, showAllCategories);
  };

  const handleToggleShowAll = () => {
    const nextShowAll = !showAllCategories;
    setShowAllCategories(nextShowAll);
    resetCategoryIfNotVisible(editType, nextShowAll);
  };

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();

    const errors: typeof editErrors = {};
    const amountError = validateAmountText(editAmount);
    if (amountError) errors.amount = amountError;
    if (!editAccountId) errors.accountId = 'Elige una cuenta.';
    if (!editCategoryId) errors.categoryId = 'Elige una categoría.';
    if (!editDate) errors.date = 'Ingresa una fecha válida.';
    setEditErrors(errors);

    if (errors.amount) return editAmountRef.current?.focus();
    if (errors.accountId) return editAccountRef.current?.focus();
    if (errors.categoryId) return editCategoryRef.current?.focus();
    if (errors.date) return editDateRef.current?.focus();

    onSave({
      id: transaction.id,
      description: editDescription.trim() || null,
      amount: Number(editAmount),
      type: editType as 'income' | 'expense',
      date: editDate !== initialDate ? editDate : undefined,
      account_id: Number(editAccountId),
      category_id: Number(editCategoryId),
    });
  };

  return (
    <ModalShell isOpen={isOpen} onClose={onClose} title="Editar movimiento">
      <form onSubmit={handleUpdate} className="space-y-4" noValidate>
        <div className="flex gap-4">
          <button
            type="button"
            onClick={() => handleTypeChange('expense')}
            className={`flex-1 cursor-pointer rounded-xl border py-2 text-sm font-medium transition-colors ${editType === 'expense' ? 'bg-background border-border text-text' : 'text-text-muted hover:text-text border-transparent'}`}
          >
            Gasto
          </button>
          <button
            type="button"
            onClick={() => handleTypeChange('income')}
            className={`flex-1 cursor-pointer rounded-xl border py-2 text-sm font-medium transition-colors ${editType === 'income' ? 'bg-primary/10 border-primary/20 text-primary' : 'text-text-muted hover:text-text border-transparent'}`}
          >
            Ingreso
          </button>
        </div>

        <Input
          ref={editAmountRef}
          label="Valor"
          type="number"
          required
          value={editAmount}
          onChange={(e) => setEditAmount(e.target.value)}
          error={editErrors.amount}
          className="bg-background"
        />

        <Input
          label="Descripción"
          type="text"
          value={editDescription}
          onChange={(e) => setEditDescription(e.target.value)}
          className="bg-background"
          placeholder="Opcional"
        />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Select
            ref={editAccountRef}
            label="Cuenta"
            required
            value={editAccountId}
            onChange={(e) => setEditAccountId(e.target.value)}
            error={editErrors.accountId}
            className="bg-background appearance-none"
          >
            <option value="" disabled>
              Selecciona...
            </option>
            {accounts?.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </Select>
          <div>
            <Select
              ref={editCategoryRef}
              label="Categoría"
              required
              value={editCategoryId}
              onChange={(e) => setEditCategoryId(e.target.value)}
              error={editErrors.categoryId}
              className="bg-background appearance-none"
            >
              <option value="" disabled>
                Selecciona...
              </option>
              {displayedCategories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                  {showAllCategories ? ` (${c.type === 'income' ? 'Ingreso' : 'Gasto'})` : ''}
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
          ref={editDateRef}
          label="Fecha"
          type="date"
          required
          value={editDate}
          onChange={(e) => setEditDate(e.target.value)}
          error={editErrors.date}
          className="bg-background"
        />

        <div className="mt-6 flex gap-3">
          <Button type="button" variant="ghost" onClick={onClose} className="flex-1">
            Cancelar
          </Button>
          <Button type="submit" variant="primary" loading={isSaving} className="flex-1">
            Guardar
          </Button>
        </div>
      </form>
    </ModalShell>
  );
}
