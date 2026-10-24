'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import ModalShell from '@/components/ui/ModalShell';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import { useAccounts } from '@/lib/hooks/useAccounts';
import { useCreateTransfer, useUpdateTransfer } from '@/lib/hooks/useTransfers';
import { useTimezone } from '@/lib/hooks/useTimezone';
import { dayInZone, todayInZone } from '@/lib/dates';
import { getApiError, formatCurrency } from '@/lib/utils';
import { validateAmountText } from '@/lib/validateAmount';
import { transferWarningText } from '@/lib/transferWarnings';
import type { Transfer, TransferPayload } from '@/types/api';

interface TransferModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Transferencia cuenta↔cuenta a editar; sin ella el modal crea una nueva. */
  transfer?: Transfer;
}

type Errors = {
  from?: string;
  to?: string;
  amountOut?: string;
  amountIn?: string;
  rate?: string;
  form?: string;
};

/**
 * Modal "Transferir" (Fase 39, F1): mueve dinero entre dos cuentas propias. Una transferencia no
 * es gasto ni ingreso. La tasa implícita y los avisos vienen de la respuesta del backend; aquí no
 * se calcula nada. Los CDT se manejan desde su propio formulario (desviación consciente de F1).
 * Al editar, montarlo con `key` para que el formulario arranque desde la transferencia actual.
 */
