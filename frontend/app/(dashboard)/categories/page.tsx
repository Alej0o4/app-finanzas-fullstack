"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Loader2, Edit2, Trash2, ArrowUpRight, ArrowDownRight, Lock } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import Link from "next/link";
import { useConfirmStore } from "@/store/useConfirmStore";

// 1. Definición del Schema (OJO al user_id)
interface Category {
  id: number;
  name: string;
  type: string; // "income" o "expense"
  user_id: number | null; // null = Categoría del sistema (inmutable)
}

// 2. Diccionario de traducción para la UI
const categoryTypeTranslations: Record<string, string> = {
  income: "Ingreso",
  expense: "Gasto",
};

export default function CategoriesPage() {
  const queryClient = useQueryClient();
  
  // Estados para Crear
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [newCategoryType, setNewCategoryType] = useState("expense");

  // Estados para Editar
  const [editingCategory, setEditingCategory] = useState<Category | null>(null);
  const [editCategoryName, setEditCategoryName] = useState("");
  const [editCategoryType, setEditCategoryType] = useState("expense");

  // GET: Obtener todas las categorías
  const { data: categories, isLoading } = useQuery<Category[]>({
    queryKey: ["categories"],
    queryFn: async () => {
      const response = await api.get("/api/categories/");
      return response.data;
    },
  });

  // POST: Crear nueva categoría personalizada
  const createCategoryMutation = useMutation({
    mutationFn: async (newCategory: { name: string; type: string }) => {
      const response = await api.post("/api/categories/", newCategory);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["categories"] });
      setIsCreateModalOpen(false);
      setNewCategoryName("");
      setNewCategoryType("expense");
    },
    onError: (error: unknown) => {
      const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      toast.error(detail || "Error al crear la categoría");
    }
  });

  // PUT: Editar categoría
  const updateCategoryMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: { name: string; type: string } }) => {
      const response = await api.put(`/api/categories/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["categories"] });
      setEditingCategory(null);
    },
    onError: (error: unknown) => {
      const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      toast.error(detail || "Error al actualizar");
    }
  });

  // DELETE: Eliminar categoría
  const deleteCategoryMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.delete(`/api/categories/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["categories"] });
    },
    onError: (error: unknown) => {
      const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      toast.error(detail || "Error al eliminar. Puede que tenga transacciones asociadas.");
    }
  });

  // Handlers
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
      {/* Encabezado */}
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

      {/* Grid de Categorías */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {categories?.map((category) => {
          const isSystemCategory = category.user_id === null;
          const isExpense = category.type === "expense";

          return (
            <div key={category.id} className="bg-surface border border-border/70 rounded-2xl p-4 hover:border-border transition-colors group relative flex flex-col justify-between h-32">
              
              {/* 1. Área interactiva para navegar al detalle de la categoría */}
              <Link href={`/categories/${category.id}`} className="block h-full w-full flex flex-col justify-between cursor-pointer">
                <div className="flex justify-between items-start">
                  <div className={`p-2 rounded-xl bg-background border border-border/60 ${isExpense ? 'text-text-muted' : 'text-primary'}`}>
                    {isExpense ? <ArrowDownRight size={18} /> : <ArrowUpRight size={18} />}
                  </div>
                </div>

                <div>
                  {/* Agregamos un ligero padding-right (pr-16) para que el texto largo no se solape con los botones flotantes */}
                  <h3 className="font-medium text-text text-sm truncate pr-16">{category.name}</h3>
                  <p className="text-xs text-text-muted mt-0.5">
                    {categoryTypeTranslations[category.type] || category.type}
                  </p>
                </div>
              </Link>

              {/* 2. Controles absolutos en la esquina superior derecha (Evitan la propagación del Link) */}
              <div className="absolute top-4 right-4 z-10 flex items-center">
                {isSystemCategory ? (
                  <div className="flex items-center space-x-1 text-xs text-text-muted bg-background px-2 py-1 rounded-md border border-border/50">
                    <Lock size={12} />
                    <span>Sistema</span>
                  </div>
                ) : (
                  <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity bg-surface pl-2 rounded-lg">
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

            </div>
          );
        })}
      </div>

      {/* Modal CREAR */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-surface border border-border/70 rounded-3xl p-6 w-full max-w-md shadow-2xl">
            <h2 className="text-xl font-bold mb-4 font-sans text-text">Nueva Categoría</h2>
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
                <button type="button" onClick={() => setIsCreateModalOpen(false)} className="flex-1 px-4 py-2.5 rounded-xl border border-border/70 text-text-muted hover:text-text hover:bg-surface-elevated transition-colors text-sm font-medium">Cancelar</button>
                <button type="submit" disabled={createCategoryMutation.isPending} className="flex-1 px-4 py-2.5 rounded-xl bg-primary hover:bg-primary-dark text-background transition-colors text-sm font-medium flex justify-center items-center cursor-pointer">
                  {createCategoryMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : "Guardar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal EDITAR */}
      {editingCategory && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-surface border border-border/70 rounded-3xl p-6 w-full max-w-md shadow-2xl">
            <h2 className="text-xl font-bold mb-4 font-sans text-text">Editar Categoría</h2>
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
                <button type="button" onClick={() => setEditingCategory(null)} className="flex-1 px-4 py-2.5 rounded-xl border border-border/70 text-text-muted hover:text-text hover:bg-surface-elevated transition-colors text-sm font-medium">Cancelar</button>
                <button type="submit" disabled={updateCategoryMutation.isPending} className="flex-1 px-4 py-2.5 rounded-xl bg-primary hover:bg-primary-dark text-background transition-colors text-sm font-medium flex justify-center items-center cursor-pointer">
                  {updateCategoryMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : "Actualizar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}