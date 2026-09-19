'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { Category } from '@/types/api';

/** Lista de categorías del usuario, incluye is_hidden (Fase 18) — GET /categories/. */
export function useCategories(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.categories.all(),
    queryFn: async () => {
      const response = await api.get('categories/');
      return response.data as Category[];
    },
    ...options,
  });
}
