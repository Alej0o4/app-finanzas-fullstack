'use client';

import { X } from 'lucide-react';
import { useId, useRef, type ReactNode } from 'react';
import { useDialogCounter } from '@/lib/hooks/useDialogCounter';
import { useDialogFocus } from '@/lib/hooks/useDialogFocus';

interface ModalShellProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}

export default function ModalShell({ isOpen, onClose, title, children }: ModalShellProps) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);

  // Fase 33 F6 (QA-034): el banner de instalación no se renderiza con un modal abierto.
  useDialogCounter(isOpen);

  // QA-014: foco inicial, trampa de foco, restauración al cerrar y Escape.
  useDialogFocus({ isOpen, dialogRef, onClose });

  if (!isOpen) return null;

  return (
    <div className="bg-background/80 fixed inset-0 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="border-border bg-surface animate-fade-in shadow-background/40 max-h-[90vh] w-full max-w-lg overflow-y-auto overscroll-contain rounded-2xl border p-4 shadow-2xl outline-none sm:p-6"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 id={titleId} className="text-text text-lg font-semibold">
            {title}
          </h2>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text hover:bg-surface-elevated cursor-pointer rounded-lg p-1.5 transition-colors active:scale-95"
            aria-label="Cerrar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
