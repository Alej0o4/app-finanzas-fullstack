import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { haySesionActiva } from '@/lib/authSession';

/**
 * Guard de autenticación compartido por los layouts de rutas autenticadas
 * ((dashboard)/layout.tsx y app/capture/layout.tsx). Redirige a /login si no
 * hay sesión activa (cookie csrf_token presente — señal de UX, no chequeo de
 * seguridad, Fase 26 Decisión F2). Extraído desde (dashboard)/layout.tsx en
 * Fase 10 (Decisión 10.1.2 de docs/specs/fase_10_spec.md).
 */
export function useRequireAuth() {
  const router = useRouter();
  useEffect(() => {
    if (!haySesionActiva()) router.replace('/login');
  }, [router]);
}
