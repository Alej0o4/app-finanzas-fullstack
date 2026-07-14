'use client';

import { useConfirmStore } from '@/store/useConfirmStore';

export default function ConfirmDialog() {
  const { isOpen, message, onConfirm, cancel } = useConfirmStore();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-surface border-border/70 mx-4 w-full max-w-sm rounded-2xl border p-6 shadow-2xl">
        <p className="text-text text-sm font-medium">{message}</p>
        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={cancel}
            className="text-text-muted hover:text-text hover:bg-surface-elevated cursor-pointer rounded-xl px-4 py-2 text-sm font-medium transition-colors"
          >
            Cancelar
          </button>
          <button
            onClick={() => {
              onConfirm?.();
              cancel();
            }}
            className="bg-danger hover:bg-danger/90 cursor-pointer rounded-xl px-4 py-2 text-sm font-semibold text-white transition-colors"
          >
            Eliminar
          </button>
        </div>
      </div>
    </div>
  );
}
