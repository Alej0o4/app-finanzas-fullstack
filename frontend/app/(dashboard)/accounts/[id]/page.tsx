"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Wallet, Loader2, ArrowDownRight, ArrowUpRight } from "lucide-react";
import { api } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";

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
  category_id: number;
}

interface Category {
  id: number;
  name: string;
}

export default function AccountDetailPage() {
  const { id } = useParams();
  const router = useRouter();

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

  const isLoading = loadingAccount || loadingTx;

  if (isLoading) return <div className="p-8 text-text-muted flex items-center gap-2"><Loader2 className="animate-spin" /> Cargando historial de cuenta...</div>;
  if (!account) return <div className="p-8 text-text-muted">No se encontró la cuenta especificada.</div>;

  return (
    <div className="space-y-8">
      {/* Botón de regreso y Encabezado de la cuenta */}
      <div className="flex items-center space-x-4">
        <button 
          onClick={() => router.back()}
          className="p-2 bg-surface hover:bg-neutral-800 border border-neutral-800/60 text-text-muted hover:text-text rounded-xl transition-colors cursor-pointer"
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
      <div className="p-6 bg-surface border border-neutral-800/60 rounded-3xl max-w-sm">
        <p className="text-xs font-medium text-text-muted uppercase tracking-wider">Saldo disponible</p>
        <p className="text-4xl font-bold text-text mt-2 font-sans">
          {formatCurrency(account.balance)}
        </p>
      </div>

      {/* Historial de transacciones de esta cuenta */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold font-sans text-text">Historial de movimientos</h2>
        
        <div className="bg-surface border border-neutral-800/60 rounded-3xl overflow-hidden shadow-sm">
          {(!transactions || transactions.length === 0) ? (
            <div className="p-12 text-center text-text-muted text-sm">
              No hay transacciones registradas con esta cuenta.
            </div>
          ) : (
            <div className="divide-y divide-neutral-800/40">
              {transactions.map((tx) => {
                const isExpense = tx.type === "expense";
                const category = categories?.find(c => c.id === tx.category_id);

                return (
                  <div key={tx.id} className="p-4 sm:px-6 hover:bg-neutral-800/20 transition-colors flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <div className={`p-2.5 rounded-full bg-background border border-neutral-800/50 ${isExpense ? 'text-text-muted' : 'text-primary'}`}>
                        {isExpense ? <ArrowDownRight size={18} /> : <ArrowUpRight size={18} />}
                      </div>
                      <div>
                        <p className="font-medium text-text text-sm">{tx.description}</p>
                        <p className="text-xs text-text-muted mt-0.5">{category?.name || "Sin categoría"}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className={`font-semibold font-sans ${isExpense ? 'text-text' : 'text-primary'}`}>
                        {isExpense ? "-" : "+"}{formatCurrency(tx.amount)}
                      </p>
                      <p className="text-[11px] text-text-muted capitalize">{formatDate(tx.date)}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}