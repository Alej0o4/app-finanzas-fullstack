"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Tag, Loader2, ArrowDownRight, ArrowUpRight } from "lucide-react";
import { api } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";

interface Category {
  id: number;
  name: string;
  type: string;
}

interface Transaction {
  id: number;
  description: string;
  amount: number;
  type: string;
  date: string;
  account_id: number;
}

interface Account {
  id: number;
  name: string;
}

export default function CategoryDetailPage() {
  const { id } = useParams();
  const router = useRouter();

  // 1. Obtener detalles de la categoría
  const { data: category, isLoading: loadingCategory } = useQuery<Category>({
    queryKey: ["category", id],
    queryFn: async () => (await api.get(`/api/categories/${id}`)).data,
  });

  // 2. Obtener transacciones filtradas por categoría
  const { data: transactions, isLoading: loadingTx } = useQuery<Transaction[]>({
    queryKey: ["transactions", "category", id],
    queryFn: async () => (await api.get(`/api/transactions/?category_id=${id}`)).data,
  });

  // 3. Traer cuentas para saber el origen de los fondos en la lista
  const { data: accounts } = useQuery<Account[]>({
    queryKey: ["accounts"],
    queryFn: async () => (await api.get("/api/accounts/")).data,
  });

  const isLoading = loadingCategory || loadingTx;

  if (isLoading) return <div className="p-8 text-text-muted flex items-center gap-2"><Loader2 className="animate-spin" /> Cargando historial de categoría...</div>;
  if (!category) return <div className="p-8 text-text-muted">No se encontró la categoría especificada.</div>;

  const isExpense = category.type === "expense";

  return (
    <div className="space-y-8">
      {/* Encabezado */}
      <div className="flex items-center space-x-4">
        <button 
          onClick={() => router.back()}
          className="p-2 bg-surface hover:bg-neutral-800 border border-neutral-800/60 text-text-muted hover:text-text rounded-xl transition-colors cursor-pointer"
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

      {/* Historial filtrado */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold font-sans text-text">Movimientos asociados</h2>
        
        <div className="bg-surface border border-neutral-800/60 rounded-3xl overflow-hidden shadow-sm">
          {(!transactions || transactions.length === 0) ? (
            <div className="p-12 text-center text-text-muted text-sm">
              No hay movimientos clasificados en esta categoría aún.
            </div>
          ) : (
            <div className="divide-y divide-neutral-800/40">
              {transactions.map((tx) => {
                const account = accounts?.find(a => a.id === tx.account_id);

                return (
                  <div key={tx.id} className="p-4 sm:px-6 hover:bg-neutral-800/20 transition-colors flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <div className={`p-2.5 rounded-full bg-background border border-neutral-800/50 ${isExpense ? 'text-text-muted' : 'text-primary'}`}>
                        {isExpense ? <ArrowDownRight size={18} /> : <ArrowUpRight size={18} />}
                      </div>
                      <div>
                        <p className="font-medium text-text text-sm">{tx.description}</p>
                        <p className="text-xs text-text-muted mt-0.5">{account?.name || "Cuenta eliminada"}</p>
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