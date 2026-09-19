'use client';

import { useRef, useState } from 'react';
import ModalShell from '@/components/ui/ModalShell';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
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
  const [editDate, setEditDate] = useState(
    transaction.date ? transaction.date.split('T')[0] : new Date().toISOString().split('T')[0]
  );
  const [editAccountId, setEditAccountId] = useState(String(transaction.account_id));
  const [editCategoryId, setEditCategoryId] = useState(String(transaction.category_id));
  // Fase 12 §12.8.3: errores por campo (no globo nativo del navegador) + foco en el primero.
  const [editErrors, setEditErrors] = useState<{
    amount?: string;
    description?: string;
    accountId?: string;
    categoryId?: string;
    date?: string;
  }>({});
  const editAmountRef = useRef<HTMLInputElement>(null);
  const editDescriptionRef = useRef<HTMLInputElement>(null);
  const editAccountRef = useRef<HTMLSelectElement>(null);
  const editCategoryRef = useRef<HTMLSelectElement>(null);
  const editDateRef = useRef<HTMLInputElement>(null);

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();

    const errors: typeof editErrors = {};
    const parsedAmount = Number(editAmount);
    if (!editAmount || Number.isNaN(parsedAmount) || parsedAmount <= 0) {
      errors.amount = 'Ingresa un monto mayor a cero.';
    }
    if (!editDescription.trim()) errors.description = 'Ingresa una descripción.';
    if (!editAccountId) errors.accountId = 'Elige una cuenta.';
    if (!editCategoryId) errors.categoryId = 'Elige una categoría.';
    if (!editDate) errors.date = 'Ingresa una fecha válida.';
    setEditErrors(errors);

    if (errors.amount) return editAmountRef.current?.focus();
    if (errors.description) return editDescriptionRef.current?.focus();
    if (errors.accountId) return editAccountRef.current?.focus();
    if (errors.categoryId) return editCategoryRef.current?.focus();
    if (errors.date) return editDateRef.current?.focus();

    onSave({
      id: transaction.id,
      description: editDescription,
      amount: parsedAmount,
      type: editType as 'income' | 'expense',
      date: editDate,
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
            onClick={() => setEditType('expense')}
            className={`flex-1 cursor-pointer rounded-xl border py-2 text-sm font-medium transition-colors ${editType === 'expense' ? 'bg-background border-border text-text' : 'text-text-muted hover:text-text border-transparent'}`}
          >
            Gasto
          </button>
          <button
            type="button"
            onClick={() => setEditType('income')}
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
          ref={editDescriptionRef}
          label="Descripción"
          type="text"
          required
          value={editDescription}
          onChange={(e) => setEditDescription(e.target.value)}
          error={editErrors.description}
          className="bg-background"
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
            {categories
              ?.filter((c) => c.type === editType)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
          </Select>
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
