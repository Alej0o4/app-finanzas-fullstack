'use client';

import { deviceTimezone, safeTimezone } from '@/lib/dates';
import { useCurrentUser } from '@/lib/hooks/useCurrentUser';

/**
 * Fase 34 §F1 — acceso único a la zona horaria del usuario.
 *
 * - `timezone`: la zona guardada (`User.timezone`) o `undefined` mientras `/users/me` no
 *   cargó. Las queries que mandan un rango dependiente de la zona se habilitan con `ready`:
 *   mandar un rango calculado con la zona equivocada pediría (y cachearía) el período errado.
 * - `displayTimezone`: siempre definida; cae a la del dispositivo mientras no hay usuario. Es
 *   para formatear fechas en pantalla, donde un parpadeo de zona es inocuo.
 */
export function useTimezone() {
  const { data: user } = useCurrentUser();
  const timezone = user?.timezone ? safeTimezone(user.timezone) : undefined;
  return {
    timezone,
    ready: timezone !== undefined,
    displayTimezone: timezone ?? deviceTimezone(),
  };
}
