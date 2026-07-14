'use client';

import { useConfirmStore } from '@/store/useConfirmStore';
import Button from '@/components/ui/Button';

export default function ConfirmDialog() {
  const { isOpen, message, onConfirm, cancel } = useConfirmStore();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-surface border-border/70 mx-4 w-full max-w-sm rounded-2xl border p-6 shadow-2xl">
        <p className="text-text text-sm font-medium">{message}</p>
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button variant="ghost" onClick={cancel}>
            Cancelar
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              onConfirm?.();
              cancel();
            }}
          >
            Eliminar
          </Button>
        </div>
      </div>
    </div>
  );
}
