'use client';

import { useEffect } from 'react';

/**
 * Registra el service worker de Oikos (`/sw.js`, Fase 13 §13.1) con feature-detection:
 * Safari de escritorio y navegadores viejos no soportan SW, y el registro es opcional
 * (mejora progresiva para instalabilidad y push) — un fallo jamás debe tumbar la app.
 */
export default function ServiceWorkerRegistration() {
  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {
        // Silencioso a propósito: el app funciona sin SW; solo pierde PWA/push.
      });
    }
  }, []);

  return null;
}
