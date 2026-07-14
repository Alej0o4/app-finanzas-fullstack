'use client';

import { useEffect, useCallback } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useUiStore } from '@/store/useUiStore';
import { useCurrentUser } from '@/lib/hooks/useCurrentUser';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import {
  LayoutDashboard,
  TrendingUp,
  Wallet,
  ArrowLeftRight,
  PieChart,
  Tags,
  ChevronLeft,
  ChevronRight,
  LogOut,
  X,
} from 'lucide-react';
import ThemeToggle from '@/components/ThemeToggle';

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { isSidebarOpen, toggleSidebar, closeSidebar } = useUiStore();
  const { data: user } = useCurrentUser();
  const queryClient = useQueryClient();

  const isMobile = useCallback(() => {
    if (typeof window === 'undefined') return false;
    return window.innerWidth < 640;
  }, []);

  useEffect(() => {
    if (isMobile()) closeSidebar();
  }, [pathname, closeSidebar, isMobile]);

  useEffect(() => {
    const handleResize = () => {
      if (!isMobile()) closeSidebar();
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [closeSidebar, isMobile]);

  const handleLogout = async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (refreshToken) {
      try {
        await api.post('/api/auth/logout', { refresh_token: refreshToken });
      } catch {
        // Si falla la revocación, el token expirará solo
      }
    }
    localStorage.removeItem('jwt_token');
    localStorage.removeItem('refresh_token');
    queryClient.clear();
    router.push('/login');
  };

  const navItems = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Analítica', href: '/analytics', icon: TrendingUp },
    { name: 'Cuentas', href: '/accounts', icon: Wallet },
    { name: 'Transacciones', href: '/transactions', icon: ArrowLeftRight },
    { name: 'Presupuestos', href: '/budgets', icon: PieChart },
    { name: 'Categorías', href: '/categories', icon: Tags },
  ];

  return (
    <>
      {/* Backdrop móvil */}
      <div
        className={`bg-background/50 fixed inset-0 z-30 backdrop-blur-sm transition-opacity duration-300 sm:hidden ${
          isSidebarOpen ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
        onClick={closeSidebar}
      />

      <aside
        className={`bg-surface border-border/70 fixed top-0 left-0 z-40 flex h-screen flex-col justify-between border-r transition-all duration-300 ease-in-out ${
          isSidebarOpen ? 'w-64' : 'w-20'
        } ${isSidebarOpen ? 'max-sm:translate-x-0' : 'max-sm:-translate-x-full'}`}
      >
        {/* Parte Superior: Logo / Nombre */}
        <div>
          <div className="border-border/40 flex h-20 items-center justify-between border-b px-6">
            <span
              className={`text-primary font-semibold tracking-wider transition-opacity duration-200 ${isSidebarOpen ? 'opacity-100' : 'hidden opacity-0'}`}
            >
              OIKOS .
            </span>
            <button
              onClick={toggleSidebar}
              className="bg-background hover:bg-surface-elevated border-border/70 text-text-muted hover:text-text cursor-pointer rounded-lg border p-1.5 transition-colors"
            >
              {isSidebarOpen ? (
                <span className="sm:hidden"><X size={16} /></span>
              ) : (
                <ChevronRight size={16} />
              )}
              <span className="hidden sm:block">
                {isSidebarOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
              </span>
            </button>
          </div>

          {/* Navegación Principal */}
          <nav className="mt-6 space-y-1.5 px-3">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => {
                    if (isMobile()) closeSidebar();
                  }}
                  className={`group relative flex items-center space-x-3 rounded-xl px-4 py-3 text-sm font-medium transition-all duration-200 ${
                    isActive
                      ? 'bg-primary text-background shadow-primary/10 font-semibold shadow-lg'
                      : 'text-text-muted hover:text-text hover:bg-surface-elevated'
                  }`}
                >
                  <Icon
                    size={20}
                    className={
                      isActive
                        ? 'text-background'
                        : 'text-text-muted group-hover:text-primary transition-colors'
                    }
                  />
                  <span
                    className={`transition-opacity duration-200 ${isSidebarOpen ? 'opacity-100' : 'hidden opacity-0'}`}
                  >
                    {item.name}
                  </span>

                  {/* Tooltip flotante si el sidebar está colapsado */}
                  {!isSidebarOpen && (
                    <div className="bg-surface-elevated text-text border-border absolute left-24 z-50 origin-left scale-0 rounded-md border px-2.5 py-1.5 font-sans text-xs shadow-xl transition-all duration-150 group-hover:scale-100">
                      {item.name}
                    </div>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Parte Inferior: Perfil / Cerrar Sesión */}
        <div className="border-border/40 border-t p-3">
          {isSidebarOpen ? (
            <div className="bg-background/40 border-border/40 flex items-center justify-between rounded-xl border p-2 px-3">
              <div className="flex items-center space-x-3">
                <div className="bg-surface-elevated border-border text-primary flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-xs font-semibold uppercase">
                  {user?.full_name
                    ?.split(' ')
                    .map((n: string) => n[0])
                    .join('') || 'U'}
                </div>
                <div className="min-w-0 flex flex-col">
                  <span className="text-text truncate text-xs font-medium">
                    {user?.full_name || 'Usuario'}
                  </span>
                  <span className="text-text-muted truncate text-[10px] capitalize">
                    {user?.email || ''}
                  </span>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <ThemeToggle />
                <button
                  onClick={handleLogout}
                  className="text-text-muted hover:text-danger cursor-pointer rounded-lg p-1.5 transition-colors"
                  title="Cerrar sesión"
                >
                  <LogOut size={16} />
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <div className="bg-surface-elevated border-border text-primary flex h-8 w-8 items-center justify-center rounded-full border text-xs font-semibold uppercase">
                {user?.full_name
                  ?.split(' ')
                  .map((n: string) => n[0])
                  .join('') || 'U'}
              </div>
              <ThemeToggle />
              <button
                onClick={handleLogout}
                className="text-text-muted hover:text-danger cursor-pointer rounded-lg p-1.5 transition-colors"
                title="Cerrar sesión"
              >
                <LogOut size={16} />
              </button>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
