'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { PaginatedResponse, Transaction } from '@/types/api';

/** Feed paginado y filtrado de transacciones (`GET /transactions/`). `params` es el
 *  mismo objeto de query params que ya arma transactions/page.tsx (skip, limit,
 *  account_id, category_id, start_date, end_date) — Fase 25 §25.4. */
export function useTransactions(params: Record<string, unknown>) {
  return useQuery({
    queryKey: queryKeys.transactions.filtered(params),
    queryFn: async () => {
      const response = await api.get('transactions/', { params });
      return response.data as PaginatedResponse<Transaction>;
    },
  });
}
