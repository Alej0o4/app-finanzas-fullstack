"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/api";

interface Account {
  id: number;
  name: string;
}

interface Category {
  id: number;
  name: string;
  type: string;
}

interface TransactionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  defaultType?: "income" | "expense";
  title?: string;
}

const todayAsInputValue = () => new Date().toISOString().split("T")[0];

export default function TransactionModal({
  isOpen,
  onClose,
  onSuccess,
  defaultType = "expense",
  title = "Registrar movimiento",
}: TransactionModalProps) {
  const queryClient = useQueryClient();

  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [type, setType] = useState<"income" | "expense">(defaultType);
  const [date, setDate] = useState(todayAsInputValue());
  const [accountId, setAccountId] = useState("");
  const [categoryId, setCategoryId] = useState("");

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    setType(defaultType);
    setDate(todayAsInputValue());
    setDescription("");
    setAmount("");
    setAccountId("");
    setCategoryId("");
  }, [defaultType, isOpen]);

  const { data: accounts } = useQuery<Account[]>({
    queryKey: ["accounts"],
    queryFn: async () => (await api.get("/api/accounts/")).data,
    enabled: isOpen,
  });

  const { data: categories } = useQuery<Category[]>({
    queryKey: ["categories"],
    queryFn: async () => (await api.get("/api/categories/")).data,
    enabled: isOpen,
  });

  const filteredCategories = useMemo(
    () => categories?.filter((category) => category.type === type) || [],
    [categories, type]
  );

  const createMutation = useMutation({
    mutationFn: async (newTx: any) => {
      const response = await api.post("/api/transactions/", newTx);
      return response.data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["transactions"] }),
        queryClient.invalidateQueries({ queryKey: ["recent-transactions"] }),
        queryClient.invalidateQueries({ queryKey: ["accounts"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboardSummary"] }),
        queryClient.invalidateQueries({ queryKey: ["budgets-progress"] }),
      ]);

      onSuccess?.();
      onClose();
    },
    onError: (error: any) => alert(error.response?.data?.detail || "Error al registrar transacción"),
  });

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();

    createMutation.mutate({
      description,
      amount: Number(amount),
      type,
      date,
      account_id: Number(accountId),
      category_id: Number(categoryId),
    });
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="bg-surface border border-border/70 rounded-3xl p-6 w-full max-w-md shadow-2xl">
        <h2 className="text-xl font-bold mb-4 font-sans text-text">{title}</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex gap-4">
            <button
              type="button"
              onClick={() => setType("expense")}
              className={`flex-1 py-2 rounded-xl text-sm font-medium transition-colors border ${
                type === "expense"
                  ? "bg-background border-border text-text"
                  : "border-transparent text-text-muted hover:text-text"
              }`}
            >
              Gasto
            </button>
            <button
              type="button"
              onClick={() => setType("income")}
              className={`flex-1 py-2 rounded-xl text-sm font-medium transition-colors border ${
                type === "income"
                  ? "bg-primary/15 border-primary/30 text-primary"
                  : "border-transparent text-text-muted hover:text-text"
              }`}
            >
              Ingreso
            </button>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Valor</label>
            <input
              type="number"
              required
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
              placeholder="0"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Descripción</label>
            <input
              required
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
              placeholder="Ej. Almuerzo il forno..."
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Cuenta</label>
              <select
                required
                value={accountId}
                onChange={(event) => setAccountId(event.target.value)}
                className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none"
              >
                <option value="" disabled>Selecciona...</option>
                {accounts?.map((account) => (
                  <option key={account.id} value={account.id}>{account.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Categoría</label>
              <select
                required
                value={categoryId}
                onChange={(event) => setCategoryId(event.target.value)}
                className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none"
              >
                <option value="" disabled>Selecciona...</option>
                {filteredCategories.map((category) => (
                  <option key={category.id} value={category.id}>{category.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Fecha</label>
            <input
              type="date"
              required
              value={date}
              onChange={(event) => setDate(event.target.value)}
              className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
            />
          </div>

          <div className="flex gap-3 mt-6">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 rounded-xl border border-border/70 text-text-muted hover:text-text hover:bg-surface-elevated transition-colors text-sm font-medium"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="flex-1 px-4 py-2.5 rounded-xl bg-primary hover:bg-primary-dark text-background transition-colors text-sm font-medium flex justify-center items-center cursor-pointer"
            >
              {createMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : "Guardar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}