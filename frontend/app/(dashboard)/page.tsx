"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

// Definimos la estructura exacta que esperamos del backend
interface DashboardSummary {
  total_balance: number;
  monthly_income: number;
  monthly_expense: number;
}

export default function DashboardPage() {
  // Usamos React Query para manejar la petición asíncrona
  const { data, isLoading, isError } = useQuery<DashboardSummary>({
    queryKey: ["dashboardSummary"],
    queryFn: async () => {
      const response = await api.get("/api/dashboard/summary");
      return response.data;
    },
  });

  // Estado 1: Cargando (Mostramos un spinner elegante)
  if (isLoading) {
    return (
      <div className="h-full flex flex-col items-center justify-center space-y-4 mt-20 text-text-muted">
        <Loader2 size={32} className="animate-spin text-primary" />
        <p className="text-sm">Sincronizando tus finanzas...</p>
      </div>
    );
  }

  // Estado 2: Error (Si el backend falla o el token expira)
  if (isError) {
    return (
      <div className="p-6 bg-danger/10 border border-danger/20 rounded-2xl flex items-center space-x-4 text-danger">
        <AlertCircle size={24} />
        <p className="font-medium text-sm">No pudimos cargar el resumen financiero. Intenta recargar la página.</p>
      </div>
    );
  }

  // Estado 3: Éxito (Renderizamos los datos reales)
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight font-sans">Buenas tardes, Alejandro</h1>
        <p className="text-text-muted text-sm mt-1">Aquí tienes el estado actual de tus finanzas orgánicas.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-6 bg-surface border border-neutral-800/40 rounded-2xl shadow-sm transition-transform hover:scale-[1.02] duration-300">
          <p className="text-xs font-medium text-text-muted uppercase tracking-wider">Balance Total</p>
          <p className="text-3xl font-semibold text-text mt-2 font-sans">
            {formatCurrency(data?.total_balance || 0)}
          </p>
        </div>
        
        <div className="p-6 bg-surface border border-neutral-800/40 rounded-2xl shadow-sm transition-transform hover:scale-[1.02] duration-300">
          <p className="text-xs font-medium text-text-muted uppercase tracking-wider">Ingresos del Mes</p>
          <p className="text-3xl font-semibold text-primary mt-2 font-sans">
             {formatCurrency(data?.monthly_income || 0)}
          </p>
        </div>
        
        <div className="p-6 bg-surface border border-neutral-800/40 rounded-2xl shadow-sm transition-transform hover:scale-[1.02] duration-300">
          <p className="text-xs font-medium text-text-muted uppercase tracking-wider">Gastos del Mes</p>
          <p className="text-3xl font-semibold text-text mt-2 font-sans">
             {formatCurrency(data?.monthly_expense || 0)}
          </p>
        </div>
      </div>
    </div>
  );
}