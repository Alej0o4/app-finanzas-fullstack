import type { UserResponse } from '@/types/api';

/**
 * Fase 31 F5 (Q4, QA-005): un solo criterio de destino post-login, compartido entre
 * `login/page.tsx` y `GoogleAuthButton` para que las dos formas de entrar se comporten
 * igual. Sin historial de transacciones → onboarding guiado; con historial → dashboard.
 */
export function getPostLoginDestination(user: UserResponse): string {
  return user.has_transaction_history ? '/' : '/capture?onboarding=1';
}
