'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import FabManager from '@/components/FabManager';
import { useUiStore } from '@/store/useUiStore';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isSidebarOpen } = useUiStore();

  useEffect(() => {
    const token = localStorage.getItem('jwt_token');
    if (!token) {
      router.replace('/login');
    }
  }, [router]);

  return (
    <div className="bg-background min-h-screen">
      <Sidebar />
      <ConfirmDialog />
      <FabManager />

      <div
        className={`flex min-h-screen flex-col transition-all duration-300 ease-in-out ${isSidebarOpen ? 'pl-64' : 'pl-20'}`}
      >
        <main className="mx-auto w-full max-w-[1600px] flex-1 p-8 lg:p-12">{children}</main>
      </div>
    </div>
  );
}
