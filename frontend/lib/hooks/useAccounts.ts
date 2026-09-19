'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { Account } from '@/types/api';

/** Lista de cuentas del usuario (`GET /accounts/`) — reemplaza el useQuery inline
 *  duplicado en 10 páginas/componentes (Fase 25 §25.4). */
export function useAccounts(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.accounts.all(),
    queryFn: async () => {
      const response = await api.get('accounts/');
      return response.data as Account[];
    },
    ...options,
  });
}
