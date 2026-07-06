"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import { useAppConfig } from "@/providers/AppConfigProvider";
import { useEffect } from "react";

interface UserPreferences {
  preferred_currency: string;
  preferred_locale: string;
  theme: string;
}

export function useUserPreferences() {
  const { updateConfig } = useAppConfig();

  const hasToken =
    typeof window !== "undefined" && !!localStorage.getItem("jwt_token");

  const query = useQuery({
    queryKey: queryKeys.userPreferences(),
    queryFn: async () => {
      const res = await api.get("/api/users/me/preferences");
      return res.data as UserPreferences;
    },
    enabled: hasToken,
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (query.data) {
      updateConfig({
        currency: query.data.preferred_currency,
        locale: query.data.preferred_locale,
      });
    }
  }, [query.data, updateConfig]);

  return { preferences: query.data, isLoading: query.isLoading, error: query.error };
}
