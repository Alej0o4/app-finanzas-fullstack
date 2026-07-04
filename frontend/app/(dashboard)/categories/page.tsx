"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Loader2, Edit2, Trash2, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { getApiError } from "@/lib/utils";
import { queryKeys } from "@/lib/queryKeys";
import ModalShell from "@/components/ui/ModalShell";
import Button from "@/components/ui/Button";
import Link from "next/link";
import { useConfirmStore } from "@/store/useConfirmStore";
import type { Category } from "@/types/api";

const categoryTypeTranslations: Record<string, string> = {
  income: "Ingreso",
  expense: "Gasto",
};

export default function CategoriesPage() {
  const queryClient = useQueryClient();

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [newCategoryType, setNewCategoryType] = useState("expense");

  const [editingCategory, setEditingCategory] = useState<Category | null>(null);
  const [editCategoryName, setEditCategoryName] = useState("");
  const [editCategoryType, setEditCategoryType] = useState("expense");

  const { data: categories, isLoading } = useQuery<Category[]>({
    queryKey: queryKeys.categories.all(),
    queryFn: async () => {
      const response = await api.get("/api/categories/");
      return response.data;
    },
  });

  const createCategoryMutation = useMutation({
    mutationFn: async (newCategory: { name: string; type: string }) => {
      const response = await api.post("/api/categories/", newCategory);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.categories.all() });
      toast.success("Categoría creada");
      setIsCreateModalOpen(false);
      setNewCategoryName("");
      setNewCategoryType("expense");
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    }
  });

  const updateCategoryMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: { name: string; type: string } }) => {
      const response = await api.put(`/api/categories/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.categories.all() });
      toast.success("Categoría actualizada");
      setEditingCategory(null);
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    }
  });

  const deleteCategoryMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.delete(`/api/categories/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.categories.all() });
      toast.success("Categoría eliminada");
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    }
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    createCategoryMutation.mutate({ name: newCategoryName, type: newCategoryType });
  };

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingCategory) return;
    updateCategoryMutation.mutate({
      id: editingCategory.id,
      data: { name: editCategoryName, type: editCategoryType },
    });
  };

  const handleDelete = (id: number, name: string) => {
    useConfirmStore.getState().confirm(
      `¿Estás seguro de que deseas eliminar la categoría "${name}"?`,
      () => deleteCategoryMutation.mutate(id)
    );
  };

  const openEditModal = (category: Category) => {
    setEditCategoryName(category.name);
    setEditCategoryType(category.type);
    setEditingCategory(category);
  };

  if (isLoading) return <div className="p-8 text-text-muted flex items-center gap-2"><Loader2 className="animate-spin" /> Cargando categorías...</div>;

  return (
    <div className="space-y-6 relative">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold font-sans text-text">Tus Categorías</h1>
          <p className="text-sm text-text-muted">Organiza y clasifica tus movimientos.</p>
        </div>
        <button
          onClick={() => setIsCreateModalOpen(true)}
          className="bg-primary hover:bg-primary-dark text-background font-semibold px-4 py-2 rounded-xl flex items-center space-x-2 transition-colors cursor-pointer"
        >
          <Plus size={18} />
          <span>Nueva Categoría</span>
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {categories?.map((category) => {
          const isSystemCategory = category.user_id === null;
          const isExpense = category.type === "expense";

          return (
            <div key={category.id} className="bg-surface border border-border/70 rounded-2xl p-4 hover:border-border transition-colors group relative flex flex-col justify-between h-32">

              <Link href={`/categories/${category.id}`} className="block h-full w-full flex flex-col justify-between cursor-pointer">
                <div className="flex justify-between items-start">
                  <div className={`p-2 rounded-xl bg-background border border-border/60 ${isExpense ? 'text-text-muted' : 'text-primary'}`}>
                    {isExpense ? <ArrowDownRight size={18} /> : <ArrowUpRight size={18} />}
                  </div>
                </div>

                <div>
                  <h3 className="font-medium text-text text-sm truncate pr-16">{category.name}</h3>
                  <p className="text-xs text-text-muted mt-0.5">
                    {categoryTypeTranslations[category.type] || category.type}
                  </p>
                </div>
              </Link>

              {!isSystemCategory && (
                <div className="absolute top-4 right-4 z-10 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity bg-surface pl-2 rounded-lg">
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      openEditModal(category);
                    }}
                    className="text-text-muted hover:text-primary p-1 transition-colors"
                    title="Editar categoría"
                  >
                    <Edit2 size={16} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      handleDelete(category.id, category.name);
                    }}
                    className="text-text-muted hover:text-danger p-1 transition-colors"
                    title="Eliminar categoría"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              )}

            </div>
          );
        })}
      </div>

      <ModalShell isOpen={isCreateModalOpen} onClose={() => setIsCreateModalOpen(false)} title="Nueva Categoría">
        <form onSubmit={handleCreate} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Nombre</label>
            <input required value={newCategoryName} onChange={(e) => setNewCategoryName(e.target.value)} className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all" placeholder="Ej. Suscripciones" />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Naturaleza</label>
            <select value={newCategoryType} onChange={(e) => setNewCategoryType(e.target.value)} className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all appearance-none">
              <option value="expense">Gasto</option>
              <option value="income">Ingreso</option>
            </select>
          </div>

          <div className="flex gap-3 mt-6">
            <Button type="button" variant="ghost" onClick={() => setIsCreateModalOpen(false)} className="flex-1">Cancelar</Button>
            <Button type="submit" variant="primary" loading={createCategoryMutation.isPending} className="flex-1">Guardar</Button>
          </div>
        </form>
      </ModalShell>

      <ModalShell isOpen={!!editingCategory} onClose={() => setEditingCategory(null)} title="Editar Categoría">
        {editingCategory && (
          <form onSubmit={handleUpdate} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Nombre</label>
              <input required value={editCategoryName} onChange={(e) => setEditCategoryName(e.target.value)} className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all" />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">Naturaleza</label>
              <select value={editCategoryType} onChange={(e) => setEditCategoryType(e.target.value)} className="w-full bg-background border border-border/70 rounded-xl px-4 py-2.5 text-sm text-text focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all appearance-none">
                <option value="expense">Gasto</option>
                <option value="income">Ingreso</option>
              </select>
            </div>

            <div className="flex gap-3 mt-6">
              <Button type="button" variant="ghost" onClick={() => setEditingCategory(null)} className="flex-1">Cancelar</Button>
              <Button type="submit" variant="primary" loading={updateCategoryMutation.isPending} className="flex-1">Actualizar</Button>
            </div>
          </form>
        )}
      </ModalShell>
    </div>
  );
}
