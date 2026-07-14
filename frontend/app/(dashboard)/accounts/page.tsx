'use client';

import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Wallet, Loader2, Edit2, Trash2, Star } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { formatCurrency, getApiError } from '@/lib/utils';
import { useConfirmStore } from '@/store/useConfirmStore';
import { useCurrentUser } from '@/lib/hooks/useCurrentUser';
import { queryKeys } from '@/lib/queryKeys';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import ModalShell from '@/components/ui/ModalShell';
import Button from '@/components/ui/Button';
import Link from 'next/link';
import type { Account, CreateAccountPayload } from '@/types/api';

const accountTypeTranslations: Record<string, string> = {
  cash: 'Efectivo',
  debit: 'Débito',
  credit: 'Crédito',
};

export default function AccountsPage() {
  const queryClient = useQueryClient();
  const { data: user } = useCurrentUser();

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newAccountName, setNewAccountName] = useState('');
  const [newAccountType, setNewAccountType] = useState('cash');
  const [newAccountCurrency, setNewAccountCurrency] = useState('COP');
  const [initialBalance, setInitialBalance] = useState('');

  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [editAccountName, setEditAccountName] = useState('');
  const [editAccountType, setEditAccountType] = useState('cash');

  const { data: accounts, isLoading } = useQuery<Account[]>({
    queryKey: queryKeys.accounts.all(),
    queryFn: async () => {
      const response = await api.get('/api/accounts/');
      return response.data;
    },
  });

  const createAccountMutation = useMutation({
    mutationFn: async (newAccount: CreateAccountPayload) => {
      const response = await api.post('/api/accounts/', newAccount);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      toast.success('Cuenta creada correctamente');
      setIsCreateModalOpen(false);
      setNewAccountName('');
      setNewAccountType('cash');
      setNewAccountCurrency('COP');
      setInitialBalance('');
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const updateAccountMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: { name: string; type: string } }) => {
      const response = await api.put(`/api/accounts/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      toast.success('Cuenta actualizada');
      setEditingAccount(null);
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const deleteAccountMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.delete(`/api/accounts/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
      toast.success('Cuenta eliminada');
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const toggleHighlightMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.patch(`/api/accounts/${id}/highlighted`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.summary() });
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    createAccountMutation.mutate({
      name: newAccountName,
      type: newAccountType as 'cash' | 'debit' | 'credit',
      balance: Number(initialBalance) || 0,
      currency: newAccountCurrency,
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
    useConfirmStore
      .getState()
      .confirm(
        `¿Estás seguro de que deseas eliminar la cuenta "${name}"? Esta acción no se puede deshacer.`,
        () => deleteAccountMutation.mutate(id)
      );
  };

  const openEditModal = (account: Account) => {
    setEditAccountName(account.name);
    setEditAccountType(account.type);
    setEditingAccount(account);
  };

  const sortedAccounts = useMemo(() => {
    if (!accounts) return [];
    const pref = user?.preferred_currency || 'COP';
    return [...accounts].sort((a, b) => {
      if (a.highlighted !== b.highlighted) return a.highlighted ? -1 : 1;
      const aKey = a.currency === pref ? 0 : 1;
      const bKey = b.currency === pref ? 0 : 1;
      return aKey - bKey || a.currency.localeCompare(b.currency);
    });
  }, [accounts, user]);

  if (isLoading)
    return (
      <div className="text-text-muted flex items-center gap-2 p-8">
        <Loader2 className="animate-spin" /> Cargando cuentas...
      </div>
    );

  return (
    <div className="relative space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-text font-sans text-xl font-bold sm:text-2xl">Tus Cuentas</h1>
          <p className="text-text-muted text-xs sm:text-sm">Gestiona el origen de tus fondos.</p>
        </div>
        <Button
          variant="primary"
          onClick={() => setIsCreateModalOpen(true)}
          className="shrink-0"
        >
          <Plus size={18} />
          <span className="hidden sm:inline">Nueva Cuenta</span>
          <span className="sm:hidden">Nueva</span>
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {sortedAccounts.map((account) => (
          <div
            key={account.id}
            className="bg-surface border-border/70 hover:border-primary/30 group relative rounded-2xl border p-4 transition-colors sm:p-5"
          >
            <Link href={`/accounts/${account.id}`} className="block cursor-pointer">
              <div className="mb-4 flex items-start justify-between">
                <div className="flex items-center space-x-3">
                  <div className="bg-background text-primary rounded-lg p-2">
                    <Wallet size={20} />
                  </div>
                  <div>
                    <h3 className="text-text font-medium">{account.name}</h3>
                    <p className="text-text-muted text-xs">
                      {accountTypeTranslations[account.type] || account.type}
                    </p>
                  </div>
                </div>
              </div>

              <div className="border-border/40 mt-4 border-t pt-4">
                <p className="text-text font-sans text-xl font-semibold sm:text-2xl">
                  {formatCurrency(account.balance, account.currency)}
                </p>
              </div>
            </Link>

            <div className="bg-surface absolute top-5 right-5 z-10 flex gap-1 rounded-lg pl-2 opacity-100 sm:opacity-0 sm:transition-opacity sm:group-hover:opacity-100">
              <button
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  toggleHighlightMutation.mutate(account.id);
                }}
                className={`p-1 transition-colors ${
                  account.highlighted
                    ? 'text-yellow-400 hover:text-yellow-300'
                    : 'text-text-muted hover:text-yellow-400'
                }`}
                title={account.highlighted ? 'Quitar de destacadas' : 'Marcar como destacada'}
              >
                <Star size={16} fill={account.highlighted ? 'currentColor' : 'none'} />
              </button>
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

      <ModalShell
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Añadir nueva cuenta"
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <Input
            label="Nombre"
            required
            value={newAccountName}
            onChange={(e) => setNewAccountName(e.target.value)}
            className="bg-background"
          />

          <Select
            label="Tipo"
            value={newAccountType}
            onChange={(e) => setNewAccountType(e.target.value)}
            className="bg-background"
          >
            <option value="cash">Efectivo</option>
            <option value="debit">Débito</option>
            <option value="credit">Crédito</option>
          </Select>

          <Select
            label="Moneda"
            value={newAccountCurrency}
            onChange={(e) => setNewAccountCurrency(e.target.value)}
            className="bg-background"
          >
            <option value="COP">COP</option>
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
          </Select>

          <Input
            label="Saldo Inicial"
            type="number"
            required
            value={initialBalance}
            onChange={(e) => setInitialBalance(e.target.value)}
            className="bg-background"
            placeholder="0"
          />

          <div className="mt-6 flex gap-3">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setIsCreateModalOpen(false)}
              className="flex-1"
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              variant="primary"
              loading={createAccountMutation.isPending}
              className="flex-1"
            >
              Guardar
            </Button>
          </div>
        </form>
      </ModalShell>

      <ModalShell
        isOpen={!!editingAccount}
        onClose={() => setEditingAccount(null)}
        title="Editar cuenta"
      >
        {editingAccount && (
          <form onSubmit={handleUpdate} className="space-y-4">
            <Input
              label="Nombre"
              required
              value={editAccountName}
              onChange={(e) => setEditAccountName(e.target.value)}
              className="bg-background"
            />

            <Select
              label="Tipo"
              value={editAccountType}
              onChange={(e) => setEditAccountType(e.target.value)}
              className="bg-background"
            >
              <option value="cash">Efectivo</option>
              <option value="debit">Débito</option>
              <option value="credit">Crédito</option>
            </Select>

            <div className="bg-surface-elevated/70 border-border/50 mt-4 rounded-xl border p-3">
              <p className="text-text-muted text-center text-xs">
                El saldo no se puede editar manualmente. Modifícalo a través de las transacciones.
              </p>
            </div>

            <div className="mt-6 flex gap-3">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setEditingAccount(null)}
                className="flex-1"
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                variant="primary"
                loading={updateAccountMutation.isPending}
                className="flex-1"
              >
                Actualizar
              </Button>
            </div>
          </form>
        )}
      </ModalShell>
    </div>
  );
}
