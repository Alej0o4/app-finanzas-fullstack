'use client';

import { toast } from 'sonner';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import { getApiError } from '@/lib/utils';
import type {
  Cdt,
  CdtListResponse,
  CreateCdtPayload,
  RedeemCdtPayload,
  UpdateCdtPayload,
} from '@/types/api';

// Fase 38. El backend es la fuente de verdad: interés causado, valores, alerta y totales llegan
// calculados; aquí no se calcula nada. Las cifras dependen de "hoy" (zona del usuario), así que la
// lectura usa `staleTime: 0` y se re-lee al montar la página o la tarjeta del dashboard.

/** Todos los CDT (vigentes primero, luego redimidos) con `totals` de los vigentes. Una sola
 *  query sin filtro: la página y la tarjeta del dashboard comparten caché. */
export function useCdts(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.cdts.all(),
    queryFn: async () => (await api.get('cdts/')).data as CdtListResponse,
    staleTime: 0,
    ...options,
  });
}

/** Un CDT no mueve saldos (D1): toda mutación invalida solo `cdts` y el resumen del dashboard
 *  (`cdt_total` / `net_worth`). Nunca `accounts`, `transactions` ni `funds`. */
function useInvalidateCdts() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.cdts.all() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() }),
    ]);
}

export function useCreateCdt() {
  const invalidate = useInvalidateCdts();
  return useMutation({
    mutationFn: async (payload: CreateCdtPayload) => (await api.post('cdts/', payload)).data as Cdt,
    onSuccess: () => invalidate(),
  });
}

export function useUpdateCdt(id: number) {
  const invalidate = useInvalidateCdts();
  return useMutation({
    mutationFn: async (payload: UpdateCdtPayload) =>
      (await api.put(`cdts/${id}`, payload)).data as Cdt,
    // También en error: un 409 (ya redimido en otra pestaña) se arregla re-leyendo la lista.
    onSettled: () => invalidate(),
  });
}

export function useRedeemCdt(id: number) {
  const invalidate = useInvalidateCdts();
  return useMutation({
    mutationFn: async (payload: RedeemCdtPayload) =>
      (await api.post(`cdts/${id}/redeem`, payload)).data as Cdt,
    onSettled: () => invalidate(),
  });
}

export function useDeleteCdt(id: number) {
  const invalidate = useInvalidateCdts();
  return useMutation({
    mutationFn: async () => {
      await api.delete(`cdts/${id}`);
    },
    // El toast vive aquí: la tarjeta se desmonta al refrescar la lista y TanStack no ejecuta los
    // callbacks por-llamada de un observer desmontado.
    onSuccess: () => {
      toast.success('CDT eliminado');
      return invalidate();
    },
    onError: (error) => toast.error(getApiError(error)),
  });
}
