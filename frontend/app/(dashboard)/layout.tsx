"use client";

import Sidebar from "@/components/Sidebar";
import { useUiStore } from "@/store/useUiStore";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isSidebarOpen } = useUiStore();

  return (
    <div className="min-h-screen bg-background">
      {/* Componente de Navegación Lateral */}
      <Sidebar />

      {/* Contenedor Principal con margen dinámico según el estado del Sidebar */}
      <div 
        className={`transition-all duration-300 ease-in-out min-h-screen flex flex-col
          ${isSidebarOpen ? "pl-64" : "pl-20"}`}
      >
        <main className="flex-1 p-8 lg:p-12max-w-[1600px] w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}