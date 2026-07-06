"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Wallet, Loader2, Edit2, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { formatCurrency, getApiError } from "@/lib/utils";
import { useAppConfig } from "@/providers/AppConfigProvider";
import { useConfirmStore } from "@/store/useConfirmStore";
import { queryKeys } from "@/lib/queryKeys";
import ModalShell from "@/components/ui/ModalShell";
import Button from "@/components/ui/Button";
import Link from "next/link";
import type { Account, CreateAccountPayload } from "@/types/api";

const accountTypeTranslations: Record<string, string> = {
  cash: "Efectivo",
  debit: "Débito",
  credit: "Crédito",
};

export default function AccountsPage() {
  const { config } = useAppConfig();
  const queryClient = useQueryClient();

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newAccountName, setNewAccountName] = useState("");
  const [newAccountType, setNewAccountType] = useState("cash");
  const [initialBalance, setInitialBalance] = useState("");

  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [editAccountName, setEditAccountName] = useState("");
  const [editAccountType, setEditAccountType] = useState("cash");

  const { data: accounts, isLoading } = useQuery<Account[]>({
    queryKey: queryKeys.accounts.all(),
    queryFn: async () => {
      const response = await api.get("/api/accounts/");
      return response.data;
    },
  });

  const createAccountMutation = useMutation({
    mutationFn: async (newAccount: CreateAccountPayload) => {
      const response = await api.post("/api/accounts/", newAccount);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      toast.success("Cuenta creada correctamente");
      setIsCreateModalOpen(false);
      setNewAccountName("");
      setNewAccountType("cash");
      setInitialBalance("");
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    }
  });

  const updateAccountMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: { name: string; type: string } }) => {
      const response = await api.put(`/api/accounts/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      toast.success("Cuenta actualizada");
      setEditingAccount(null);
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    }
  });

  const deleteAccountMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.delete(`/api/accounts/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      toast.success("Cuenta eliminada");
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    }
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    createAccountMutation.mutate({
      name: newAccountName,
      type: newAccountType as "cash" | "debit" | "credit",
      balance: Number(initialBalance) || 0,
    });
  };

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingAccount) return;
    updateAccountMutation.mutate({
      id: editingAccount.id,
      data: { name: editAccountName, type: editAccountType },
    });
  };

  const handleDelete = (id: number, name: string) => {
    useConfirmStore.getState().confirm(
      `¿Estás seguro de que deseas eliminar la cuenta "${name}"? Esta acción no se puede deshacer.`,
      () => deleteAccountMutation.mutate(id)
    );
  };

  const openEditModal = (account: Account) => {
    setEditAccountName(account.name);
    setEditAccountType(account.type);
    setEditingAccount(account);
  };

  if (isLoading) return <div className="p-8 text-text-muted flex items-center gap-2"><Loader2 className="animate-spin" /> Cargando cuentas...</div>;

  return (
    <div className="space-y-6 relative">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold font-sans text-text">Tus Cuentas</h1>
          <p className="text-sm text-text-muted">Gestiona el origen de tus fondos.</p>
        </div>
        <button
          onClick={() => setIsCreateModalOpen(true)}
          className="bg-primary hover:bg-primary-dark text-background font-semibold px-4 py-2 rounded-xl flex items-center space-x-2 transition-colors cursor-pointer"
        >
          <Plus size={18} />
          <span>Nueva Cuenta</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {accounts?.map((account) => (
          <div key={account.id} className="bg-surface border border-border/70 rounded-2xl p-5 hover:border-primary/30 transition-colors group relative">

            <Link href={`/accounts/${account.id}`} className="block cursor-pointer">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center space-x-3">
                  <div className="p-2 bg-background rounded-lg text-primary">
                    <Wallet size={20} />
                  </div>
                  <div>
                    <h3 className="font-medium text-text">{account.name}</h3>
                    <p className="text-xs text-text-muted">
                      {accountTypeTranslations[account.type] || account.type}
                    </p>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-border/40">
                <p className="text-2xl font-semibold font-sans text-text">
                  {formatCurrency(account.balance, config.currency)}
                </p>
              </div>
            </Link>

            <div className="absolute top-5 right-5 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity bg-surface pl-2 rounded-lg">
              <button
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  openEditModal(account);
                }}
                className="text-text-muted hover:text-primary p-1 transition-colors"
                title="Editar cuenta"
              >
                <Edit2 size={16} />
              </button>
              <button
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  handleDelete(account.id, account.name);
                }}
                className="text-text-muted hover:text-danger p-1 transition-colors"
                title="Eliminar cuenta"
              >
                <Trash2 size={16} />
              </button>
            </div>

          </div>
        ))}
      </div>

      <ModalShell isOpen={isCreateModalOpen} onClose={() => setIsCreateModalOpen(false)} title="Añadir nueva cuenta">
        <form onSubmit={handleCreate} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Nombre</label>
            <input required value={newAccountName} onChange={(e) => setNewAccountName(e.target.value)} className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all" />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Tipo</label>
            <select value={newAccountType} onChange={(e) => setNewAccountType(e.target.value)} className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all appearance-none">
              <option value="cash">Efectivo</option>
              <option value="debit">Débito</option>
              <option value="credit">Crédito</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Saldo Inicial</label>
            <input type="number" required value={initialBalance} onChange={(e) => setInitialBalance(e.target.value)} className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all" placeholder="0" />
          </div>

          <div className="flex gap-3 mt-6">
            <Button type="button" variant="ghost" onClick={() => setIsCreateModalOpen(false)} className="flex-1">Cancelar</Button>
            <Button type="submit" variant="primary" loading={createAccountMutation.isPending} className="flex-1">Guardar</Button>
          </div>
        </form>
      </ModalShell>

      <ModalShell isOpen={!!editingAccount} onClose={() => setEditingAccount(null)} title="Editar cuenta">
        {editingAccount && (
          <form onSubmit={handleUpdate} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Nombre</label>
              <input required value={editAccountName} onChange={(e) => setEditAccountName(e.target.value)} className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all" />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Tipo</label>
              <select value={editAccountType} onChange={(e) => setEditAccountType(e.target.value)} className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all appearance-none">
                <option value="cash">Efectivo</option>
                <option value="debit">Débito</option>
                <option value="credit">Crédito</option>
              </select>
            </div>

            <div className="p-3 bg-surface-elevated/70 rounded-xl border border-border/50 mt-4">
              <p className="text-xs text-text-muted text-center">El saldo no se puede editar manualmente. Modifícalo a través de las transacciones.</p>
            </div>

            <div className="flex gap-3 mt-6">
              <Button type="button" variant="ghost" onClick={() => setEditingAccount(null)} className="flex-1">Cancelar</Button>
              <Button type="submit" variant="primary" loading={updateAccountMutation.isPending} className="flex-1">Actualizar</Button>
            </div>
          </form>
        )}
      </ModalShell>
    </div>
  );
}
