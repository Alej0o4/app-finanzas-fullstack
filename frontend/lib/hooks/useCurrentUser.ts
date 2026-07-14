import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';

export function useCurrentUser() {
  return useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: async () => {
      const response = await api.get('/api/users/me');
      return response.data as {
        id: number;
        email: string;
        full_name: string;
        preferred_currency: string;
        preferred_locale: string;
      };
    },
  });
}
