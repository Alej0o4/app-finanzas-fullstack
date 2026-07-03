"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, ArrowRightLeft, ArrowDownRight, ArrowUpRight, Loader2, Trash2, FilterX } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { useConfirmStore } from "@/store/useConfirmStore";
import TransactionModal from "@/components/modals/TransactionModal";

// 1. Interfaces
interface Account { id: number; name: string; }
interface Category { id: number; name: string; type: string; }
interface Transaction {
  id: number;
  description: string;
  amount: number;
  type: string; // "income" o "expense"
  date: string;
  account_id: number;
  category_id: number;
}

type DatePreset = "all" | "7d" | "month" | "year" | "custom";

const formatDateBoundaryForBackend = (value: string, boundary: "start" | "end") => {
  if (!value) {
    return null;
  }

  return boundary === "start"
    ? `${value}T00:00:00`
    : `${value}T23:59:59`;
};

const getPresetDates = (preset: Exclude<DatePreset, "custom">) => {
  const today = new Date();
  const endDate = today.toISOString().slice(0, 10);

  if (preset === "all") {
    return { startDate: "", endDate: "" };
  }

  if (preset === "7d") {
    const start = new Date(today);
    start.setDate(today.getDate() - 6);
    return { startDate: start.toISOString().slice(0, 10), endDate };
  }

  if (preset === "month") {
    return {
      startDate: `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-01`,
      endDate,
    };
  }

  return {
    startDate: `${today.getFullYear()}-01-01`,
    endDate,
  };
};

