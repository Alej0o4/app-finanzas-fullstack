import { useEffect, useRef, type RefObject } from 'react';
import { useEscapeToClose } from './useEscapeToClose';

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Roles con los que un overlay cuenta como "diálogo": el confirm de borrado es un
 *  `alertdialog` (Fase 33 F8, QA-039) y si no estuviera acá su propio `focusin` se
 *  guardaría como "anteriormente enfocado", dejando el ref de restauración sucio. */
const DIALOG_ROLES = '[role="dialog"], [role="alertdialog"]';

interface UseDialogFocusOptions {
  isOpen: boolean;
  dialogRef: RefObject<HTMLElement | null>;
  onClose: () => void;
  /** Elemento al que se le da el foco al abrir. Por defecto, el primer campo del
   *  contenido y, si no hay, el propio diálogo. */
  initialFocusRef?: RefObject<HTMLElement | null>;
}

/**
 * Foco inicial, trampa de Tab, restauración al cerrar y Escape de un diálogo modal
 * (QA-014, compartido con el confirm de borrado desde la Fase 33 F8). Se extrajo de
 * `ModalShell` para que el confirm cumpliera el mismo estándar sin duplicar la lógica ni
 * tener que usar el encabezado de `ModalShell`, que no tiene.
 *
 * El comportamiento por defecto es el de `ModalShell` sin cambios: si no se pasa
 * `initialFocusRef` y ningún hijo tiene `autoFocus`, el foco va al primer campo.
 */
export function useDialogFocus({
  isOpen,
  dialogRef,
  onClose,
  initialFocusRef,
}: UseDialogFocusOptions): void {
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  // El elemento que abrió el diálogo: se rastrea con `focusin` mientras el foco está FUERA
  // del diálogo. No se puede leer `document.activeElement` al abrir porque un hijo con
  // `autoFocus` ya movió el foco para cuando corre el efecto.
  useEffect(() => {
    const track = (e: FocusEvent) => {
      const target = e.target as HTMLElement | null;
      // `closest` y no `dialogRef.contains`: el `autoFocus` de un hijo puede dispararse
      // antes de que el ref del diálogo esté asignado.
      if (target && !target.closest(DIALOG_ROLES)) previouslyFocusedRef.current = target;
    };
    document.addEventListener('focusin', track);
    return () => document.removeEventListener('focusin', track);
  }, []);

  useEscapeToClose(isOpen, onClose);

  useEffect(() => {
    if (!isOpen) return;
    const dialog = dialogRef.current;
    if (!dialog) return;

    // Respeta un `autoFocus` de los hijos (ya aplicado al montar); si no hay, se enfoca el
    // elemento que pidió el caller, el primer campo del contenido (no el botón "Cerrar") o,
    // en su defecto, el propio diálogo.
    if (!dialog.contains(document.activeElement)) {
      const firstField = dialog.querySelector<HTMLElement>(
        'input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled])'
      );
      (initialFocusRef?.current ?? firstField ?? dialog).focus();
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
  }, [isOpen, dialogRef, initialFocusRef]);
}
