'use client';

import { Sun, Moon, Monitor } from 'lucide-react';
import { useAppConfig } from '@/providers/AppConfigProvider';
import { useEffect, useCallback, useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { PreferencesUpdatePayload } from '@/types/api';

type Theme = 'dark' | 'light' | 'system';

const THEMES: Theme[] = ['dark', 'light', 'system'];

const THEME_ICONS: Record<Theme, typeof Sun> = {
  dark: Moon,
  light: Sun,
  system: Monitor,
};

const THEME_LABELS: Record<Theme, string> = {
  dark: 'Oscuro',
  light: 'Claro',
  system: 'Sistema',
};

function getSystemTheme(): 'dark' | 'light' {
  if (typeof window === 'undefined') return 'dark';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function resolveTheme(theme: Theme): 'dark' | 'light' {
  return theme === 'system' ? getSystemTheme() : theme;
}

export default function ThemeToggle() {
  const { config, updateConfig } = useAppConfig();
  const theme = (config.theme as Theme) ?? 'dark';
  const initialised = useRef(false);
  const prevTheme = useRef(theme);
  const queryClient = useQueryClient();

  const patchTheme = useMutation({
    mutationFn: async (body: PreferencesUpdatePayload) => {
      await api.patch('/api/users/me/preferences', body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.userPreferences() });
    },
  });

  const applyTheme = useCallback((t: Theme) => {
    document.documentElement.setAttribute('data-theme', resolveTheme(t));
  }, []);

  useEffect(() => {
    if (initialised.current) return;
    initialised.current = true;

    const saved = localStorage.getItem('oikos_theme') as Theme | null;
    if (saved) {
      updateConfig({ theme: saved });
    } else {
      applyTheme(theme);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!initialised.current) return;
    applyTheme(theme);
    localStorage.setItem('oikos_theme', theme);
  }, [theme, applyTheme]);

  useEffect(() => {
    if (theme !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => applyTheme('system');
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [theme, applyTheme]);

  const cycleTheme = () => {
    const idx = THEMES.indexOf(theme);
    const next = THEMES[(idx + 1) % THEMES.length];
    updateConfig({ theme: next });
    prevTheme.current = next;
    localStorage.setItem('oikos_theme', next);
    applyTheme(next);
    if (typeof window !== 'undefined' && localStorage.getItem('jwt_token')) {
      patchTheme.mutate({ preferred_theme: next });
    }
  };

  const Icon = THEME_ICONS[theme];

  return (
    <button
      onClick={cycleTheme}
      className="text-text-muted hover:text-text cursor-pointer rounded-lg p-1.5 transition-colors"
      title={`Tema: ${THEME_LABELS[theme]}`}
    >
      <Icon size={16} />
    </button>
  );
}
