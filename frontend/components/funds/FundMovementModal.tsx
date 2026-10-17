'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import ModalShell from '@/components/ui/ModalShell';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import { useFundMovement } from '@/lib/hooks/useFunds';
import { formatCurrency, getApiError } from '@/lib/utils';
import { validateAmountText } from '@/lib/validateAmount';
import type { Fund } from '@/types/api';

interface FundMovementModalProps {
  fund: Fund;
  mode: 'contribution' | 'withdrawal';
  onClose: () => void;
}

/** Aportar (monto pre-llenado con el aporte sugerido por el servidor) o retirar (máx. = saldo).
 *  Se monta solo mientras está abierto. */
export default function FundMovementModal({ fund, mode, onClose }: FundMovementModalProps) {
  const isContribution = mode === 'contribution';
  const balance = Number(fund.balance);
  const suggested =
    isContribution && fund.required_contribution !== null && Number(fund.required_contribution) > 0
      ? String(Number(fund.required_contribution))
      : '';

  const mutation = useFundMovement(fund.id, isContribution ? 'contributions' : 'withdrawals');
  const [amount, setAmount] = useState(suggested);
  const [note, setNote] = useState('');
  const [amountError, setAmountError] = useState<string>();
  const [formError, setFormError] = useState<string>();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (mutation.isPending) return;
    setFormError(undefined);

    let error = validateAmountText(amount) ?? undefined;
    if (!error && !isContribution && Number(amount) > balance) {
      error = `El sobre solo tiene ${formatCurrency(balance, fund.currency)} apartado.`;
    }
    setAmountError(error);
    if (error) return;

    mutation.mutate(
      { amount: Number(amount), note: note.trim() || undefined },
      {
        onSuccess: () => {
          toast.success(isContribution ? 'Aporte registrado' : 'Retiro registrado');
          onClose();
        },
        onError: (err) => setFormError(getApiError(err)),
      }
    );
  };

  return (
    <ModalShell
      isOpen
      onClose={onClose}
      title={isContribution ? `Aportar a ${fund.name}` : `Retirar de ${fund.name}`}
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {!isContribution && (
          <p className="text-text-muted text-sm">
            Disponible en el sobre: {formatCurrency(balance, fund.currency)}
          </p>
        )}
        <div>
          <Input
            label={`Monto (${fund.currency})`}
            type="number"
            inputMode="decimal"
            min={0}
            max={isContribution ? undefined : balance}
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            error={amountError}
            className="bg-background"
          />
          {suggested && (
            <p className="text-text-muted mt-1 text-xs">
              Pre-llenado con tu aporte sugerido de este mes.
            </p>
          )}
        </div>
        <Input
          label="Nota (opcional)"
          value={note}
          maxLength={200}
          onChange={(e) => setNote(e.target.value)}
          className="bg-background"
        />
        {formError && (
          <p role="alert" className="text-danger text-sm">
            {formError}
          </p>
        )}
        <div className="mt-6 flex gap-3">
          <Button type="button" variant="ghost" onClick={onClose} className="flex-1">
            Cancelar
          </Button>
          <Button type="submit" loading={mutation.isPending} className="flex-1">
            {isContribution ? 'Aportar' : 'Retirar'}
          </Button>
        </div>
      </form>
    </ModalShell>
  );
}
