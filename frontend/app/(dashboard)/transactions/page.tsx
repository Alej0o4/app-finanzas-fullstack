"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, ArrowRightLeft, ArrowDownRight, ArrowUpRight, Loader2, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";

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

  // Estados del formulario
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [type, setType] = useState("expense"); // Por defecto, es más común registrar gastos
  const [date, setDate] = useState(new Date().toISOString().split("T")[0]); // Fecha de hoy
  const [accountId, setAccountId] = useState("");
  const [categoryId, setCategoryId] = useState("");

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

  // UX: Filtramos las categorías para mostrar solo las que coincidan con el tipo de transacción (Ingreso/Gasto)
  const filteredCategories = categories?.filter(c => c.type === type) || [];

  // 3. POST: Crear Transacción
  const createMutation = useMutation({
    mutationFn: async (newTx: any) => {
      const response = await api.post("/api/transactions/", newTx);
      return response.data;
    },
    onSuccess: () => {
      // MAGIA REACTIVA: Actualizamos la lista actual, pero también forzamos 
      // a que las cuentas y el dashboard se recalculen con el nuevo saldo.
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      queryClient.invalidateQueries({ queryKey: ["dashboardSummary"] });
      
      setIsModalOpen(false);
      setDescription("");
      setAmount("");
      setAccountId("");
      setCategoryId("");
    },
    onError: (error: any) => alert(error.response?.data?.detail || "Error al registrar transacción")
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
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate({
      description,
      amount: Number(amount),
      type,
      date,
      account_id: Number(accountId),
      category_id: Number(categoryId)
    });
  };

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
      <div className="bg-surface border border-neutral-800/60 rounded-3xl overflow-hidden shadow-sm">
        {(!transactions || transactions.length === 0) ? (
          <div className="p-12 text-center flex flex-col items-center text-text-muted">
            <ArrowRightLeft size={48} className="mb-4 opacity-20" />
            <p>Aún no tienes movimientos registrados.</p>
          </div>
        ) : (
          <div className="divide-y divide-neutral-800/40">
            {transactions.map((tx) => {
              const isExpense = tx.type === "expense";
              const account = accounts?.find(a => a.id === tx.account_id);
              const category = categories?.find(c => c.id === tx.category_id);

              return (
                <div key={tx.id} className="p-4 sm:px-6 hover:bg-neutral-800/30 transition-colors flex items-center justify-between group">
                  <div className="flex items-center space-x-4">
                    <div className={`p-2.5 rounded-full bg-background border border-neutral-800/50 ${isExpense ? 'text-text-muted' : 'text-primary'}`}>
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

      {/* Modal CREAR */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-surface border border-neutral-800/60 rounded-3xl p-6 w-full max-w-md shadow-2xl">
            <h2 className="text-xl font-bold mb-4 font-sans text-text">Registrar movimiento</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              
              <div className="flex gap-4">
                <button type="button" onClick={() => setType("expense")} className={`flex-1 py-2 rounded-xl text-sm font-medium transition-colors border ${type === "expense" ? "bg-background border-neutral-700 text-text" : "border-transparent text-text-muted hover:text-text"}`}>Gasto</button>
                <button type="button" onClick={() => setType("income")} className={`flex-1 py-2 rounded-xl text-sm font-medium transition-colors border ${type === "income" ? "bg-primary/10 border-primary/20 text-primary" : "border-transparent text-text-muted hover:text-text"}`}>Ingreso</button>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Valor</label>
                <input type="number" required value={amount} onChange={(e) => setAmount(e.target.value)} className="w-full bg-background border border-neutral-800/60 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all" placeholder="0" />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Descripción</label>
                <input required value={description} onChange={(e) => setDescription(e.target.value)} className="w-full bg-background border border-neutral-800/60 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all" placeholder="Ej. Almuerzo il forno..." />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Cuenta</label>
                  <select required value={accountId} onChange={(e) => setAccountId(e.target.value)} className="w-full bg-background border border-neutral-800/60 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none">
                    <option value="" disabled>Selecciona...</option>
                    {accounts?.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Categoría</label>
                  <select required value={categoryId} onChange={(e) => setCategoryId(e.target.value)} className="w-full bg-background border border-neutral-800/60 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none">
                    <option value="" disabled>Selecciona...</option>
                    {filteredCategories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Fecha</label>
                <input type="date" required value={date} onChange={(e) => setDate(e.target.value)} className="w-full bg-background border border-neutral-800/60 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all" />
              </div>

              <div className="flex gap-3 mt-6">
                <button type="button" onClick={() => setIsModalOpen(false)} className="flex-1 px-4 py-2.5 rounded-xl border border-neutral-800/60 text-text-muted hover:text-text hover:bg-neutral-800 transition-colors text-sm font-medium">Cancelar</button>
                <button type="submit" disabled={createMutation.isPending} className="flex-1 px-4 py-2.5 rounded-xl bg-primary hover:bg-primary-dark text-background transition-colors text-sm font-medium flex justify-center items-center cursor-pointer">
                  {createMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : "Guardar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}