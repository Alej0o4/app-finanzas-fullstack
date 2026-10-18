'use client';

import { toast } from 'sonner';
import { getApiError } from '@/lib/utils';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type {
  CreateRecurringPayload,
  PendingOccurrence,
  RecurringCalendar,
  RecurringRule,
  RecurringSuggestion,
  Transaction,
  UpdateRecurringPayload,
} from '@/types/api';

// Fase 37. El backend es la fuente de verdad: pendientes, calendario, costo mensualizado y
// sugerencias llegan calculados; aquí no se proyecta ninguna fecha ni se suma ningún monto.
// Las ocurrencias dependen de "hoy" (zona del usuario) y de resolver en orden, así que todas las
// lecturas usan `staleTime: 0`: se re-leen al montar la página o la tarjeta del dashboard.

/** Reglas del usuario, activas y pausadas (`GET /recurring/`). */
export function useRecurringRules() {
  return useQuery({
    queryKey: queryKeys.recurring.rules(),
    queryFn: async () => (await api.get('recurring/')).data as RecurringRule[],
    staleTime: 0,
  });
}

/** Ocurrencias vencidas por confirmar o saltar (`GET /recurring/pending`). */
export function usePendingRecurring(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.recurring.pending(),
    queryFn: async () => (await api.get('recurring/pending')).data as PendingOccurrence[],
    staleTime: 0,
    ...options,
  });
}

/** Calendario de 12 meses con totales por moneda y `monthly_commitment`. */
export function useRecurringCalendar() {
  return useQuery({
    queryKey: queryKeys.recurring.calendar(),
    queryFn: async () => (await api.get('recurring/calendar')).data as RecurringCalendar,
    staleTime: 0,
  });
}

/** Cargos anuales detectados en el historial (`GET /recurring/suggestions`). */
export function useRecurringSuggestions() {
  return useQuery({
    queryKey: queryKeys.recurring.suggestions(),
    queryFn: async () => (await api.get('recurring/suggestions')).data as RecurringSuggestion[],
    staleTime: 0,
  });
}

/** Crear, editar, pausar, saltar o borrar solo cambian lo recurrente (reglas, pendientes,
 *  calendario y sugerencias, todos bajo el prefijo `['recurring']`). */
function useInvalidateRecurring() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.recurring.all() });
}

export function useCreateRecurring() {
  const invalidate = useInvalidateRecurring();
  return useMutation({
    mutationFn: async (payload: CreateRecurringPayload) =>
      (await api.post('recurring/', payload)).data as RecurringRule,
    onSuccess: () => invalidate(),
  });
}

/** También pausa/reanuda (`{ status }`). Reanudar mueve `next_date` en el servidor. */
export function useUpdateRecurring(id: number) {
  const invalidate = useInvalidateRecurring();
  return useMutation({
    mutationFn: async (payload: UpdateRecurringPayload) =>
      (await api.put(`recurring/${id}`, payload)).data as RecurringRule,
    onSuccess: () => invalidate(),
  });
}

export function useDeleteRecurring(id: number) {
  const invalidate = useInvalidateRecurring();
  return useMutation({
    mutationFn: async () => {
      await api.delete(`recurring/${id}`);
    },
    // Los toasts de skip/confirm/delete viven aquí y no en el `mutate(..., { onSuccess })` del
    // componente: la fila/tarjeta se desmonta al refrescar la lista y TanStack no ejecuta los
    // callbacks por-llamada de un observer desmontado.
    onSuccess: () => {
      toast.success('Regla eliminada');
      return invalidate();
    },
    onError: (error) => toast.error(getApiError(error)),
  });
}

export function useSkipRecurring() {
  const invalidate = useInvalidateRecurring();
  return useMutation({
    mutationFn: async ({ ruleId, occurrenceDate }: { ruleId: number; occurrenceDate: string }) =>
      (await api.post(`recurring/${ruleId}/skip`, { occurrence_date: occurrenceDate }))
        .data as RecurringRule,
    onSuccess: () => toast.success('Ocurrencia saltada'),
    onError: (error) => toast.error(getApiError(error)),
    // También en error: un 409 (ya resuelta en otra pestaña) se arregla re-leyendo la lista.
    onSettled: () => invalidate(),
  });
}

/**
 * Confirmar crea una transacción normal y mueve el saldo de la cuenta, así que invalida lo mismo
 * que crear una transacción (ver `TransactionModal`) además de lo recurrente.
 * `amount` se omite para usar el de la regla.
 */
export function useConfirmRecurring() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      ruleId,
      occurrenceDate,
      amount,
    }: {
      ruleId: number;
      occurrenceDate: string;
      amount?: number;
    }) =>
      (
        await api.post(`recurring/${ruleId}/confirm`, {
          occurrence_date: occurrenceDate,
          amount: amount ?? null,
        })
      ).data as Transaction,
    onSuccess: (tx) => toast.success(`Registrado: ${tx.description ?? 'recurrente'}`),
    onError: (error) => toast.error(getApiError(error)),
    onSettled: async (_data, error) => {
      // Un 409/404 no movió dinero: basta re-leer lo recurrente.
      const invalidations = [
        queryClient.invalidateQueries({ queryKey: queryKeys.recurring.all() }),
      ];
      if (!error) {
        invalidations.push(
          queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all() }),
          queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() }),
          queryClient.invalidateQueries({ queryKey: queryKeys.accounts.summary() }),
          queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() }),
          queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.categoryBreakdown() }),
          queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() }),
          queryClient.invalidateQueries({ queryKey: queryKeys.budgets.all() }),
          queryClient.invalidateQueries({ queryKey: ['analytics-cashflow'] }),
          queryClient.invalidateQueries({ queryKey: ['analytics-categories'] }),
          queryClient.invalidateQueries({ queryKey: queryKeys.funds.all() }),
          queryClient.invalidateQueries({ queryKey: queryKeys.funds.details() })
        );
      }
      await Promise.all(invalidations);
    },
  });
}
