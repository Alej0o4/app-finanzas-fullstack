"use client";

import { Sun, Moon, Monitor } from "lucide-react";
import { useAppConfig } from "@/providers/AppConfigProvider";
import { useEffect, useCallback, useRef } from "react";

type Theme = "dark" | "light" | "system";

const THEMES: Theme[] = ["dark", "light", "system"];

const THEME_ICONS: Record<Theme, typeof Sun> = {
  dark: Moon,
  light: Sun,
  system: Monitor,
};

const THEME_LABELS: Record<Theme, string> = {
  dark: "Oscuro",
  light: "Claro",
  system: "Sistema",
};

function getSystemTheme(): "dark" | "light" {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function resolveTheme(theme: Theme): "dark" | "light" {
  return theme === "system" ? getSystemTheme() : theme;
}

export default function ThemeToggle() {
  const { config, updateConfig } = useAppConfig();
  const theme = (config.theme as Theme) ?? "dark";
  const initialised = useRef(false);

  const applyTheme = useCallback((t: Theme) => {
    document.documentElement.setAttribute("data-theme", resolveTheme(t));
  }, []);

  useEffect(() => {
    if (initialised.current) return;
    initialised.current = true;

    const saved = localStorage.getItem("oikos_theme") as Theme | null;
    if (saved && saved !== theme) {
      updateConfig({ theme: saved });
    } else {
      applyTheme(theme);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!initialised.current) return;
    applyTheme(theme);
    localStorage.setItem("oikos_theme", theme);
  }, [theme, applyTheme]);

  useEffect(() => {
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => applyTheme("system");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme, applyTheme]);

  const cycleTheme = () => {
    const idx = THEMES.indexOf(theme);
    const next = THEMES[(idx + 1) % THEMES.length];
    updateConfig({ theme: next });
  };

  const Icon = THEME_ICONS[theme];

  return (
    <button
      onClick={cycleTheme}
      className="text-text-muted hover:text-text p-1.5 rounded-lg transition-colors cursor-pointer"
      title={`Tema: ${THEME_LABELS[theme]}`}
    >
      <Icon size={16} />
    </button>
  );
}
