"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
// Importamos los nuevos iconos (Edit2 y Trash2)
import { Plus, Wallet, Loader2, Edit2, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import Link from "next/link";

interface Account {
  id: number;
  name: string;
  type: string; 
  balance: number;
}

const accountTypeTranslations: Record<string, string> = {
  cash: "Efectivo",
  debit: "Débito",
  credit: "Crédito",
};

export default function AccountsPage() {
  const queryClient = useQueryClient();
  
  // Estados para Crear
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newAccountName, setNewAccountName] = useState("");
  const [newAccountType, setNewAccountType] = useState("cash");
  const [initialBalance, setInitialBalance] = useState(""); 

  // Estados para Editar
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [editAccountName, setEditAccountName] = useState("");
  const [editAccountType, setEditAccountType] = useState("cash");

  // GET: Obtener cuentas
  const { data: accounts, isLoading } = useQuery<Account[]>({
    queryKey: ["accounts"],
    queryFn: async () => {
      const response = await api.get("/api/accounts/");
      return response.data;
    },
  });

  // POST: Crear cuenta
  const createAccountMutation = useMutation({
    mutationFn: async (newAccount: { name: string; type: string; balance: number }) => {
      const response = await api.post("/api/accounts/", newAccount);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      queryClient.invalidateQueries({ queryKey: ["dashboardSummary"] });
      setIsCreateModalOpen(false);
      setNewAccountName("");
      setNewAccountType("cash");
      setInitialBalance("");
    },
    onError: (error: any) => alert(error.response?.data?.detail || "Error al crear la cuenta")
  });

  // PUT: Editar cuenta (¡SIN ENVIAR BALANCE!)
  const updateAccountMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: { name: string; type: string } }) => {
      const response = await api.put(`/api/accounts/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      setEditingAccount(null); // Cierra el modal
    },
    onError: (error: any) => alert(error.response?.data?.detail || "Error al actualizar")
  });

  // DELETE: Eliminar cuenta
  const deleteAccountMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.delete(`/api/accounts/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      queryClient.invalidateQueries({ queryKey: ["dashboardSummary"] });
    },
    onError: (error: any) => {
      // Manejo del error 400 por relaciones bloqueadas
      alert(error.response?.data?.detail || "No se puede eliminar esta cuenta. Verifica que no tenga transacciones asociadas.");
    }
  });

  // Handlers
  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    createAccountMutation.mutate({
      name: newAccountName,
      type: newAccountType,
      balance: Number(initialBalance) || 0,
    });
  };

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingAccount) return;
    updateAccountMutation.mutate({
      id: editingAccount.id,
      data: { name: editAccountName, type: editAccountType }, // Estricto: sin balance
    });
  };

  const handleDelete = (id: number, name: string) => {
    // Para no borrar accidentalmente, usamos el confirm nativo del navegador por ahora
    if (window.confirm(`¿Estás seguro de que deseas eliminar la cuenta "${name}"? Esta acción no se puede deshacer.`)) {
      deleteAccountMutation.mutate(id);
    }
  };

  const openEditModal = (account: Account) => {
    setEditAccountName(account.name);
    setEditAccountType(account.type);
    setEditingAccount(account);
  };

  if (isLoading) return <div className="p-8 text-text-muted flex items-center gap-2"><Loader2 className="animate-spin" /> Cargando cuentas...</div>;

  return (
    <div className="space-y-6 relative">
      {/* Encabezado */}
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

      {/* Grid de Cuentas */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {accounts?.map((account) => (
          <div key={account.id} className="bg-surface border border-border/70 rounded-2xl p-5 hover:border-primary/30 transition-colors group relative">
            
            {/* 1. Área clickeable para navegar al detalle de la cuenta */}
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
                  {formatCurrency(account.balance)}
                </p>
              </div>
            </Link>

            {/* 2. Botones de acción flotantes (Con stopPropagation para no navegar al editar) */}
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

      {/* Modal para CREAR */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-surface border border-border/70 rounded-3xl p-6 w-full max-w-md shadow-2xl">
            <h2 className="text-xl font-bold mb-4 font-sans text-text">Añadir nueva cuenta</h2>
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
                <button type="button" onClick={() => setIsCreateModalOpen(false)} className="flex-1 px-4 py-2.5 rounded-xl border border-border/70 text-text-muted hover:text-text hover:bg-surface-elevated transition-colors text-sm font-medium">Cancelar</button>
                <button type="submit" disabled={createAccountMutation.isPending} className="flex-1 px-4 py-2.5 rounded-xl bg-primary hover:bg-primary-dark text-background transition-colors text-sm font-medium flex justify-center items-center cursor-pointer disabled:opacity-70">
                  {createAccountMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : "Guardar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal para EDITAR */}
      {editingAccount && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-surface border border-border/70 rounded-3xl p-6 w-full max-w-md shadow-2xl">
            <h2 className="text-xl font-bold mb-4 font-sans text-text">Editar cuenta</h2>
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

              {/* Fíjate cómo NO existe el campo de saldo aquí */}
              <div className="p-3 bg-surface-elevated/70 rounded-xl border border-border/50 mt-4">
                <p className="text-xs text-text-muted text-center">El saldo no se puede editar manualmente. Modifícalo a través de las transacciones.</p>
              </div>

              <div className="flex gap-3 mt-6">
                <button type="button" onClick={() => setEditingAccount(null)} className="flex-1 px-4 py-2.5 rounded-xl border border-border/70 text-text-muted hover:text-text hover:bg-surface-elevated transition-colors text-sm font-medium">Cancelar</button>
                <button type="submit" disabled={updateAccountMutation.isPending} className="flex-1 px-4 py-2.5 rounded-xl bg-primary hover:bg-primary-dark text-background transition-colors text-sm font-medium flex justify-center items-center cursor-pointer disabled:opacity-70">
                  {updateAccountMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : "Actualizar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}