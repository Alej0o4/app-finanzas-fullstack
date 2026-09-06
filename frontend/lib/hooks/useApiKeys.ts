'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { components } from '@/types/generated/api';

// Fase 16 §16.1: los schemas de API keys nacen junto con el codegen (§16.3) — se tipan
// con los tipos generados desde openapi.json (types/generated/api.ts), no con los manuales
// de types/api.ts (regla "código nuevo usa tipos generados", Decisión 16.3.2).
type ApiKey = components['schemas']['ApiKeyResponse'];
type ApiKeyCreateResponse = components['schemas']['ApiKeyCreateResponse'];

/** Lista de API keys propias (`GET /api-keys/`). Incluye las revocadas — `revoked_at`
 *  seteado — para que el usuario pueda auditar qué key existió y cuándo se usó. */
export function useApiKeys() {
  return useQuery({
    queryKey: queryKeys.apiKeys(),
    queryFn: async () => {
      const response = await api.get('api-keys/');
      return response.data as ApiKey[];
    },
  });
}

/** Crea una API key (`POST /api-keys/`). La respuesta trae la key en texto plano una
 *  sola vez (§16.1.4, Decisión 16.1.5) — el caller debe mostrarla antes de descartarla. */
export function useCreateApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (name: string) => {
      const response = await api.post('api-keys/', { name });
      return response.data as ApiKeyCreateResponse;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.apiKeys() });
    },
  });
}

/** Revoca una API key (`DELETE /api-keys/{id}` — marca `revoked_at`, no borra la fila). */
export function useRevokeApiKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`api-keys/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.apiKeys() });
    },
  });
}
