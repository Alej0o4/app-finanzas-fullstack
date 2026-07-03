"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Wallet, Loader2, ArrowDownRight, ArrowUpRight, Pencil, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { useConfirmStore } from "@/store/useConfirmStore";
import { useState } from "react";

interface Account {
  id: number;
  name: string;
  type: string;
  balance: number;
}

interface Transaction {
  id: number;
  description: string;
  amount: number;
  type: string;
  date: string;
  account_id: number;
  category_id: number;
}

interface Category {
  id: number;
  name: string;
  type: string;
}

export default function AccountDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedTransaction, setSelectedTransaction] = useState<Transaction | null>(null);
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [type, setType] = useState("expense");
  const [transactionDate, setTransactionDate] = useState(new Date().toISOString().split("T")[0]);
  const [accountId, setAccountId] = useState(String(id));
  const [categoryId, setCategoryId] = useState("");

  // 1. Obtener detalles específicos de la cuenta
  const { data: account, isLoading: loadingAccount } = useQuery<Account>({
    queryKey: ["account", id],
    queryFn: async () => (await api.get(`/api/accounts/${id}`)).data,
  });

  // 2. Obtener transacciones filtradas por cuenta (pasando el query parameter al backend)
  const { data: transactions, isLoading: loadingTx } = useQuery<Transaction[]>({
    queryKey: ["transactions", "account", id],
    queryFn: async () => (await api.get(`/api/transactions/?account_id=${id}`)).data,
  });

  // 3. Traer categorías para cruzar los nombres en la lista
  const { data: categories } = useQuery<Category[]>({
    queryKey: ["categories"],
    queryFn: async () => (await api.get("/api/categories/")).data,
  });
  const { data: allAccounts } = useQuery<Account[]>({
    queryKey: ["accounts"],
    queryFn: async () => (await api.get("/api/accounts/")).data,
  });

  const accountOptions: Account[] = allAccounts || (account ? [account] : []);

  const filteredCategories = categories?.filter(c => c.type === type) || [];

  interface UpdateTransactionPayload {
    id: number;
    description: string;
    amount: number;
    type: string;
    date: string;
    account_id: number;
    category_id: number;
  }

  const updateMutation = useMutation({
    mutationFn: async (payload: UpdateTransactionPayload) => {
      const response = await api.put(`/api/transactions/${payload.id}`, payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["transactions", "account", id] });
      queryClient.invalidateQueries({ queryKey: ["account", id] });
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      queryClient.invalidateQueries({ queryKey: ["dashboardSummary"] });
      queryClient.invalidateQueries({ queryKey: ["budgets-progress"] });
      setIsModalOpen(false);
      setSelectedTransaction(null);
    }
  });

  const deleteMutation = useMutation({
    mutationFn: async (txId: number) => {
      await api.delete(`/api/transactions/${txId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["transactions", "account", id] });
      queryClient.invalidateQueries({ queryKey: ["account", id] });
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      queryClient.invalidateQueries({ queryKey: ["dashboardSummary"] });
      queryClient.invalidateQueries({ queryKey: ["budgets-progress"] });
    }
  });

  const openEditModal = (tx: Transaction) => {
    setSelectedTransaction(tx);
    setDescription(tx.description || "");
    setAmount(String(tx.amount));
    setType(tx.type);
    setTransactionDate(tx.date ? tx.date.split("T")[0] : new Date().toISOString().split("T")[0]);
    setAccountId(String(tx.account_id));
    setCategoryId(String(tx.category_id));
    setIsModalOpen(true);
  };

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTransaction) return;

    updateMutation.mutate({
      id: selectedTransaction.id,
      description,
      amount: Number(amount),
      type,
      date: transactionDate,
      account_id: Number(accountId),
      category_id: Number(categoryId)
    });
  };

  const isLoading = loadingAccount || loadingTx;

  if (isLoading) return <div className="p-8 text-text-muted flex items-center gap-2"><Loader2 className="animate-spin" /> Cargando historial de cuenta...</div>;
  if (!account) return <div className="p-8 text-text-muted">No se encontró la cuenta especificada.</div>;

  return (
    <div className="space-y-8">
      {/* Botón de regreso y Encabezado de la cuenta */}
      <div className="flex items-center space-x-4">
        <button 
          onClick={() => router.back()}
          className="p-2 bg-surface hover:bg-surface-elevated border border-border/70 text-text-muted hover:text-text rounded-xl transition-colors cursor-pointer"
        >
          <ArrowLeft size={18} />
        </button>
        <div>
          <div className="flex items-center space-x-2 text-text-muted text-xs uppercase tracking-wider">
            <Wallet size={12} />
            <span>Detalle de cuenta</span>
          </div>
          <h1 className="text-2xl font-bold font-sans text-text mt-0.5">{account.name}</h1>
        </div>
      </div>

      {/* Tarjeta de Saldo Destacada */}
      <div className="p-6 bg-surface border border-border/70 rounded-3xl max-w-sm">
        <p className="text-xs font-medium text-text-muted uppercase tracking-wider">Saldo disponible</p>
        <p className="text-4xl font-bold text-text mt-2 font-sans">
          {formatCurrency(account.balance)}
        </p>
      </div>

      {/* Historial de transacciones de esta cuenta */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold font-sans text-text">Historial de movimientos</h2>
        
        <div className="bg-surface border border-border/70 rounded-3xl overflow-hidden shadow-sm">
          {(!transactions || transactions.length === 0) ? (
            <div className="p-12 text-center text-text-muted text-sm">
              No hay transacciones registradas con esta cuenta.
            </div>
          ) : (
            <div className="divide-y divide-border/40">
              {transactions.map((tx) => {
                const isExpense = tx.type === "expense";
                const category = categories?.find(c => c.id === tx.category_id);

                return (
                  <div key={tx.id} className="group p-4 sm:px-6 hover:bg-surface-elevated transition-colors flex items-center justify-between gap-4">
                    <div className="flex items-center space-x-4">
                      <div className={`p-2.5 rounded-full bg-background border border-border/60 ${isExpense ? 'text-text-muted' : 'text-primary'}`}>
                        {isExpense ? <ArrowDownRight size={18} /> : <ArrowUpRight size={18} />}
                      </div>
                      <div>
                        <p className="font-medium text-text text-sm">{tx.description}</p>
                        <p className="text-xs text-text-muted mt-0.5">{category?.name || "Sin categoría"}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <p className={`font-semibold font-sans ${isExpense ? 'text-text' : 'text-primary'}`}>
                          {isExpense ? "-" : "+"}{formatCurrency(tx.amount)}
                        </p>
                        <p className="text-[11px] text-text-muted capitalize">{formatDate(tx.date)}</p>
                      </div>
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => openEditModal(tx)}
                          className="p-2 rounded-lg text-text-muted hover:text-text hover:bg-surface-elevated transition-colors"
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          onClick={() => useConfirmStore.getState().confirm("¿Borrar esta transacción?", () => deleteMutation.mutate(tx.id))}
                          className="p-2 rounded-lg text-text-muted hover:text-danger hover:bg-surface-elevated transition-colors"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {isModalOpen && selectedTransaction && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-surface border border-border/70 rounded-3xl p-6 w-full max-w-md shadow-2xl">
            <h2 className="text-xl font-bold mb-4 font-sans text-text">Editar movimiento</h2>
            <form onSubmit={handleUpdate} className="space-y-4">
              <div className="flex gap-4">
                <button type="button" onClick={() => setType("expense")} className={`flex-1 py-2 rounded-xl text-sm font-medium transition-colors border ${type === "expense" ? "bg-background border-border text-text" : "border-transparent text-text-muted hover:text-text"}`}>Gasto</button>
                <button type="button" onClick={() => setType("income")} className={`flex-1 py-2 rounded-xl text-sm font-medium transition-colors border ${type === "income" ? "bg-primary/10 border-primary/20 text-primary" : "border-transparent text-text-muted hover:text-text"}`}>Ingreso</button>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Valor</label>
                <input type="number" required value={amount} onChange={(e) => setAmount(e.target.value)} className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all" />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Descripción</label>
                <input required value={description} onChange={(e) => setDescription(e.target.value)} className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all" />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Cuenta</label>
                  <select required value={accountId} onChange={(e) => setAccountId(e.target.value)} className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none">
                    <option value="" disabled>Selecciona...</option>
                    {accountOptions.map((a) => (
                      <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Categoría</label>
                  <select required value={categoryId} onChange={(e) => setCategoryId(e.target.value)} className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none">
                    <option value="" disabled>Selecciona...</option>
                    {filteredCategories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Fecha</label>
                <input type="date" required value={transactionDate} onChange={(e) => setTransactionDate(e.target.value)} className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all" />
              </div>

              <div className="flex gap-3 mt-6">
                <button type="button" onClick={() => setIsModalOpen(false)} className="flex-1 px-4 py-2.5 rounded-xl border border-border/70 text-text-muted hover:text-text hover:bg-surface-elevated transition-colors text-sm font-medium">Cancelar</button>
                <button type="submit" disabled={updateMutation.isPending} className="flex-1 px-4 py-2.5 rounded-xl bg-primary hover:bg-primary-dark text-background transition-colors text-sm font-medium flex justify-center items-center cursor-pointer">
                  {updateMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : "Guardar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}