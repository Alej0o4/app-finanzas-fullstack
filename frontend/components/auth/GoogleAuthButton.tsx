'use client';

import { useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { UserResponse } from '@/types/api';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (resp: { credential: string }) => void;
          }) => void;
          renderButton: (parent: HTMLElement, options: Record<string, unknown>) => void;
        };
      };
    };
  }
}

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

// El SDK de GIS se carga con next/script afterInteractive (layout de auth) — asíncrono, así
// que `window.google` puede tardar unos cientos de ms en existir tras el montaje. Se reintenta
// la inicialización cada ~200ms hasta ~10s antes de rendirse (igual que sin configurar).
const POLL_INTERVAL_MS = 200;
const MAX_POLL_ATTEMPTS = 50;

export default function GoogleAuthButton() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const buttonRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;

    const handleCredential = async (response: { credential: string }) => {
      try {
        const { data } = await api.post('auth/google', { id_token: response.credential });
        localStorage.setItem('jwt_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);

        // Mismo criterio de destino que login/page.tsx:79-86 — funciona igual para un
        // registro nuevo (has_transaction_history=false → /capture) y para una usuaria
        // recurrente que eligió Google (→ /dashboard).
        try {
          const meResponse = await api.get('users/me');
          const user = meResponse.data as UserResponse;
          queryClient.setQueryData(queryKeys.currentUser(), user);
          router.push(user.has_transaction_history ? '/dashboard' : '/capture?onboarding=1');
        } catch {
          router.push('/capture');
        }
      } catch {
        // Fallo silencioso intencional: sin estado de error propio en este componente
        // mínimo. Si falla, la usuaria sigue viendo el formulario normal de la página y
        // puede reintentar con Google o usar contraseña — no bloquea el flujo existente.
      }
    };

    const initGoogleButton = () => {
      if (!window.google?.accounts?.id) return false;
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleCredential,
      });
      if (buttonRef.current) {
        window.google.accounts.id.renderButton(buttonRef.current, {
          theme: 'outline',
          size: 'large',
          width: '100%',
          text: 'continue_with',
          locale: 'es',
        });
      }
      return true;
    };

    // Guard de arranque: el script GIS (afterInteractive) puede no haber cargado cuando este
    // efecto corre. Un `?.` directo silenciosamente nunca renderizaría el botón; en cambio se
    // hace poll hasta que window.google exista (o hasta agotar la ventana de ~10s, degradando
    // a no renderizar nada — el mismo comportamiento que con NEXT_PUBLIC_GOOGLE_CLIENT_ID ausente).
    if (initGoogleButton()) return;

    let cancelled = false;
    let attempts = 0;
    const interval = window.setInterval(() => {
      attempts += 1;
      if (cancelled || attempts > MAX_POLL_ATTEMPTS) {
        window.clearInterval(interval);
        return;
      }
      if (initGoogleButton()) window.clearInterval(interval);
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [router, queryClient]);

  if (!GOOGLE_CLIENT_ID) return null;

  return (
    <div className="mt-6">
      <div className="mb-4 flex items-center gap-3">
        <div className="border-border/70 h-px flex-1 border-t" />
        <span className="text-text-muted text-xs">o</span>
        <div className="border-border/70 h-px flex-1 border-t" />
      </div>
      <div ref={buttonRef} />
    </div>
  );
}
