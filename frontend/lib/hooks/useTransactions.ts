'use client';

import { useQuery, type UseQueryOptions } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { PaginatedResponse, Transaction } from '@/types/api';

type TransactionsQueryKey = readonly ['transactions', Record<string, unknown>];

/** Opciones de `useQuery` que el caller puede pasar. `queryKey` y `queryFn` los fija el hook. */
type TransactionsQueryOptions = Omit<
  UseQueryOptions<
    PaginatedResponse<Transaction>,
    Error,
    PaginatedResponse<Transaction>,
    TransactionsQueryKey
  >,
  'queryKey' | 'queryFn'
>;

/** Feed paginado y filtrado de transacciones (`GET /transactions/`). `params` es el
 *  mismo objeto de query params que ya arma transactions/page.tsx (skip, limit,
 *  account_id, category_id, start_date, end_date) — Fase 25 §25.4.
 *
 *  Fase 29: acepta un segundo argumento con opciones de `useQuery` para que el dashboard
 *  pueda usar `placeholderData: keepPreviousData` al navegar de mes — sin eso, cada `◀ ▶`
 *  devolvería la lista a `isLoading` y la sección volvería a su skeleton (User Story 9).
 *  Los callers que no pasan nada quedan idénticos a antes. */
export function useTransactions(
  params: Record<string, unknown>,
  options?: TransactionsQueryOptions
) {
  return useQuery({
    queryKey: queryKeys.transactions.filtered(params),
    queryFn: async () => {
      const response = await api.get('transactions/', { params });
      return response.data as PaginatedResponse<Transaction>;
    },
    ...options,
  });
}
