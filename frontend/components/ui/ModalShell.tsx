'use client';

import { X } from 'lucide-react';
import type { ReactNode } from 'react';

interface ModalShellProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}

export default function ModalShell({ isOpen, onClose, title, children }: ModalShellProps) {
  if (!isOpen) return null;

  return (
    <div className="bg-background/80 fixed inset-0 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
      <div className="border-border bg-surface animate-in fade-in max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border p-4 shadow-2xl duration-200 sm:p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-text text-lg font-semibold">{title}</h2>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text hover:bg-surface-elevated cursor-pointer rounded-lg p-1.5 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
