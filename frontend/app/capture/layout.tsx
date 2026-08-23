'use client';

import Link from 'next/link';
import { LayoutDashboard } from 'lucide-react';
import { useRequireAuth } from '@/lib/hooks/useRequireAuth';

/**
 * Layout minimalista para /capture (Fase 10, Decisión 10.1.3 de
 * docs/specs/fase_10_spec.md): centrado tipo (auth)/layout.tsx, sin Sidebar,
 * FabManager ni ConfirmDialog — la captura no debe distraer ni cargar el
 * chrome del shell autenticado.
 *
 * A diferencia de (auth), esta es una ruta autenticada dentro del flujo normal
 * de uso y no hay sidebar desde donde navegar, así que provee una salida
 * explícita ("Ver dashboard") para salir sin guardar.
 *
 * Sin animaciones propias: prefers-reduced-motion se respeta vía la regla
 * global de globals.css y el foco visible sigue el patrón de Fase 9
 * (focus-visible:ring-2 focus-visible:outline-none, igual que Button.tsx).
 */
export default function CaptureLayout({ children }: { children: React.ReactNode }) {
  useRequireAuth();

  return (
    <div className="bg-background flex min-h-screen flex-col p-4 sm:p-8">
      <header className="flex justify-end">
        <Link
          href="/"
          className="text-text-muted hover:text-text hover:bg-surface-elevated focus-visible:ring-primary/50 flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors duration-200 focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98]"
        >
          <LayoutDashboard size={16} />
          Ver dashboard
        </Link>
      </header>
      <main className="flex w-full flex-1 items-center justify-center">{children}</main>
    </div>
  );
}
