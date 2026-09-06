import { create } from 'zustand';

interface ConfirmState {
  isOpen: boolean;
  message: string;
  /** Etiqueta del botón de confirmación. Default: "Eliminar" (retrocompatible). */
  confirmLabel?: string;
  onConfirm: (() => void) | null;
  confirm: (message: string, onConfirm: () => void, confirmLabel?: string) => void;
  cancel: () => void;
}

export const useConfirmStore = create<ConfirmState>((set) => ({
  isOpen: false,
  message: '',
  confirmLabel: undefined,
  onConfirm: null,
  confirm: (message, onConfirm, confirmLabel) =>
    set({ isOpen: true, message, onConfirm, confirmLabel }),
  cancel: () => set({ isOpen: false, message: '', confirmLabel: undefined, onConfirm: null }),
}));
