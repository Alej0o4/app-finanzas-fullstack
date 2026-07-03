"use client";

import { useConfirmStore } from "@/store/useConfirmStore";

export default function ConfirmDialog() {
  const { isOpen, message, onConfirm, cancel } = useConfirmStore();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-surface border border-border/70 rounded-2xl p-6 shadow-2xl max-w-sm w-full mx-4">
        <p className="text-sm text-text font-medium">{message}</p>
        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={cancel}
            className="px-4 py-2 rounded-xl text-sm font-medium text-text-muted hover:text-text hover:bg-surface-elevated transition-colors cursor-pointer"
          >
            Cancelar
          </button>
          <button
            onClick={() => {
              onConfirm?.();
              cancel();
            }}
            className="px-4 py-2 rounded-xl text-sm font-semibold bg-danger text-white hover:bg-danger/90 transition-colors cursor-pointer"
          >
            Eliminar
          </button>
        </div>
      </div>
    </div>
  );
}
