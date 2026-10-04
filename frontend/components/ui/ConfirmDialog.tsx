'use client';

import { useId, useRef } from 'react';
import { useDialogCounter } from '@/lib/hooks/useDialogCounter';
import { useDialogFocus } from '@/lib/hooks/useDialogFocus';
import { useConfirmStore } from '@/store/useConfirmStore';
import Button from '@/components/ui/Button';

export default function ConfirmDialog() {
  const { isOpen, message, confirmLabel, onConfirm, cancel } = useConfirmStore();
  const messageId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  useDialogCounter(isOpen);

  // Fase 33 F8 (QA-039): mismo estándar de accesibilidad que `ModalShell` (QA-014), con el
  // foco inicial en "Cancelar" — la opción segura, para no borrar al pulsar Enter. El
  // mensaje va como `aria-describedby` (descripción), no como título: el confirm no tiene
  // encabezado propio.
  useDialogFocus({ isOpen, dialogRef, onClose: cancel, initialFocusRef: cancelRef });

  if (!isOpen) return null;

  return (
    // `z-[60]` y no `z-50` como los overlays de `ModalShell`: este dialog vive en el layout,
    // antes de `{children}`, así que con igual z-index cualquier modal de una página se
    // pintaría encima (hoy no hay ninguno que se abra junto a un confirm, pero el orden del
    // DOM no lo garantiza).
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-describedby={messageId}
        tabIndex={-1}
        className="bg-surface border-border/70 shadow-background/40 mx-4 w-full max-w-sm overscroll-contain rounded-2xl border p-6 shadow-2xl outline-none"
      >
        <p id={messageId} className="text-text text-sm font-medium">
          {message}
        </p>
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button ref={cancelRef} variant="ghost" onClick={cancel}>
            Cancelar
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              onConfirm?.();
              cancel();
            }}
          >
            {confirmLabel || 'Eliminar'}
          </Button>
        </div>
      </div>
    </div>
  );
}
