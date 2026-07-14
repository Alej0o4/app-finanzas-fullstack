'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import FabManager from '@/components/FabManager';
import { useUiStore } from '@/store/useUiStore';
import { Menu } from 'lucide-react';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isSidebarOpen, toggleSidebar, setSidebarOpen } = useUiStore();

  useEffect(() => {
    const token = localStorage.getItem('jwt_token');
    if (!token) {
      router.replace('/login');
    }
  }, [router]);

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
      <Sidebar />
      <ConfirmDialog />
      <FabManager />

      <div
        className={`flex min-h-screen flex-col transition-all duration-300 ease-in-out ${
          isSidebarOpen ? 'sm:pl-64' : 'sm:pl-20'
        }`}
      >
        {/* Hamburger móvil */}
        <button
          onClick={toggleSidebar}
          className="bg-surface border-border/70 text-text-muted hover:text-text fixed top-4 left-4 z-30 cursor-pointer rounded-lg border p-2 shadow-md transition-colors sm:hidden"
          aria-label="Abrir menú"
        >
          <Menu size={20} />
        </button>

        <main className="mx-auto w-full max-w-[1600px] flex-1 p-4 sm:p-8 lg:p-12">{children}</main>
      </div>
    </div>
  );
}
