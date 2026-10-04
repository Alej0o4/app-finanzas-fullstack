import { useEffect } from 'react';
import { useUiStore } from '@/store/useUiStore';

/**
 * Registra un diálogo abierto en el contador del store de UI (Fase 33 F6, QA-034), que
 * `InstallPrompt` lee para no renderizarse encima de un modal o de un confirm de borrado.
 *
 * El conteo va en un efecto con cleanup simétrico, nunca en el cuerpo del render: es lo
 * único que lo mantiene sin desfasarse con el doble montaje de efectos de StrictMode
 * (activo en dev — Next 16 lo pone por defecto), que da `+1 −1 +1` = neto +1. Un
 * incremento en el render o un async sin cleanup quedarían desfasados para el resto de la
 * sesión y apagarían el banner para siempre.
 */
export function useDialogCounter(isOpen: boolean): void {
  const openDialog = useUiStore((state) => state.openDialog);
  const closeDialog = useUiStore((state) => state.closeDialog);

  useEffect(() => {
    if (!isOpen) return;
    openDialog();
    return closeDialog;
  }, [isOpen, openDialog, closeDialog]);
}
