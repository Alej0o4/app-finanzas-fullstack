"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, ArrowRightLeft, ArrowDownRight, ArrowUpRight, Loader2, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
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

export default function TransactionsPage() {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);

  // 2. Traer TODA la información necesaria en paralelo
  const { data: transactions, isLoading: loadingTx } = useQuery<Transaction[]>({
    queryKey: ["transactions"],
    queryFn: async () => (await api.get("/api/transactions/")).data,
  });

  const { data: accounts } = useQuery<Account[]>({
    queryKey: ["accounts"],
    queryFn: async () => (await api.get("/api/accounts/")).data,
  });

  const { data: categories } = useQuery<Category[]>({
    queryKey: ["categories"],
    queryFn: async () => (await api.get("/api/categories/")).data,
  });

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
                      onClick={() => window.confirm("¿Borrar esta transacción?") && deleteMutation.mutate(tx.id)}
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