'use client';

import { useState } from 'react';
import ModalShell from '@/components/ui/ModalShell';
import TransactionCaptureForm from '@/components/forms/TransactionCaptureForm';

interface QuickTransactionModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultType?: 'income' | 'expense';
}

export default function QuickTransactionModal({
  isOpen,
  onClose,
  defaultType = 'expense',
}: QuickTransactionModalProps) {
  const [type, setType] = useState<'income' | 'expense'>(defaultType);

  return (
    <ModalShell
      isOpen={isOpen}
      onClose={onClose}
      title={type === 'expense' ? 'Gasto rápido' : 'Ingreso rápido'}
    >
      {isOpen && (
        <TransactionCaptureForm
          onSuccess={onClose}
          defaultType={defaultType}
          onTypeChange={setType}
        />
      )}
    </ModalShell>
  );
}
