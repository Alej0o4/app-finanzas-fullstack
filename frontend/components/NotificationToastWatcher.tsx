'use client';

import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import { useUnreadCount } from '@/hooks/useNotifications';
import type { AppNotification, PaginatedResponse } from '@/types/api';

async function fetchLatestNotifications(limit: number): Promise<AppNotification[]> {
  const response = await api.get('notifications/', { params: { skip: 0, limit } });
  return (response.data as PaginatedResponse<AppNotification>).items;
}

/**
 * Toast (sonner) por cada aviso nuevo mientras la app está abierta — el bell + badge
 * (Fase 13 §13.5) sigue siendo el registro persistente, pero un badge que tarda hasta
 * 60s en notarse es poco visible comparado con el resto de acciones de la app, que
 * usan toast (crear transacción, guardar presupuesto, etc.).
 *
 * Se apoya en el poll ya existente de `useUnreadCount` en vez de agregar uno propio a
 * la query de lista completa (Decisión 13.5.4: esa query es más pesada y a propósito
 * no tiene `refetchInterval`) — solo se pide la lista, bajo demanda, cuando el conteo
 * sube. Monta una sola vez en el shell autenticado, independiente de si el sidebar
 * está colapsado (a diferencia de `NotificationBell`, que se desmonta/remonta al
 * togglear el sidebar).
 */
export default function NotificationToastWatcher() {
  const queryClient = useQueryClient();
  const { data: unreadData } = useUnreadCount();
  const lastCountRef = useRef<number | null>(null);
  const lastSeenIdRef = useRef(0);
  const seededRef = useRef(false);

  useEffect(() => {
    const count = unreadData?.count;
    if (count === undefined) return;

    if (!seededRef.current) {
      // Primera carga: solo sembrar el cursor — nunca mostrar como toast el backlog de
      // avisos sin leer que ya existía antes de abrir la app.
      seededRef.current = true;
      lastCountRef.current = count;
      fetchLatestNotifications(1)
        .then((items) => {
          lastSeenIdRef.current = items[0]?.id ?? 0;
        })
        .catch(() => {
          // Silencioso: en el peor caso el próximo aviso real también dispara el fetch
          // de abajo y el cursor se siembra ahí.
        });
      return;
    }

    if (lastCountRef.current !== null && count > lastCountRef.current) {
      fetchLatestNotifications(10)
        .then((items) => {
          const nuevas = items
            .filter((n) => n.id > lastSeenIdRef.current)
            .sort((a, b) => a.id - b.id);
          for (const notificacion of nuevas) {
            toast.warning(notificacion.title, { description: notificacion.body });
          }
          if (items.length > 0) {
            lastSeenIdRef.current = Math.max(lastSeenIdRef.current, ...items.map((n) => n.id));
          }
          if (nuevas.length > 0) {
            // Invalida (no sobreescribe) la query de la lista completa: si el popover
            // está abierto, se refresca solo; si no, la próxima apertura trae los avisos
            // nuevos sin depender de este fetch parcial de 10 filas.
            queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all() });
          }
        })
        .catch(() => {
          // Silencioso: el aviso ya quedó en la bandeja in-app (fuente de verdad); el
          // toast es un canal adicional, best-effort, igual que el push (Decisión 13.2.3).
        });
    }

    lastCountRef.current = count;
  }, [unreadData?.count, queryClient]);

  return null;
}
