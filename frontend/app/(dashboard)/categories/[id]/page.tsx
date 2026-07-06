"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Tag, Loader2, ArrowDownRight, ArrowUpRight, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { formatCurrency, formatDate, getApiError } from "@/lib/utils";
import { useAppConfig } from "@/providers/AppConfigProvider";
import { useConfirmStore } from "@/store/useConfirmStore";
import { queryKeys } from "@/lib/queryKeys";
import ModalShell from "@/components/ui/ModalShell";
import Button from "@/components/ui/Button";
import { useState } from "react";
import type { Category, Transaction, Account, UpdateTransactionPayload, PaginatedResponse } from "@/types/api";

export default function CategoryDetailPage() {
  const { config } = useAppConfig();
  const { id } = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedTransaction, setSelectedTransaction] = useState<Transaction | null>(null);
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [type, setType] = useState("expense");
  const [transactionDate, setTransactionDate] = useState(new Date().toISOString().split("T")[0]);
  const [accountId, setAccountId] = useState("");
  const [categoryId, setCategoryId] = useState(String(id));

  const { data: category, isLoading: loadingCategory } = useQuery<Category>({
    queryKey: queryKeys.categories.byId(id as string),
    queryFn: async () => (await api.get(`/api/categories/${id}`)).data,
  });

  const { data: transactionsData, isLoading: loadingTx } = useQuery<PaginatedResponse<Transaction>>({
    queryKey: queryKeys.transactions.byCategory(id as string),
    queryFn: async () => (await api.get(`/api/transactions/`, { params: { category_id: Number(id) } })).data,
  });

  const transactions = transactionsData?.items;

  const { data: accounts } = useQuery<Account[]>({
    queryKey: queryKeys.accounts.all(),
    queryFn: async () => (await api.get("/api/accounts/")).data,
  });

  const { data: categories } = useQuery<Category[]>({
    queryKey: queryKeys.categories.all(),
    queryFn: async () => (await api.get("/api/categories/")).data,
  });

  const filteredCategories = categories?.filter(c => c.type === type) || [];

  const updateMutation = useMutation({
    mutationFn: async (payload: UpdateTransactionPayload) => {
      const response = await api.put(`/api/transactions/${payload.id}`, payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.transactions.byCategory(id as string) });
      queryClient.invalidateQueries({ queryKey: queryKeys.categories.byId(id as string) });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() });
      toast.success("Transacción actualizada");
      setIsModalOpen(false);
      setSelectedTransaction(null);
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    }
  });

  const deleteMutation = useMutation({
    mutationFn: async (txId: number) => {
      await api.delete(`/api/transactions/${txId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.transactions.byCategory(id as string) });
      queryClient.invalidateQueries({ queryKey: queryKeys.categories.byId(id as string) });
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() });
      toast.success("Transacción eliminada");
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
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
      type: type as "income" | "expense",
      date: transactionDate,
      account_id: Number(accountId),
      category_id: Number(categoryId)
    });
  };

  const isLoading = loadingCategory || loadingTx;

  if (isLoading) return <div className="p-8 text-text-muted flex items-center gap-2"><Loader2 className="animate-spin" /> Cargando historial de categoría...</div>;
  if (!category) return <div className="p-8 text-text-muted">No se encontró la categoría especificada.</div>;

  const isExpense = category.type === "expense";

  return (
    <div className="space-y-8">
      <div className="flex items-center space-x-4">
        <button
          onClick={() => router.back()}
          className="p-2 bg-surface hover:bg-surface-elevated border border-border/70 text-text-muted hover:text-text rounded-xl transition-colors cursor-pointer"
        >
          <ArrowLeft size={18} />
        </button>
        <div>
          <div className="flex items-center space-x-2 text-text-muted text-xs uppercase tracking-wider">
            <Tag size={12} />
            <span>Detalle de categoría</span>
          </div>
          <h1 className="text-2xl font-bold font-sans text-text mt-0.5">{category.name}</h1>
        </div>
      </div>

      <div className="space-y-4">
        <h2 className="text-lg font-bold font-sans text-text">Movimientos asociados</h2>

        <div className="bg-surface border border-border/70 rounded-3xl overflow-hidden shadow-sm">
          {(!transactions || transactions.length === 0) ? (
            <div className="p-12 text-center text-text-muted text-sm">
              No hay movimientos clasificados en esta categoría aún.
            </div>
          ) : (
            <div className="divide-y divide-border/40">
              {transactions.map((tx) => {
                const account = accounts?.find(a => a.id === tx.account_id);

                return (
                  <div key={tx.id} className="group p-4 sm:px-6 hover:bg-surface-elevated transition-colors flex items-center justify-between gap-4">
                    <div className="flex items-center space-x-4">
                      <div className={`p-2.5 rounded-full bg-background border border-border/60 ${isExpense ? 'text-text-muted' : 'text-primary'}`}>
                        {isExpense ? <ArrowDownRight size={18} /> : <ArrowUpRight size={18} />}
                      </div>
                      <div>
                        <p className="font-medium text-text text-sm">{tx.description}</p>
                        <p className="text-xs text-text-muted mt-0.5">{account?.name || "Cuenta eliminada"}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <p className={`font-semibold font-sans ${isExpense ? 'text-text' : 'text-primary'}`}>
                          {isExpense ? "-" : "+"}{formatCurrency(tx.amount, config.currency)}
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

      <ModalShell isOpen={isModalOpen && !!selectedTransaction} onClose={() => setIsModalOpen(false)} title="Editar movimiento">
        {selectedTransaction && (
          <form onSubmit={handleUpdate} className="space-y-4">
            <div className="flex gap-4">
              <button type="button" onClick={() => setType("expense")} className={`flex-1 py-2 rounded-xl text-sm font-medium transition-colors border cursor-pointer ${type === "expense" ? "bg-background border-border text-text" : "border-transparent text-text-muted hover:text-text"}`}>Gasto</button>
              <button type="button" onClick={() => setType("income")} className={`flex-1 py-2 rounded-xl text-sm font-medium transition-colors border cursor-pointer ${type === "income" ? "bg-primary/10 border-primary/20 text-primary" : "border-transparent text-text-muted hover:text-text"}`}>Ingreso</button>
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
                  {accounts?.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
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
              <Button type="button" variant="ghost" onClick={() => setIsModalOpen(false)} className="flex-1">Cancelar</Button>
              <Button type="submit" variant="primary" loading={updateMutation.isPending} className="flex-1">Guardar</Button>
            </div>
          </form>
        )}
      </ModalShell>
    </div>
  );
}
