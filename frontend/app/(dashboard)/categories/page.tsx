'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Loader2, Edit2, Trash2, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { getApiError } from '@/lib/utils';
import { queryKeys } from '@/lib/queryKeys';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import ModalShell from '@/components/ui/ModalShell';
import Button from '@/components/ui/Button';
import Link from 'next/link';
import { useConfirmStore } from '@/store/useConfirmStore';
import CategoryIcon from '@/components/ui/CategoryIcon';
import type { Category } from '@/types/api';

const categoryTypeTranslations: Record<string, string> = {
  income: 'Ingreso',
  expense: 'Gasto',
};

export default function CategoriesPage() {
  const queryClient = useQueryClient();

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [newCategoryType, setNewCategoryType] = useState('expense');

  const [editingCategory, setEditingCategory] = useState<Category | null>(null);
  const [editCategoryName, setEditCategoryName] = useState('');
  const [editCategoryType, setEditCategoryType] = useState('expense');

  const { data: categories, isLoading } = useQuery<Category[]>({
    queryKey: queryKeys.categories.all(),
    queryFn: async () => {
      const response = await api.get('/api/categories/');
      return response.data;
    },
  });

  const createCategoryMutation = useMutation({
    mutationFn: async (newCategory: { name: string; type: string }) => {
      const response = await api.post('/api/categories/', newCategory);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.categories.all() });
      toast.success('Categoría creada');
      setIsCreateModalOpen(false);
      setNewCategoryName('');
      setNewCategoryType('expense');
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const updateCategoryMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: { name: string; type: string } }) => {
      const response = await api.put(`/api/categories/${id}`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.categories.all() });
      toast.success('Categoría actualizada');
      setEditingCategory(null);
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
  });

  const deleteCategoryMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.delete(`/api/categories/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.categories.all() });
      toast.success('Categoría eliminada');
    },
    onError: (error: unknown) => {
      toast.error(getApiError(error));
    },
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
    useConfirmStore
      .getState()
      .confirm(`¿Estás seguro de que deseas eliminar la categoría "${name}"?`, () =>
        deleteCategoryMutation.mutate(id)
      );
  };

  const openEditModal = (category: Category) => {
    setEditCategoryName(category.name);
    setEditCategoryType(category.type);
    setEditingCategory(category);
  };

  if (isLoading)
    return (
      <div className="text-text-muted flex items-center gap-2 p-8">
        <Loader2 className="animate-spin" /> Cargando categorías...
      </div>
    );

  return (
    <div className="relative space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-text font-sans text-2xl font-bold">Tus Categorías</h1>
          <p className="text-text-muted text-sm">Organiza y clasifica tus movimientos.</p>
        </div>
        <button
          onClick={() => setIsCreateModalOpen(true)}
          className="bg-primary hover:bg-primary-dark text-background flex cursor-pointer items-center space-x-2 rounded-xl px-4 py-2 font-semibold transition-colors"
        >
          <Plus size={18} />
          <span>Nueva Categoría</span>
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
        {categories?.map((category) => {
          const isSystemCategory = category.user_id === null;
          const isExpense = category.type === 'expense';

          return (
            <div
              key={category.id}
              className="bg-surface border-border/70 hover:border-border group relative flex h-32 flex-col justify-between rounded-2xl border p-4 transition-colors"
            >
              <Link
                href={`/categories/${category.id}`}
                className="block flex h-full w-full cursor-pointer flex-col justify-between"
              >
                <div className="flex items-start justify-between">
                  <div
                    className={`bg-background border-border/60 rounded-xl border p-2 ${isExpense ? 'text-text-muted' : 'text-primary'}`}
                  >
                    <CategoryIcon
                      icon={category.icon}
                      size={18}
                      fallback={
                        isExpense ? <ArrowDownRight size={18} /> : <ArrowUpRight size={18} />
                      }
                    />
                  </div>
                </div>

                <div>
                  <h3 className="text-text truncate pr-16 text-sm font-medium">{category.name}</h3>
                  <p className="text-text-muted mt-0.5 text-xs">
                    {categoryTypeTranslations[category.type] || category.type}
                  </p>
                </div>
              </Link>

              {!isSystemCategory && (
                <div className="bg-surface absolute top-4 right-4 z-10 flex gap-2 rounded-lg pl-2 opacity-0 transition-opacity group-hover:opacity-100">
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

      <ModalShell
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Nueva Categoría"
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <Input
            label="Nombre"
            required
            value={newCategoryName}
            onChange={(e) => setNewCategoryName(e.target.value)}
            className="bg-background"
            placeholder="Ej. Suscripciones"
          />

          <Select
            label="Naturaleza"
            value={newCategoryType}
            onChange={(e) => setNewCategoryType(e.target.value)}
            className="bg-background"
          >
            <option value="expense">Gasto</option>
            <option value="income">Ingreso</option>
          </Select>

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
              loading={createCategoryMutation.isPending}
              className="flex-1"
            >
              Guardar
            </Button>
          </div>
        </form>
      </ModalShell>

      <ModalShell
        isOpen={!!editingCategory}
        onClose={() => setEditingCategory(null)}
        title="Editar Categoría"
      >
        {editingCategory && (
          <form onSubmit={handleUpdate} className="space-y-4">
            <Input
              label="Nombre"
              required
              value={editCategoryName}
              onChange={(e) => setEditCategoryName(e.target.value)}
              className="bg-background"
            />

            <Select
              label="Naturaleza"
              value={editCategoryType}
              onChange={(e) => setEditCategoryType(e.target.value)}
              className="bg-background"
            >
              <option value="expense">Gasto</option>
              <option value="income">Ingreso</option>
            </Select>

            <div className="mt-6 flex gap-3">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setEditingCategory(null)}
                className="flex-1"
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                variant="primary"
                loading={updateCategoryMutation.isPending}
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
