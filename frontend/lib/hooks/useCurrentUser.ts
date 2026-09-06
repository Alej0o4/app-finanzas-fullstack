import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { UserResponse } from '@/types/api';

export function useCurrentUser() {
  return useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: async () => {
      const response = await api.get('users/me');
      return response.data as UserResponse;
    },
  });
}
