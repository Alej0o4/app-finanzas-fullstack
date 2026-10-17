'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import ModalShell from '@/components/ui/ModalShell';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import { KIND_LABELS } from '@/components/funds/fundPresentation';
import { useCreateFund, useUpdateFund } from '@/lib/hooks/useFunds';
import { useTimezone } from '@/lib/hooks/useTimezone';
import { todayInZone } from '@/lib/dates';
import { getApiError } from '@/lib/utils';
import { validateAmountText } from '@/lib/validateAmount';
import type { Account, CreateFundPayload, Fund, FundKind, UpdateFundPayload } from '@/types/api';

interface FundFormModalProps {
  /** Sobre a editar; sin él, el modal crea uno nuevo. */
  fund?: Fund;
  accounts: Account[];
  onClose: () => void;
  onCreated?: (fund: Fund) => void;
}

type GoalMode = 'amount' | 'months';

/** Se monta solo mientras está abierto (`{open && <FundFormModal/>}`), así el estado del
 *  formulario siempre arranca desde el sobre actual. */
export default function FundFormModal({ fund, accounts, onClose, onCreated }: FundFormModalProps) {
  const isEdit = fund !== undefined;
  const { displayTimezone } = useTimezone();
  const today = todayInZone(displayTimezone);

  const createMutation = useCreateFund();
  const updateMutation = useUpdateFund(fund?.id ?? 0);
  const isPending = createMutation.isPending || updateMutation.isPending;

  const [name, setName] = useState(fund?.name ?? '');
  const [kind, setKind] = useState<FundKind>(fund?.kind ?? 'goal');
  const [accountId, setAccountId] = useState(fund ? String(fund.account_id) : '');
  const [goalMode, setGoalMode] = useState<GoalMode>(
    fund?.kind === 'emergency' && fund.target_months !== null ? 'months' : 'amount'
  );
  const [targetAmount, setTargetAmount] = useState(
    fund && fund.target_months === null && fund.target_amount !== null
      ? String(Number(fund.target_amount))
      : ''
  );
  const [targetMonths, setTargetMonths] = useState(
    fund?.target_months ? String(fund.target_months) : '6'
  );
  const [targetDate, setTargetDate] = useState(fund?.target_date ?? '');
  const [errors, setErrors] = useState<{
    name?: string;
    account?: string;
    amount?: string;
    months?: string;
    date?: string;
    form?: string;
  }>({});

  const usesMonths = kind === 'emergency' && goalMode === 'months';
  // La moneda del sobre es la de su cuenta y no se elige; al editar solo caben cuentas de la
  // misma moneda (el backend responde 422 si no).
  const selectableAccounts = isEdit
    ? accounts.filter((a) => a.currency === fund.currency)
    : accounts;
  const selectedAccount = accounts.find((a) => String(a.id) === accountId);
  const currency = isEdit ? fund.currency : selectedAccount?.currency;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isPending) return;

    const next: typeof errors = {};
    const trimmed = name.trim();
    if (!trimmed) next.name = 'Ponle un nombre al sobre.';
    if (!accountId) next.account = 'Elige la cuenta de donde sale el dinero.';
    if (usesMonths) {
      const m = Number(targetMonths);
      if (!Number.isInteger(m) || m < 1 || m > 60) next.months = 'Ingresa de 1 a 60 meses.';
    } else {
      const amountError = validateAmountText(targetAmount);
      if (amountError) next.amount = amountError;
    }
    // El backend solo valida la fecha cuando se envía; al editar un sobre vencido sin tocarla
    // no se manda, así que solo se exige "hoy o después" si cambió.
    const dateChanged = targetDate !== (fund?.target_date ?? '');
    if (targetDate && dateChanged && targetDate < today) {
      next.date = 'La fecha debe ser hoy o posterior.';
    }
    setErrors(next);
    if (Object.keys(next).length > 0) return;

    const onError = (error: unknown) => setErrors({ form: getApiError(error) });

    if (isEdit) {
      const payload: UpdateFundPayload = {};
      if (trimmed !== fund.name) payload.name = trimmed;
      if (Number(accountId) !== fund.account_id) payload.account_id = Number(accountId);
      if (usesMonths) {
        if (Number(targetMonths) !== fund.target_months)
          payload.target_months = Number(targetMonths);
      } else if (
        fund.target_months !== null ||
        Number(targetAmount) !== Number(fund.target_amount)
      ) {
        payload.target_amount = Number(targetAmount);
      }
      if (dateChanged) payload.target_date = targetDate || null;
      if (Object.keys(payload).length === 0) return onClose();
      updateMutation.mutate(payload, {
        onSuccess: () => {
          toast.success('Sobre actualizado');
          onClose();
        },
        onError,
      });
      return;
    }

    const payload: CreateFundPayload = { name: trimmed, kind, account_id: Number(accountId) };
    if (usesMonths) payload.target_months = Number(targetMonths);
    else payload.target_amount = Number(targetAmount);
    if (targetDate) payload.target_date = targetDate;
    createMutation.mutate(payload, {
      onSuccess: (created) => {
        toast.success('Sobre creado');
        onClose();
        onCreated?.(created);
      },
      onError,
    });
  };

  return (
    <ModalShell isOpen onClose={onClose} title={isEdit ? 'Editar sobre' : 'Nuevo sobre'}>
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <Input
          label="Nombre"
          value={name}
          maxLength={100}
          onChange={(e) => setName(e.target.value)}
          error={errors.name}
          placeholder="Ej. SOAT, Viaje, Emergencias"
          className="bg-background"
        />

        {isEdit ? (
          <p className="text-text-muted text-sm">Tipo: {KIND_LABELS[fund.kind]}</p>
        ) : (
          <Select
            label="Tipo"
            value={kind}
            onChange={(e) => {
              setKind(e.target.value as FundKind);
              setGoalMode('amount');
            }}
            className="bg-background"
          >
            {(Object.keys(KIND_LABELS) as FundKind[]).map((k) => (
              <option key={k} value={k}>
                {KIND_LABELS[k]}
              </option>
            ))}
          </Select>
        )}

        <div>
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
            {selectableAccounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.currency})
              </option>
            ))}
          </Select>
          {currency && <p className="text-text-muted mt-1 text-xs">Moneda del sobre: {currency}</p>}
        </div>

        {kind === 'emergency' && (
          <Select
            label="¿Cómo defines la meta?"
            value={goalMode}
            onChange={(e) => setGoalMode(e.target.value as GoalMode)}
            className="bg-background"
          >
            <option value="months">Meses de gasto</option>
            <option value="amount">Monto fijo</option>
          </Select>
        )}

        {usesMonths ? (
          <Input
            label="Meses de gasto a cubrir"
            type="number"
            inputMode="numeric"
            min={1}
            max={60}
            step={1}
            value={targetMonths}
            onChange={(e) => setTargetMonths(e.target.value)}
            error={errors.months}
            className="bg-background"
          />
        ) : (
          <Input
            label="Meta"
            type="number"
            inputMode="decimal"
            min={0}
            step="0.01"
            value={targetAmount}
            onChange={(e) => setTargetAmount(e.target.value)}
            error={errors.amount}
            className="bg-background"
          />
        )}

        <div>
          <Input
            label="Fecha objetivo (opcional)"
            type="date"
            value={targetDate}
            min={isEdit ? undefined : today}
            onChange={(e) => setTargetDate(e.target.value)}
            error={errors.date}
            className="bg-background"
          />
          {targetDate && (
            <button
              type="button"
              onClick={() => setTargetDate('')}
              className="text-primary/70 hover:text-primary mt-1 text-xs transition-colors"
            >
              Quitar fecha
            </button>
          )}
        </div>

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
            {isEdit ? 'Guardar' : 'Crear sobre'}
          </Button>
        </div>
      </form>
    </ModalShell>
  );
}
