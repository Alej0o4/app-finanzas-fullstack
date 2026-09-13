'use client';

import { useEffect } from 'react';
import Sidebar from '@/components/Sidebar';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import FabManager from '@/components/FabManager';
import InstallPrompt from '@/components/InstallPrompt';
import NotificationToastWatcher from '@/components/NotificationToastWatcher';
import { useRequireAuth } from '@/lib/hooks/useRequireAuth';
import { useUiStore } from '@/store/useUiStore';
import { Menu } from 'lucide-react';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { isSidebarOpen, toggleSidebar, setSidebarOpen } = useUiStore();

  useRequireAuth();

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 640px)');
    const handleChange = (e: MediaQueryListEvent | MediaQueryList) => {
      if (e.matches) setSidebarOpen(true);
      else setSidebarOpen(false);
    };
    handleChange(mq);
    mq.addEventListener('change', handleChange);
    return () => mq.removeEventListener('change', handleChange);
  }, [setSidebarOpen]);

  return (
    <div className="bg-background min-h-screen">
      {/* Fase 12 §12.7: único salto útil en el shell autenticado — (auth) y /capture no
          tienen navegación previa que saltar. */}
      <a
        href="#main-content"
        className="bg-primary text-background focus-visible:ring-primary/50 sr-only rounded-lg px-4 py-2 text-sm font-medium focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus-visible:ring-2 focus-visible:outline-none"
      >
        Saltar al contenido principal
      </a>
      <Sidebar />
      <ConfirmDialog />
      <FabManager />
      <InstallPrompt />
      <NotificationToastWatcher />

      <div
        className={`flex min-h-screen flex-col transition-[padding] duration-300 ease-in-out ${
          isSidebarOpen ? 'sm:pl-64' : 'sm:pl-20'
        }`}
      >
        {/* Hamburger móvil */}
        <button
          onClick={toggleSidebar}
          className="bg-surface border-border/70 text-text-muted hover:text-text shadow-background/30 fixed top-4 left-4 z-30 cursor-pointer rounded-lg border p-2 shadow-md transition-colors sm:hidden"
          aria-label="Abrir menú"
        >
          <Menu size={20} />
        </button>

        <main
          id="main-content"
          tabIndex={-1}
          // pt-16/pb-24 en mobile reservan el espacio de los dos FABs fijos (hamburguesa
          // arriba-izquierda, "+" nueva transacción abajo-derecha) para que nunca floten
          // sobre el título de la página ni sobre la última fila de una lista con scroll —
          // el estándar es reservar el hueco en el contenedor, no dejar el FAB flotando
          // sobre contenido que se desplaza debajo.
          className="mx-auto w-full max-w-[1600px] min-w-0 flex-1 overflow-x-hidden p-4 pt-16 pb-24 sm:p-8 lg:p-12"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
