import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * Guard de autenticación compartido por los layouts de rutas autenticadas
 * ((dashboard)/layout.tsx y app/capture/layout.tsx). Redirige a /login si no
 * hay JWT en localStorage. Extraído desde (dashboard)/layout.tsx en Fase 10
 * (Decisión 10.1.2 de docs/specs/fase_10_spec.md).
 */
export function useRequireAuth() {
  const router = useRouter();
  useEffect(() => {
    const token = localStorage.getItem('jwt_token');
    if (!token) router.replace('/login');
  }, [router]);
}
