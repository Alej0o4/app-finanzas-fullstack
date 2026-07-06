"use client";

import React, { createContext, useContext, useState, useCallback, type ReactNode } from "react";

interface AppConfig {
  currency: string;
  locale: string;
  theme: string;
}

interface AppConfigContextType {
  config: AppConfig;
  updateConfig: (partial: Partial<AppConfig>) => void;
}

const defaultConfig: AppConfig = {
  currency: "COP",
  locale: "es-CO",
  theme: "dark",
};

const AppConfigContext = createContext<AppConfigContextType>({
  config: defaultConfig,
  updateConfig: () => {},
});

export function AppConfigProvider({
  children,
  initialPreferences,
}: {
  children: ReactNode;
  initialPreferences?: Partial<AppConfig>;
}) {
  const [config, setConfig] = useState<AppConfig>({
    ...defaultConfig,
    ...initialPreferences,
  });

  const updateConfig = useCallback((partial: Partial<AppConfig>) => {
    setConfig((prev) => ({ ...prev, ...partial }));
  }, []);

  return (
    <AppConfigContext.Provider value={{ config, updateConfig }}>
      {children}
    </AppConfigContext.Provider>
  );
}

export function useAppConfig() {
  return useContext(AppConfigContext);
}
