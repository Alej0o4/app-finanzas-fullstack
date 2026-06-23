import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface CurrentUser {
  id: number;
  email: string;
  full_name: string;
}

export function useCurrentUser() {
  return useQuery<CurrentUser>({
    queryKey: ["currentUser"],
    queryFn: async () => {
      const response = await api.get("/api/users/me");
      return response.data;
    },
  });
}