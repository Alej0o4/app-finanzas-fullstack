'use client';

import { useEffect, useState } from 'react';
import { BellPlus } from 'lucide-react';
import { api } from '@/lib/api';

type PushOptInState = 'idle' | 'done' | 'blocked' | 'unavailable';

/** Se marca tras una suscripción exitosa: evita re-verificar/re-POSTear en cada
 *  apertura del popover (el upsert del backend es idempotente, pero no hace falta). */
const OPTED_IN_KEY = 'oikos_push_opted_in';

function readOptedIn(): boolean {
  try {
    return localStorage.getItem(OPTED_IN_KEY) === '1';
  } catch {
    return false;
  }
}

function markOptedIn() {
  try {
    localStorage.setItem(OPTED_IN_KEY, '1');
  } catch {
    // localStorage no disponible: el flag no persiste, se re-verifica la próxima vez.
  }
}

/** Convierte una clave VAPID base64url (la que devuelve el backend) a Uint8Array,
 *  el formato que exige `PushManager.subscribe({ applicationServerKey })`. El
 *  `Uint8Array<ArrayBuffer>` explícito es requerido por el tipado de BufferSource. */
function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(new ArrayBuffer(rawData.length));
  for (let i = 0; i < rawData.length; i++) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

/**
 * Opt-in discreto de push web (Fase 13 §13.2): se monta en el footer del popover de
 * notificaciones — nunca un modal que bloquee. Maneja silenciosamente todo fallo:
 * permiso denegado, push no soportado, 503 de VAPID y suscripción ya existente.
 * iOS sin service worker/push soportado → no renderiza nada.
 */
export default function PushOptIn() {
  const [status, setStatus] = useState<PushOptInState>('idle');

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      // Fuerza una continuación async para que ninguna transición de estado ocurra
      // de forma síncrona dentro del efecto (regla react-hooks/set-state-in-effect).
      await Promise.resolve();

      if (
        !('serviceWorker' in navigator) ||
        !('PushManager' in window) ||
        !('Notification' in window)
      ) {
        if (!cancelled) setStatus('unavailable');
        return;
      }

      if (Notification.permission === 'denied') {
        if (!cancelled) setStatus('blocked');
        return;
      }

      // Ya se optó en este navegador en una sesión previa: nada que hacer, sin
      // re-verificar el subscription ni volver a POSTear.
      if (readOptedIn()) {
        if (!cancelled) setStatus('done');
        return;
      }

      try {
        const registration = await navigator.serviceWorker.ready;
        const existing = await registration.pushManager.getSubscription();

        // Ya suscrito en este navegador (sesión previa o instalación previa de la PWA)
        // sin el flag (p. ej. se limpió el storage): re-registrar el endpoint con el
        // usuario actual — el backend hace upsert por endpoint. Silencioso, sin botón.
        if (existing) {
          const json = existing.toJSON();
          if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) {
            if (!cancelled) setStatus('unavailable');
            return;
          }
          await api.post('push/subscribe', {
            endpoint: json.endpoint,
            keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
          });
          markOptedIn();
          if (!cancelled) setStatus('done');
        }
        // Sin suscripción y permiso 'default'/'granted': queda 'idle' y se muestra el botón.
      } catch {
        if (!cancelled) setStatus('unavailable');
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const handleOptIn = async () => {
    if (status !== 'idle') return;

    try {
      let permission = Notification.permission;
      if (permission === 'default') {
        permission = await Notification.requestPermission();
      }
      if (permission !== 'granted') {
        setStatus('blocked');
        return;
      }

      // Endpoint público, pero responde 503 si VAPID no está configurado en el backend
      // (mismo criterio de fallo silencioso con log que email.py/SMTP). Se captura abajo.
      const keyResponse = await api.get('push/vapid-public-key');
      const { public_key: publicKey } = keyResponse.data as { public_key: string };
      if (!publicKey) throw new Error('VAPID_PUBLIC_KEY sin configurar');

      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      });

      // subscription.toJSON() ya da el shape { endpoint, keys: { p256dh, auth } }.
      const json = subscription.toJSON();
      if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) {
        throw new Error('Suscripción push incompleta del navegador');
      }

      await api.post('push/subscribe', {
        endpoint: json.endpoint,
        keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
      });

      markOptedIn();
      setStatus('done');
    } catch {
      // Fallo silencioso (denegado, 503 de VAPID, red, navegador sin consentimiento):
      // la bandeja in-app sigue siendo el canal garantizado (Decisión 13.2.3).
      setStatus('unavailable');
    }
  };

  if (status !== 'idle') return null;

  return (
    <div className="border-border/40 text-text-muted flex items-center justify-between gap-2 border-t px-3 py-2">
      <span className="text-[11px]">¿Quieres avisos fuera de Oikos?</span>
      <button
        type="button"
        onClick={handleOptIn}
        className="text-text hover:bg-surface flex shrink-0 cursor-pointer items-center gap-1 rounded-md px-1.5 py-1 text-[11px] font-medium transition-colors active:scale-95"
      >
        <BellPlus size={12} />
        Activar
      </button>
    </div>
  );
}
