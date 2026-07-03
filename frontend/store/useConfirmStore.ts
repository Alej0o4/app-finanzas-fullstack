import { create } from 'zustand';

interface ConfirmState {
  isOpen: boolean;
  message: string;
  onConfirm: (() => void) | null;
  confirm: (message: string, onConfirm: () => void) => void;
  cancel: () => void;
}

export const useConfirmStore = create<ConfirmState>((set) => ({
  isOpen: false,
  message: '',
  onConfirm: null,
  confirm: (message, onConfirm) => set({ isOpen: true, message, onConfirm }),
  cancel: () => set({ isOpen: false, message: '', onConfirm: null }),
}));