export default function TransactionsPage() {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [accountFilter, setAccountFilter] = useState("all");
  const [datePreset, setDatePreset] = useState<DatePreset>("all");

  const startDateParam = formatDateBoundaryForBackend(startDate, "start");
  const endDateParam = formatDateBoundaryForBackend(endDate, "end");

  // 2. Traer TODA la información necesaria en paralelo
  const { data: transactions, isLoading: loadingTx } = useQuery<Transaction[]>({
    queryKey: ["transactions", { startDate: startDateParam, endDate: endDateParam, categoryFilter, accountFilter }],
    queryFn: async () => {
      const params: Record<string, string | number> = {};

      if (startDateParam) {
        params.start_date = startDateParam;
      }

      if (endDateParam) {
        params.end_date = endDateParam;
      }

      if (categoryFilter !== "all") {
        params.category_id = Number(categoryFilter);
      }

      if (accountFilter !== "all") {
        params.account_id = Number(accountFilter);
      }

      return (await api.get("/api/transactions/", { params })).data;
    },
  });

  const { data: accounts } = useQuery<Account[]>({
    queryKey: ["accounts"],
    queryFn: async () => (await api.get("/api/accounts/")).data,
  });

  const { data: categories } = useQuery<Category[]>({
    queryKey: ["categories"],
    queryFn: async () => (await api.get("/api/categories/")).data,
  });

  const applyPreset = (preset: Exclude<DatePreset, "custom">) => {
    const nextDates = getPresetDates(preset);
    setStartDate(nextDates.startDate);
    setEndDate(nextDates.endDate);
    setDatePreset(preset);
  };

  const clearFilters = () => {
    setStartDate("");
    setEndDate("");
    setCategoryFilter("all");
    setAccountFilter("all");
    setDatePreset("all");
  };

  // 4. DELETE: Eliminar Transacción
  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/api/transactions/${id}`);
    },
    onSuccess: () => {
      // Al borrar, también los saldos cambian, así que invalidamos todo
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      queryClient.invalidateQueries({ queryKey: ["dashboardSummary"] });
      queryClient.invalidateQueries({ queryKey: ["budgets-progress"] });
    }
  });

  if (loadingTx) return <div className="p-8 text-text-muted flex items-center gap-2"><Loader2 className="animate-spin" /> Cargando movimientos...</div>;

  return (
    <div className="space-y-6 relative">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold font-sans text-text">Transacciones</h1>
          <p className="text-sm text-text-muted">El registro histórico de tus movimientos.</p>
        </div>
        <button 
          onClick={() => setIsModalOpen(true)}
          className="bg-primary hover:bg-primary-dark text-background font-semibold px-4 py-2 rounded-xl flex items-center space-x-2 transition-colors cursor-pointer"
        >
          <Plus size={18} />
          <span>Nuevo Movimiento</span>
        </button>
      </div>

      <div className="bg-surface border border-border/70 rounded-2xl p-4 sm:p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-medium text-text-soft">
            <FilterX size={16} className="text-text-muted" />
            Filtros de feed
          </div>
          <button
            type="button"
            onClick={clearFilters}
            className="text-sm text-text-muted hover:text-text transition-colors"
          >
            Limpiar filtros
          </button>
        </div>

        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {([
              { key: "all", label: "Todo el histórico" },
              { key: "7d", label: "Últimos 7 días" },
              { key: "month", label: "Este mes" },
              { key: "year", label: "Este año" },
            ] as const).map((preset) => (
              <button
                key={preset.key}
                type="button"
                onClick={() => applyPreset(preset.key)}
                className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
                  datePreset === preset.key
                    ? "border-primary bg-primary/10 text-text"
                    : "border-border/70 bg-background text-text-muted hover:border-primary/60 hover:text-text"
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
            <label className="flex flex-col gap-1.5 text-sm text-text-muted">
              Fecha inicial
              <input
                type="date"
                value={startDate}
                onChange={(event) => {
                  setStartDate(event.target.value);
                  setDatePreset("custom");
                }}
                className="rounded-xl border border-border/70 bg-background px-3 py-2 text-text outline-none transition-colors focus:border-primary"
              />
            </label>

            <label className="flex flex-col gap-1.5 text-sm text-text-muted">
              Fecha final
              <input
                type="date"
                value={endDate}
                onChange={(event) => {
                  setEndDate(event.target.value);
                  setDatePreset("custom");
                }}
                className="rounded-xl border border-border/70 bg-background px-3 py-2 text-text outline-none transition-colors focus:border-primary"
              />
            </label>

            <label className="flex flex-col gap-1.5 text-sm text-text-muted">
              Cuenta
              <select
                value={accountFilter}
                onChange={(event) => setAccountFilter(event.target.value)}
                className="rounded-xl border border-border/70 bg-background px-3 py-2 text-text outline-none transition-colors focus:border-primary"
              >
                <option value="all">Todas las cuentas</option>
                {accounts?.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1.5 text-sm text-text-muted">
              Categoría
              <select
                value={categoryFilter}
                onChange={(event) => setCategoryFilter(event.target.value)}
                className="rounded-xl border border-border/70 bg-background px-3 py-2 text-text outline-none transition-colors focus:border-primary"
              >
                <option value="all">Todas las categorías</option>
                {categories?.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </div>

      {/* Lista de Transacciones */}
      <div className="bg-surface border border-border/70 rounded-3xl overflow-hidden shadow-sm">
        {(!transactions || transactions.length === 0) ? (
          <div className="p-12 text-center flex flex-col items-center text-text-muted">
            <ArrowRightLeft size={48} className="mb-4 opacity-20" />
            <p>Aún no tienes movimientos registrados.</p>
          </div>
        ) : (
          <div className="divide-y divide-border/40">
            {transactions.map((tx) => {
              const isExpense = tx.type === "expense";
              const account = accounts?.find(a => a.id === tx.account_id);
              const category = categories?.find(c => c.id === tx.category_id);

              return (
                <div key={tx.id} className="p-4 sm:px-6 hover:bg-surface-elevated transition-colors flex items-center justify-between group">
                  <div className="flex items-center space-x-4">
                    <div className={`p-2.5 rounded-full bg-background border border-border/60 ${isExpense ? 'text-text-muted' : 'text-primary'}`}>
                      {isExpense ? <ArrowDownRight size={18} /> : <ArrowUpRight size={18} />}
                    </div>
                    <div>
                      <p className="font-medium text-text text-sm">{tx.description}</p>
                      <div className="flex text-xs text-text-muted space-x-2 mt-0.5">
                        <span>{account?.name || "Cuenta eliminada"}</span>
                        <span>•</span>
                        <span>{category?.name || "Sin categoría"}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-6">
                    <div className="text-right">
                      <p className={`font-semibold font-sans ${isExpense ? 'text-text' : 'text-primary'}`}>
                        {isExpense ? "-" : "+"}{formatCurrency(tx.amount)}
                      </p>
                      <p className="text-xs text-text-muted capitalize">{formatDate(tx.date)}</p>
                    </div>
                    <button 
                      onClick={() => useConfirmStore.getState().confirm("¿Borrar esta transacción?", () => deleteMutation.mutate(tx.id))}
                      className="text-text-muted hover:text-danger opacity-0 group-hover:opacity-100 transition-opacity p-1"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <TransactionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={() => queryClient.invalidateQueries({ queryKey: ["transactions"] })}
        title="Registrar movimiento"
        defaultType="expense"
      />
    </div>
  );
}