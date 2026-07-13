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

interface QuickTransactionModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultType?: "income" | "expense";
}

const todayAsInputValue = () => new Date().toISOString().split("T")[0];

export default function QuickTransactionModal({
  isOpen,
  onClose,
  defaultType = "expense",
}: QuickTransactionModalProps) {
  const queryClient = useQueryClient();

  const [amount, setAmount] = useState("");
  const [type, setType] = useState<"income" | "expense">(defaultType);
  const [accountId, setAccountId] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [date, setDate] = useState(todayAsInputValue());
  const [description, setDescription] = useState("");

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

  const filteredCategories = useMemo(
    () => categories?.filter((c) => c.type === type) || [],
    [categories, type]
  );

  const effectiveAccountId = accountId || (accounts?.length ? String(accounts[0].id) : "");

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
        queryClient.invalidateQueries({ queryKey: ["analytics-cashflow"] }),
        queryClient.invalidateQueries({ queryKey: ["analytics-categories"] }),
      ]);

      toast.success(type === "expense" ? "Gasto registrado" : "Ingreso registrado");

      setAmount("");
      setCategoryId("");
      setDate(todayAsInputValue());
      setDescription("");
      onClose();
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!effectiveAccountId || !categoryId || !amount) return;

    createMutation.mutate({
      description,
      amount: Number(amount),
      type,
      date,
      account_id: Number(effectiveAccountId),
      category_id: Number(categoryId),
    });
  };

  const handleTypeChange = (newType: "income" | "expense") => {
    setType(newType);
    setCategoryId("");
  };

  const title = type === "expense" ? "Gasto rápido" : "Ingreso rápido";

  return (
    <ModalShell isOpen={isOpen} onClose={onClose} title={title}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => handleTypeChange("expense")}
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
            onClick={() => handleTypeChange("income")}
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
          <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">
            Valor
          </label>
          <input
            type="number"
            required
            autoFocus
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
            placeholder="0"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">
              Cuenta
            </label>
            <select
              required
              value={effectiveAccountId}
              onChange={(event) => setAccountId(event.target.value)}
              className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none"
            >
              <option value="" disabled>Selecciona...</option>
              {accounts?.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name} ({account.currency})
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">
              Categoría
            </label>
            <select
              required
              value={categoryId}
              onChange={(event) => setCategoryId(event.target.value)}
              className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none"
            >
              <option value="" disabled>Selecciona...</option>
              {filteredCategories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">
              Fecha
            </label>
            <input
              type="date"
              required
              value={date}
              onChange={(event) => setDate(event.target.value)}
              className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">
              Descripción
            </label>
            <input
              type="text"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text placeholder-text-muted/50 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
              placeholder="Opcional"
            />
          </div>
        </div>

        <div className="flex gap-3 pt-2">
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
            Registrar
          </Button>
        </div>
      </form>
    </ModalShell>
  );
}
