'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type {
  CreateFundPayload,
  Fund,
  FundDetail,
  FundEntry,
  UpdateFundPayload,
} from '@/types/api';

/** Lista de sobres (`GET /funds/`). Con `includeArchived` la key lleva un segmento extra, pero
 *  sigue colgando de `['funds']`, así que `invalidateQueries(funds.all())` cubre ambas. */
export function useFunds(options?: { includeArchived?: boolean }) {
  const includeArchived = options?.includeArchived ?? false;
  return useQuery({
    queryKey: includeArchived
      ? ([...queryKeys.funds.all(), 'archived'] as const)
      : queryKeys.funds.all(),
    queryFn: async () => {
      const response = await api.get('funds/', { params: { include_archived: includeArchived } });
      return response.data as Fund[];
    },
    staleTime: 0, // ver useFund: el respaldo depende de cuentas/transacciones
  });
}

/** Detalle de un sobre con sus últimos 50 movimientos (`GET /funds/{id}`). */
export function useFund(id: string | number) {
  return useQuery({
    queryKey: queryKeys.funds.byId(id),
    queryFn: async () => (await api.get(`funds/${id}`)).data as FundDetail,
    // El faltante de respaldo depende del saldo de las cuentas, que cambia con transacciones
    // y cuentas (que no invalidan estas keys): siempre se re-lee al montar.
    staleTime: 0,
  });
}

/** Invalidación común de toda mutación de sobres: la lista, el detalle y el "Disponible real"
 *  del dashboard (prefijo sin segmento de mes, regla de queryKeys.ts). */
function useInvalidateFunds() {
  const queryClient = useQueryClient();
  return (fundId?: string | number) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.funds.all() });
    if (fundId !== undefined) {
      queryClient.invalidateQueries({ queryKey: queryKeys.funds.byId(fundId) });
    }
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
  };
}

export function useCreateFund() {
  const invalidate = useInvalidateFunds();
  return useMutation({
    mutationFn: async (payload: CreateFundPayload) =>
      (await api.post('funds/', payload)).data as Fund,
    onSuccess: (fund) => invalidate(fund.id),
  });
}

export function useUpdateFund(id: string | number) {
  const invalidate = useInvalidateFunds();
  return useMutation({
    mutationFn: async (payload: UpdateFundPayload) =>
      (await api.put(`funds/${id}`, payload)).data as Fund,
    onSuccess: () => invalidate(id),
  });
}

/** Aportar o retirar: mismo body `{amount, note?}`, distinta ruta. */
export function useFundMovement(id: string | number, kind: 'contributions' | 'withdrawals') {
  const invalidate = useInvalidateFunds();
  return useMutation({
    mutationFn: async (payload: { amount: number; note?: string }) =>
      (await api.post(`funds/${id}/${kind}`, payload)).data as FundEntry,
    onSuccess: () => invalidate(id),
  });
}

/** Borra el sobre y su historial (A1). El detalle ya no existe: se quita del caché en vez de
 *  invalidarlo (refetchearía un 404); la lista y el "Disponible real" sí se invalidan. */
export function useDeleteFund(id: string | number) {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateFunds();
  return useMutation({
    mutationFn: async () => {
      await api.delete(`funds/${id}`);
    },
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: queryKeys.funds.byId(id) });
      invalidate();
    },
  });
}

export function useArchiveFund(id: string | number) {
  const invalidate = useInvalidateFunds();
  return useMutation({
    mutationFn: async (archive: boolean) =>
      (await api.post(`funds/${id}/${archive ? 'archive' : 'unarchive'}`)).data as Fund,
    onSuccess: () => invalidate(id),
  });
}
