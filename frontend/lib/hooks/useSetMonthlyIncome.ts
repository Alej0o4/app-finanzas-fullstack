import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';

/** PATCH /api/v1/users/me { monthly_income } — compartido entre la card inline del
 * dashboard (Decisión 11.3.2) y el paso de onboarding de Fase 15 (Decisión 15.3.1).
 * No hace toast aquí: cada caller decide su propio mensaje/transición. */
export function useSetMonthlyIncome() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (monthly_income: number) =>
      (await api.patch('users/me', { monthly_income })).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
    },
  });
}
