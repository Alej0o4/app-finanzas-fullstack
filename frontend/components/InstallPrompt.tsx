'use client';

import { useEffect, useState } from 'react';
import { Download, X } from 'lucide-react';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

/** Umbral de promoción (Fase 13 §13.1): recién desde la segunda visita autenticada —
 *  no competir con el onboarding en el primer render. Mismo mecanismo simple de
 *  localStorage que usePersistedState. */
const VISITS_KEY = 'oikos_install_visits';
const DISMISSED_KEY = 'oikos_install_dismissed';
const MIN_VISITS = 2;

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // localStorage lleno o no disponible: la promoción simplemente no persiste.
  }
}

function isStandalone(): boolean {
  if (typeof window === 'undefined') return false;
  return (
    ('standalone' in navigator && (navigator as { standalone?: boolean }).standalone === true) ||
    (typeof window.matchMedia === 'function' &&
      window.matchMedia('(display-mode: standalone)').matches)
  );
}

/** iOS Safari no dispara `beforeinstallprompt` (limitación de la plataforma): se
 *  muestra la instrucción estática. Chrome-iOS (CriOS) queda fuera: no expone
 *  "Agregar a pantalla de inicio" de la misma forma (limitación conocida, no bloqueante). */
function isIOSSafari(): boolean {
  if (typeof window === 'undefined') return false;
  return (
    /iphone|ipad|ipod/i.test(navigator.userAgent) &&
    !/crios|fxios|opios|edgios/i.test(navigator.userAgent)
  );
}

/**
 * Banner discreto de instalación PWA (Fase 13 §13.1): guarda el evento
 * `beforeinstallprompt` diferido (evita el prompt nativo automático) y muestra el
 * banner solo tras el umbral de visitas — nunca en el primer render.
 */
export default function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [visits, setVisits] = useState(() => Number(readStorage(VISITS_KEY) || '0'));
  const [dismissed, setDismissed] = useState(() => readStorage(DISMISSED_KEY) === '1');

  useEffect(() => {
    // Ya instalada (Chrome standalone o iOS agregada a pantalla de inicio): no promocionar.
    if (isStandalone()) return;

    const handleBeforeInstallPrompt = (event: Event) => {
      event.preventDefault();
      setDeferredPrompt(event as BeforeInstallPromptEvent);
    };
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);

    // Contador de visitas autenticadas: se incrementa en cada montaje del shell.
    // Es telemetría mínima de promoción, no un derivado de props — el setState aquí
    // es intencional (mismo precedente de acumulación que transactions/page.tsx usa
    // con setAllItems dentro de un efecto).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setVisits((prev) => {
      const next = prev + 1;
      writeStorage(VISITS_KEY, String(next));
      return next;
    });

    return () => window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
  }, []);

  const eligible = visits >= MIN_VISITS && !dismissed && !isStandalone();
  const showChrome = eligible && deferredPrompt !== null;
  const showIOS = eligible && deferredPrompt === null && isIOSSafari();

  if (!showChrome && !showIOS) return null;

  const handleInstallClick = async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    setDeferredPrompt(null);
    if (outcome === 'accepted') {
      writeStorage(DISMISSED_KEY, '1');
      setDismissed(true);
    }
  };

  const handleDismiss = () => {
    writeStorage(DISMISSED_KEY, '1');
    setDismissed(true);
  };

  return (
    <div className="bg-surface-elevated border-border shadow-background/40 fixed bottom-6 left-1/2 z-50 flex max-w-[calc(100vw-2rem)] -translate-x-1/2 items-center gap-3 rounded-2xl border px-4 py-3 shadow-2xl backdrop-blur-sm">
      <p className="text-text-muted text-xs sm:text-sm">
        {showChrome ? (
          <>
            <span className="text-primary font-semibold">Oikos</span> instalado se abre como app y
            puede notificarte.
          </>
        ) : (
          <>
            <span className="text-primary font-semibold">Oikos</span> en tu pantalla de inicio:{' '}
            <span className="text-text-soft">Compartir → Agregar a pantalla de inicio</span>
          </>
        )}
      </p>
      {showChrome && (
        <button
          type="button"
          onClick={handleInstallClick}
          className="bg-primary text-background hover:bg-primary-dark flex shrink-0 cursor-pointer items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors active:scale-95"
        >
          <Download size={14} />
          Instalar
        </button>
      )}
      <button
        type="button"
        onClick={handleDismiss}
        className="text-text-muted hover:text-text cursor-pointer rounded-md p-1 transition-colors"
        aria-label="Descartar aviso de instalación"
      >
        <X size={14} />
      </button>
    </div>
  );
}
