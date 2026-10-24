'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { Transfer, TransferPayload } from '@/types/api';

/** Una transferencia mueve saldos de dos cuentas y puede tocar sobres y CDT vinculados (Fase 39,
 *  F4). NO toca presupuestos ni Analítica: las transferencias no son flujo. */
export function useInvalidateAfterTransfer() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.summary() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.cdts.all() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.funds.all() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.funds.details() }),
    ]);
}

export function useCreateTransfer() {
  const invalidate = useInvalidateAfterTransfer();
  return useMutation({
    mutationFn: async (payload: TransferPayload) =>
      (await api.post('transfers/', payload)).data as Transfer,
    onSuccess: () => invalidate(),
  });
}

export function useUpdateTransfer(id: number) {
  const invalidate = useInvalidateAfterTransfer();
  return useMutation({
    mutationFn: async (payload: TransferPayload) =>
      (await api.put(`transfers/${id}`, payload)).data as Transfer,
    // También en error: un 409 (vinculada a un CDT) se arregla re-leyendo la lista.
    onSettled: () => invalidate(),
  });
}

export function useDeleteTransfer() {
  const invalidate = useInvalidateAfterTransfer();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`transfers/${id}`);
    },
    onSettled: () => invalidate(),
  });
}
