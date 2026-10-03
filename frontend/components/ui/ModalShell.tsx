'use client';

import { X } from 'lucide-react';
import { useEffect, useId, useRef, type ReactNode } from 'react';
import { useEscapeToClose } from '@/lib/hooks/useEscapeToClose';

interface ModalShellProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function ModalShell({ isOpen, onClose, title, children }: ModalShellProps) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  // El elemento que abrió el modal: se rastrea con `focusin` mientras el foco está FUERA del
  // diálogo. No se puede leer `document.activeElement` al abrir porque un hijo con `autoFocus`
  // ya movió el foco para cuando corre el effect.
  useEffect(() => {
    const track = (e: FocusEvent) => {
      const target = e.target as HTMLElement | null;
      // `closest` y no `dialogRef.contains`: el `autoFocus` de un hijo puede dispararse antes de que
      // el ref del diálogo esté asignado.
      if (target && !target.closest('[role="dialog"]')) previouslyFocusedRef.current = target;
    };
    document.addEventListener('focusin', track);
    return () => document.removeEventListener('focusin', track);
  }, []);

  useEscapeToClose(isOpen, onClose);

  // QA-014: foco inicial, trampa de foco y restauración al cerrar.
  useEffect(() => {
    if (!isOpen) return;
    const dialog = dialogRef.current;
    if (!dialog) return;

    // Respeta un `autoFocus` de los hijos (ya aplicado al montar); si no hay, enfoca el primer
    // campo del contenido (no el botón "Cerrar") o, en su defecto, el propio diálogo.
    if (!dialog.contains(document.activeElement)) {
      const firstField = dialog.querySelector<HTMLElement>(
        'input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled])'
      );
      (firstField ?? dialog).focus();
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;
      const focusables = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (focusables.length === 0) {
        e.preventDefault();
        dialog.focus();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || active === dialog)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      } else if (!dialog.contains(active)) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      const previouslyFocused = previouslyFocusedRef.current;
      if (previouslyFocused?.isConnected) previouslyFocused.focus();
    };
  }, [isOpen]);

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
