/**
 * Fase 26: con cookies httpOnly, JS ya no puede leer el JWT — pero sí puede leer el cookie
 * csrf_token (no-httpOnly a propósito, ver backend/app/core/auth_cookies.py), que el backend
 * setea/limpia exactamente cuando hay/no-hay sesión. Se reusa como señal de "¿hay sesión
 * activa?" para UX (mostrar/ocultar, activar una query) — NO es un chequeo de seguridad: la
 * fuente de verdad sigue siendo el 401 real del backend en cada request (igual que hoy).
 */
export function haySesionActiva(): boolean {
  if (typeof document === 'undefined') return false;
  return /(?:^|; )csrf_token=/.test(document.cookie);
}

// Fase 31 F4 (Q5, QA-021): rutas del grupo `(auth)` — sin sidebar, sin sesión requerida.
// El interceptor de `lib/api.ts` las usa para no redirigir a /login cuando ya se está en
// una de ellas (una cookie csrf_token huérfana no debe recargar /login en bucle).
export const AUTH_ROUTES = [
  '/login',
  '/register',
  '/forgot-password',
  '/reset-password',
  '/verify-email',
] as const;

export function isAuthRoute(pathname: string): boolean {
  return AUTH_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`));
}