export default function TransferModal({ isOpen, onClose, transfer }: TransferModalProps) {
  const isEdit = transfer !== undefined;
  const { displayTimezone } = useTimezone();
  const { data: accounts, isError: accountsError } = useAccounts({ enabled: isOpen });
  const createMutation = useCreateTransfer();
  const updateMutation = useUpdateTransfer(transfer?.id ?? 0);
  const isPending = createMutation.isPending || updateMutation.isPending;

  const [fromId, setFromId] = useState(transfer ? String(transfer.from_account_id) : '');
  const [toId, setToId] = useState(transfer ? String(transfer.to_account_id) : '');
  const [amountOut, setAmountOut] = useState(transfer ? String(Number(transfer.amount_out)) : '');
  const [amountIn, setAmountIn] = useState(transfer ? String(Number(transfer.amount_in)) : '');
  const [rate, setRate] = useState('');
  const [mode, setMode] = useState<'amount' | 'rate'>('amount');
  const [dateOverride, setDate] = useState<string | null>(
    transfer ? dayInZone(transfer.date, displayTimezone) : null
  );
  const date = dateOverride ?? todayInZone(displayTimezone);
  const [description, setDescription] = useState(transfer?.description ?? '');
  const [errors, setErrors] = useState<Errors>({});

  const from = accounts?.find((a) => String(a.id) === fromId);
  const to = accounts?.find((a) => String(a.id) === toId);
  const crossCurrency = Boolean(from && to && from.currency !== to.currency);
  // La tasa solo existe para pares con COP (la define el backend); sin COP se exige monto de entrada.
  const rateAllowed = crossCurrency && (from?.currency === 'COP' || to?.currency === 'COP');
  const foreign = from?.currency === 'COP' ? to?.currency : from?.currency;
  const effectiveMode = rateAllowed ? mode : 'amount';

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isPending) return;

    const next: Errors = {};
    if (!fromId) next.from = 'Elige la cuenta de origen.';
    if (!toId) next.to = 'Elige la cuenta de destino.';
    else if (fromId === toId) next.to = 'El destino debe ser una cuenta distinta del origen.';
    const outError = validateAmountText(amountOut);
    if (outError) next.amountOut = outError;
    if (crossCurrency) {
      if (effectiveMode === 'amount') {
        const inError = validateAmountText(amountIn);
        if (inError) next.amountIn = inError;
      } else if (!rate.trim() || !Number.isFinite(Number(rate)) || Number(rate) <= 0) {
        next.rate = 'Ingresa una tasa mayor a cero.';
      }
    }
    setErrors(next);
    if (Object.keys(next).length > 0) return;

    const payload: TransferPayload = {
      from_account_id: Number(fromId),
      to_account_id: Number(toId),
      amount_out: Number(amountOut),
      description: description.trim() || null,
    };
    // Al editar sin tocar el día se omite `date`: el backend conserva la fecha/hora original.
    if (!isEdit || date !== dayInZone(transfer.date, displayTimezone)) payload.date = date;
    if (crossCurrency) {
      if (effectiveMode === 'amount') payload.amount_in = Number(amountIn);
      else payload.exchange_rate = Number(rate);
    }

    const onSuccess = (saved: Transfer) => {
      const rateLine =
        saved.exchange_rate != null
          ? `Tasa implícita: ${formatCurrency(Number(saved.exchange_rate), 'COP')} por 1 ${
              saved.currency_out === 'COP' ? saved.currency_in : saved.currency_out
            }`
          : undefined;
      toast.success(isEdit ? 'Transferencia actualizada' : 'Transferencia registrada', {
        description: rateLine,
      });
      for (const warning of saved.warnings ?? []) {
        toast.warning('Quedaste por debajo de lo comprometido', {
          description: transferWarningText(warning, accounts),
          duration: 8000,
        });
      }
      onClose();
    };
    const onError = (error: unknown) => setErrors({ form: getApiError(error) });

    if (isEdit) updateMutation.mutate(payload, { onSuccess, onError });
    else createMutation.mutate(payload, { onSuccess, onError });
  };

  return (
    <ModalShell
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Editar transferencia' : 'Transferir'}
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <p className="bg-primary/10 text-text rounded-xl p-2.5 text-xs">
          Una transferencia mueve dinero entre tus cuentas. No cuenta como gasto ni ingreso.
        </p>

        {accountsError && (
          <p role="alert" className="text-danger text-sm">
            No se pudieron cargar tus cuentas. Cierra e intenta de nuevo.
          </p>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Select
            label="Desde"
            value={fromId}
            onChange={(e) => setFromId(e.target.value)}
            error={errors.from}
            className="bg-background"
          >
            <option value="" disabled>
              Selecciona...
            </option>
            {accounts?.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.currency})
              </option>
            ))}
          </Select>
          <Select
            label="Hacia"
            value={toId}
            onChange={(e) => setToId(e.target.value)}
            error={errors.to}
            className="bg-background"
          >
            <option value="" disabled>
              Selecciona...
            </option>
            {accounts?.map((a) => (
              <option key={a.id} value={a.id} disabled={String(a.id) === fromId}>
                {a.name} ({a.currency})
              </option>
            ))}
          </Select>
        </div>

        <Input
          label={`Monto que sale${from ? ` (${from.currency})` : ''}`}
          type="number"
          inputMode="decimal"
          min={0}
          step="0.01"
          value={amountOut}
          onChange={(e) => setAmountOut(e.target.value)}
          error={errors.amountOut}
          className="bg-background"
          placeholder="0"
        />

        {crossCurrency && (
          <div className="space-y-2">
            {rateAllowed && (
              <div className="flex gap-2" role="group" aria-label="Cómo indicar la conversión">
                {(
                  [
                    ['amount', 'Indicar monto recibido'],
                    ['rate', 'Indicar tasa'],
                  ] as const
                ).map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    aria-pressed={effectiveMode === key}
                    onClick={() => setMode(key)}
                    className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
                      effectiveMode === key
                        ? 'border-primary bg-primary/10 text-text'
                        : 'border-border/70 bg-background text-text-muted hover:text-text'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
            {effectiveMode === 'amount' ? (
              <Input
                label={`Monto que entra${to ? ` (${to.currency})` : ''}`}
                type="number"
                inputMode="decimal"
                min={0}
                step="0.01"
                value={amountIn}
                onChange={(e) => setAmountIn(e.target.value)}
                error={errors.amountIn}
                className="bg-background"
                placeholder="0"
              />
            ) : (
              <Input
                label={`Tasa (COP por 1 ${foreign})`}
                type="number"
                inputMode="decimal"
                min={0}
                step="0.0001"
                value={rate}
                onChange={(e) => setRate(e.target.value)}
                error={errors.rate}
                className="bg-background"
                placeholder="4000"
              />
            )}
            <p className="text-text-muted text-xs">
              Las monedas son distintas: el monto que entra o la tasa definen la conversión. Al
              guardar verás la tasa implícita calculada.
            </p>
          </div>
        )}

        <Input
          label="Fecha"
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="bg-background"
        />

        <Input
          label="Descripción"
          value={description}
          maxLength={255}
          onChange={(e) => setDescription(e.target.value)}
          className="bg-background"
          placeholder="Opcional"
        />

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
            {isEdit ? 'Guardar' : 'Transferir'}
          </Button>
        </div>
      </form>
    </ModalShell>
  );
}
