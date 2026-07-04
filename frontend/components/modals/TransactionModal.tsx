"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import { getApiError } from "@/lib/utils";
import ModalShell from "@/components/ui/ModalShell";
import Button from "@/components/ui/Button";
import type { Account, Category, CreateTransactionPayload } from "@/types/api";

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
  const [showAllCategories, setShowAllCategories] = useState(false);

  const { data: accounts } = useQuery<Account[]>({
    queryKey: queryKeys.accounts.all(),
    queryFn: async () => (await api.get("/api/accounts/")).data,
    enabled: isOpen,
  });

  const { data: categories } = useQuery<Category[]>({
    queryKey: queryKeys.categories.all(),
    queryFn: async () => (await api.get("/api/categories/")).data,
    enabled: isOpen,
  });

  const displayedCategories = useMemo(
    () => {
      if (showAllCategories) return categories || [];
      return categories?.filter((category) => category.type === type) || [];
    },
    [categories, type, showAllCategories]
  );

  const createMutation = useMutation({
    mutationFn: async (newTx: CreateTransactionPayload) => {
      const response = await api.post("/api/transactions/", newTx);
      return response.data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.transactions.all() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.recentTransactions() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.budgets.progress() }),
      ]);

      toast.success("Transacción creada correctamente");
      onSuccess?.();
      onClose();
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
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

  return (
    <ModalShell isOpen={isOpen} onClose={onClose} title={title}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex gap-4">
          <button
            type="button"
            onClick={() => setType("expense")}
            className={`flex-1 py-2 rounded-xl text-sm font-medium transition-colors border cursor-pointer ${
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
            className={`flex-1 py-2 rounded-xl text-sm font-medium transition-colors border cursor-pointer ${
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
              {displayedCategories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}{showAllCategories ? ` (${category.type === "income" ? "Ingreso" : "Gasto"})` : ""}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setShowAllCategories(!showAllCategories)}
              className="text-xs text-primary/70 hover:text-primary mt-1 transition-colors"
            >
              {showAllCategories ? "← Solo del tipo" : "+ Mostrar todas las categorías"}
            </button>
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
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            className="flex-1"
          >
            Cancelar
          </Button>
          <Button
            type="submit"
            variant="primary"
            loading={createMutation.isPending}
            className="flex-1"
          >
            Guardar
          </Button>
        </div>
      </form>
    </ModalShell>
  );
}
