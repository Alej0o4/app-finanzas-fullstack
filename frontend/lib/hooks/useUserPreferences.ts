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
