"use client";

import { useUserPreferences } from "@/lib/hooks/useUserPreferences";

export function UserPreferencesSync() {
  useUserPreferences();
  return null;
}
