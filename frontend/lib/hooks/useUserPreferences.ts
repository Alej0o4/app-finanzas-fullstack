'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import { useAppConfig } from '@/providers/AppConfigProvider';
import { useEffect } from 'react';
import type { PreferencesUpdatePayload, UserPreferences } from '@/types/api';

export function useUserPreferences() {
  const { updateConfig } = useAppConfig();
  const queryClient = useQueryClient();

  const hasToken = typeof window !== 'undefined' && !!localStorage.getItem('jwt_token');

  const query = useQuery({
    queryKey: queryKeys.userPreferences(),
    queryFn: async () => {
      const res = await api.get('users/me/preferences');
      return res.data as UserPreferences;
    },
    enabled: hasToken,
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (query.data) {
      updateConfig({
        currency: query.data.preferred_currency,
        locale: query.data.preferred_locale,
        theme: query.data.preferred_theme,
      });
    }
  }, [query.data, updateConfig]);

  // Mutación compartida para escribir preferencias (Fase 14 §14.6.2): el mismo
  // patrón que ThemeToggle usaba duplicado; las escrituras que tocan el tema
  // actualizan la configuración de la app para que el cambio aplique en vivo.
  const mutation = useMutation({
    mutationFn: async (body: PreferencesUpdatePayload) => {
      await api.patch('users/me/preferences', body);
    },
    onSuccess: (_data, body) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.userPreferences() });

      // B1 (spec Fase 21): `currentUser()` es la fuente real de
      // `user?.preferred_currency` que leen dashboard/accounts/analytics, y
      // `categoryBreakdown()` tiene clave fija con la moneda pasada por query param —
      // invalidar ambas acá evita que el dashboard sirva el desglose de la moneda vieja
      // desde cache hasta un reload manual (Hallazgo 8).
      if (body.preferred_currency) {
        queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() });
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.categoryBreakdown() });
      }
      if (body.apply_to_default_account) {
        // Fase 22 §22.1 (Decisión 22.1.6): la cuenta por defecto pudo cambiar de moneda
        // server-side; `accounts.all()` alimenta el selector de Settings (Decisión 21.1.1)
        // y `TransactionCaptureForm`, que la leen del mismo cache.
        queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      }
      if (body.preferred_theme) {
        updateConfig({ theme: body.preferred_theme });
      }
    },
  });

  return {
    preferences: query.data,
    isLoading: query.isLoading,
    error: query.error,
    updatePreferences: mutation,
  };
}
