'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import ModalShell from '@/components/ui/ModalShell';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import { useCreateCdt, useUpdateCdt } from '@/lib/hooks/useCdts';
import { useTimezone } from '@/lib/hooks/useTimezone';
import { todayInZone } from '@/lib/dates';
import { getApiError } from '@/lib/utils';
import { validateAmountText } from '@/lib/validateAmount';
import type { Cdt, CreateCdtPayload, UpdateCdtPayload } from '@/types/api';

const CURRENCY_OPTIONS = ['COP', 'USD', 'EUR'];

interface CdtFormModalProps {
  /** CDT vigente a editar; sin él el modal crea uno nuevo. */
  cdt?: Cdt;
  onClose: () => void;
}

type Errors = {
  name?: string;
  principal?: string;
  rate?: string;
  opened?: string;
  maturity?: string;
  form?: string;
};

/** Se monta solo mientras está abierto, así el estado arranca siempre desde el CDT actual. */
export default function CdtFormModal({ cdt, onClose }: CdtFormModalProps) {
  const isEdit = cdt !== undefined;
  const { displayTimezone } = useTimezone();
  const today = todayInZone(displayTimezone);

  const createMutation = useCreateCdt();
  const updateMutation = useUpdateCdt(cdt?.id ?? 0);
  const isPending = createMutation.isPending || updateMutation.isPending;

  const [name, setName] = useState(cdt?.name ?? '');
  const [currency, setCurrency] = useState(cdt?.currency ?? 'COP');
  const [principal, setPrincipal] = useState(cdt ? String(Number(cdt.principal)) : '');
  const [rate, setRate] = useState(cdt ? String(Number(cdt.rate_ea)) : '');
  const [openedOn, setOpenedOn] = useState(cdt?.opened_on ?? today);
  const [maturityOn, setMaturityOn] = useState(cdt?.maturity_on ?? '');
  const [errors, setErrors] = useState<Errors>({});

  const currencyOptions = CURRENCY_OPTIONS.includes(currency)
    ? CURRENCY_OPTIONS
    : [currency, ...CURRENCY_OPTIONS];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isPending) return;

    const next: Errors = {};
    const trimmed = name.trim();
    if (!trimmed) next.name = 'Ponle un nombre al CDT.';
    const principalError = validateAmountText(principal);
    if (principalError) next.principal = principalError;
    const rateNumber = Number(rate);
    if (!rate.trim() || !Number.isFinite(rateNumber) || rateNumber <= 0 || rateNumber > 100) {
      next.rate = 'Indica una tasa E.A. mayor que 0 y hasta 100 (ej. 11.5).';
    }
    if (!openedOn) next.opened = 'Indica la fecha de apertura.';
    if (!maturityOn) next.maturity = 'Indica la fecha de vencimiento.';
    else if (openedOn && maturityOn <= openedOn) {
      next.maturity = 'El vencimiento debe ser posterior a la apertura.';
    }
    setErrors(next);
    if (Object.keys(next).length > 0) return;

    const onError = (error: unknown) => setErrors({ form: getApiError(error) });

    if (isEdit) {
      const payload: UpdateCdtPayload = {};
      if (trimmed !== cdt.name) payload.name = trimmed;
      if (currency !== cdt.currency) payload.currency = currency;
      if (Number(principal) !== Number(cdt.principal)) payload.principal = Number(principal);
      if (rateNumber !== Number(cdt.rate_ea)) payload.rate_ea = rateNumber;
      if (openedOn !== cdt.opened_on) payload.opened_on = openedOn;
      if (maturityOn !== cdt.maturity_on) payload.maturity_on = maturityOn;
      if (Object.keys(payload).length === 0) return onClose();
      updateMutation.mutate(payload, {
        onSuccess: () => {
          toast.success('CDT actualizado');
          onClose();
        },
        onError,
      });
      return;
    }

    const payload: CreateCdtPayload = {
      name: trimmed,
      currency,
      principal: Number(principal),
      rate_ea: rateNumber,
      opened_on: openedOn,
      maturity_on: maturityOn,
    };
    createMutation.mutate(payload, {
      onSuccess: () => {
        toast.success('CDT creado');
        onClose();
      },
      onError,
    });
  };

  return (
    <ModalShell isOpen onClose={onClose} title={isEdit ? 'Editar CDT' : 'Nuevo CDT'}>
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <p className="bg-primary/10 text-text rounded-xl p-2.5 text-xs">
          Un CDT no mueve el saldo de tus cuentas. Si el capital sigue en una cuenta, ajusta el
          saldo de esa cuenta para que el dinero no se cuente dos veces en tu patrimonio.
        </p>

        <Input
          label="Nombre"
          value={name}
          maxLength={100}
          onChange={(e) => setName(e.target.value)}
          error={errors.name}
          placeholder="Ej. CDT Bancolombia 12 meses"
          className="bg-background"
        />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Select
            label="Moneda"
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="bg-background"
          >
            {currencyOptions.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
          <Input
            label="Tasa E.A. (%)"
            type="number"
            inputMode="decimal"
            min={0}
            max={100}
            step="0.0001"
            value={rate}
            onChange={(e) => setRate(e.target.value)}
            error={errors.rate}
            placeholder="11.5"
            className="bg-background"
          />
        </div>

        <Input
          label={`Capital (${currency})`}
          type="number"
          inputMode="decimal"
          min={0}
          step="0.01"
          value={principal}
          onChange={(e) => setPrincipal(e.target.value)}
          error={errors.principal}
          className="bg-background"
        />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input
            label="Apertura"
            type="date"
            value={openedOn}
            onChange={(e) => setOpenedOn(e.target.value)}
            error={errors.opened}
            className="bg-background"
          />
          <Input
            label="Vencimiento"
            type="date"
            value={maturityOn}
            onChange={(e) => setMaturityOn(e.target.value)}
            error={errors.maturity}
            className="bg-background"
          />
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
            {isEdit ? 'Guardar' : 'Crear CDT'}
          </Button>
        </div>
      </form>
    </ModalShell>
  );
}
