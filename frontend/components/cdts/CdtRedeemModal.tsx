'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import ModalShell from '@/components/ui/ModalShell';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import { useAccounts } from '@/lib/hooks/useAccounts';
import Select from '@/components/ui/Select';
import { useRedeemCdt } from '@/lib/hooks/useCdts';
import { useTimezone } from '@/lib/hooks/useTimezone';
import { todayInZone } from '@/lib/dates';
import { getApiError } from '@/lib/utils';
import type { Cdt, RedeemCdtPayload } from '@/types/api';

interface CdtRedeemModalProps {
  cdt: Cdt;
  onClose: () => void;
}

/** Solo se redime desde el vencimiento (el servidor responde 422 antes). Redimir solo cambia el estado y guarda el monto final (D4): no crea transacción ni mueve
 *  saldos. El monto queda vacío por defecto y el servidor usa capital + interés a la fecha. */
export default function CdtRedeemModal({ cdt, onClose }: CdtRedeemModalProps) {
  const { displayTimezone } = useTimezone();
  const today = todayInZone(displayTimezone);
  const mutation = useRedeemCdt(cdt.id);

  const [redeemedOn, setRedeemedOn] = useState(today);
  const [finalAmount, setFinalAmount] = useState('');
  const [accountId, setAccountId] = useState('');
  const { data: accounts } = useAccounts();
  const accountOptions = accounts?.filter((a) => a.currency === cdt.currency) ?? [];
  const [errors, setErrors] = useState<{ date?: string; amount?: string; form?: string }>({});

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (mutation.isPending) return;

    const next: typeof errors = {};
    if (!redeemedOn) next.date = 'Indica la fecha de redención.';
    else if (redeemedOn < cdt.maturity_on) next.date = 'No puede ser anterior al vencimiento.';
    else if (redeemedOn > today) next.date = 'No puede ser una fecha futura.';
    const hasAmount = finalAmount.trim() !== '';
    if (hasAmount && (!Number.isFinite(Number(finalAmount)) || Number(finalAmount) < 0)) {
      next.amount = 'Ingresa un monto válido (0 o más).';
    }
    setErrors(next);
    if (Object.keys(next).length > 0) return;

    const payload: RedeemCdtPayload = { redeemed_on: redeemedOn };
    if (hasAmount) payload.final_amount = Number(finalAmount);
    if (accountId) payload.account_id = Number(accountId);
    mutation.mutate(payload, {
      onSuccess: () => {
        toast.success('CDT redimido');
        onClose();
      },
      onError: (error) => setErrors({ form: getApiError(error) }),
    });
  };

  return (
    <ModalShell isOpen onClose={onClose} title={`Redimir ${cdt.name}`}>
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <p className="bg-primary/10 text-text rounded-xl p-2.5 text-xs">
          Redimir marca el CDT como cerrado y guarda cuánto recibiste. Si eliges una cuenta de
          destino, el dinero entra a ella como una transferencia; si recibiste más que el capital,
          la diferencia se registra como ingreso en la categoría Rendimientos.
        </p>

        <Input
          label="Fecha de redención"
          type="date"
          value={redeemedOn}
          min={cdt.maturity_on}
          max={today}
          onChange={(e) => setRedeemedOn(e.target.value)}
          error={errors.date}
          className="bg-background"
        />

        <div>
          <Input
            label={`Monto recibido (${cdt.currency}), opcional`}
            type="number"
            inputMode="decimal"
            min={0}
            step="0.01"
            value={finalAmount}
            onChange={(e) => setFinalAmount(e.target.value)}
            error={errors.amount}
            placeholder="Se calcula a la fecha de redención"
            className="bg-background"
          />
          <p className="text-text-muted mt-1 text-xs">
            Si lo dejas vacío, se usa capital + rendimiento a la fecha de redención. Pon lo que el
            banco te pagó de verdad (ya neto de retención).
          </p>
        </div>

        <div>
          <Select
            label="Cuenta de destino (opcional)"
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            className="bg-background"
          >
            <option value="">Ninguna (no mover saldos)</option>
            {accountOptions.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.currency})
              </option>
            ))}
          </Select>
          <p className="text-text-muted mt-1 text-xs">
            Solo cuentas en {cdt.currency}. Con cuenta de destino, el monto recibido no puede ser
            menor al capital.
          </p>
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
          <Button type="submit" loading={mutation.isPending} className="flex-1">
            Redimir
          </Button>
        </div>
      </form>
    </ModalShell>
  );
}
