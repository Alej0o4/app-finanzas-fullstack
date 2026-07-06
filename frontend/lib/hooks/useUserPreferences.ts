"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAppConfig } from "@/providers/AppConfigProvider";

interface UserPreferences {
  preferred_currency: string;
  preferred_locale: string;
  theme: string;
}

export function useUserPreferences() {
  const { updateConfig } = useAppConfig();
  const [preferences, setPreferences] = useState<UserPreferences | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const token =
      typeof window !== "undefined" ? localStorage.getItem("jwt_token") : null;

    if (!token) {
      setIsLoading(false);
      return;
    }

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
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [updateConfig]);

  return { preferences, isLoading, error };
}
