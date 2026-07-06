"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAppConfig } from "@/providers/AppConfigProvider";

interface UserPreferences {
  preferred_currency: string;
  preferred_locale: string;
  theme: string;
}

const TOKEN_KEY = "jwt_token";

export function useUserPreferences() {
  const { updateConfig } = useAppConfig();
  const [preferences, setPreferences] = useState<UserPreferences | null>(null);
  const [error, setError] = useState<unknown>(null);

  const token =
    typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;

  useEffect(() => {
    if (!token) return;

    api
      .get("/api/users/me/preferences")
      .then((res) => {
        const data = res.data as UserPreferences;
        setPreferences(data);
        updateConfig({
          currency: data.preferred_currency,
          locale: data.preferred_locale,
          theme: data.theme,
        });
      })
      .catch((err) => {
        setError(err);
      });
  }, [updateConfig, token]);

  return { preferences, isLoading: !!token, error };
}
