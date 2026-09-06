'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { AppNotification, PaginatedResponse, UnreadCountResponse } from '@/types/api';

const NOTIFICATIONS_PAGE_SIZE = 50;

/**
 * Bandeja de avisos in-app (Fase 13 §13.5).
 *
 * La lista y el conteo del badge viven en queries SEPARADAS a propósito (Decisión 13.5.4):
 * el `refetchInterval` corto del badge no debe disparar la query de lista completa — el
 * unread-count es un COUNT(*) barato en el backend, la lista es una query pesada.
 */
export function useNotifications() {
  return useQuery({
    queryKey: queryKeys.notifications.all(),
    queryFn: async () => {
      const response = await api.get('notifications/', {
        params: { skip: 0, limit: NOTIFICATIONS_PAGE_SIZE },
      });
      return response.data as PaginatedResponse<AppNotification>;
    },
  });
}

export function useUnreadCount() {
  return useQuery({
    queryKey: queryKeys.notifications.unreadCount(),
    queryFn: async () => {
      const response = await api.get('notifications/unread-count');
      return response.data as UnreadCountResponse;
    },
    refetchInterval: 60_000,
  });
}

/** Marca una notificación como leída e invalida lista + badge. */
export function useMarkAsRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (notificationId: number) => {
      const response = await api.patch(`notifications/${notificationId}/read`);
      return response.data as AppNotification;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications.unreadCount() });
    },
  });
}

/** Acción "marcar todo como leído" de la bandeja (PATCH /notifications/read-all). */
export function useMarkAllAsRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const response = await api.patch('notifications/read-all');
      return response.data as UnreadCountResponse;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications.unreadCount() });
    },
  });
}
