'use client';

import { FilterX } from 'lucide-react';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import type { Account, Category } from '@/types/api';

export type DatePreset = 'all' | '7d' | 'month' | 'year' | 'custom';

const PRESETS = [
  { key: 'all', label: 'Todo el histórico' },
  { key: '7d', label: 'Últimos 7 días' },
  { key: 'month', label: 'Este mes' },
  { key: 'year', label: 'Este año' },
] as const;

interface TransactionFiltersProps {
  datePreset: DatePreset;
  startDate: string;
  endDate: string;
  accountFilter: string;
  categoryFilter: string;
  accounts?: Account[];
  categories?: Category[];
  onApplyPreset: (preset: Exclude<DatePreset, 'custom'>) => void;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
  onAccountFilterChange: (value: string) => void;
  onCategoryFilterChange: (value: string) => void;
  onClearFilters: () => void;
}

export default function TransactionFilters({
  datePreset,
  startDate,
  endDate,
  accountFilter,
  categoryFilter,
  accounts,
  categories,
  onApplyPreset,
  onStartDateChange,
  onEndDateChange,
  onAccountFilterChange,
  onCategoryFilterChange,
  onClearFilters,
}: TransactionFiltersProps) {
  return (
    <div className="bg-surface border-border/70 shadow-background/20 min-w-0 space-y-4 overflow-x-hidden rounded-2xl border p-4 shadow-sm sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="text-text-soft flex items-center gap-2 text-sm font-medium">
          <FilterX size={16} className="text-text-muted" />
          Filtros de feed
        </div>
        <Button variant="ghost" size="sm" onClick={onClearFilters}>
          Limpiar filtros
        </Button>
      </div>

      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((preset) => (
            <button
              key={preset.key}
              type="button"
              onClick={() => onApplyPreset(preset.key)}
              className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
                datePreset === preset.key
                  ? 'border-primary bg-primary/10 text-text'
                  : 'border-border/70 bg-background text-text-muted hover:border-primary/60 hover:text-text'
              }`}
            >
              {preset.label}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-4">
          <Input
            label="Fecha inicial"
            type="date"
            value={startDate}
            onChange={(event) => onStartDateChange(event.target.value)}
            className="bg-background"
          />

          <Input
            label="Fecha final"
            type="date"
            value={endDate}
            onChange={(event) => onEndDateChange(event.target.value)}
            className="bg-background"
          />

          <Select
            label="Cuenta"
            value={accountFilter}
            onChange={(event) => onAccountFilterChange(event.target.value)}
            className="bg-background"
          >
            <option value="all">Todas las cuentas</option>
            {accounts?.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name}
              </option>
            ))}
          </Select>

          <Select
            label="Categoría"
            value={categoryFilter}
            onChange={(event) => onCategoryFilterChange(event.target.value)}
            className="bg-background"
          >
            <option value="all">Todas las categorías</option>
            {categories?.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </Select>
        </div>
      </div>
    </div>
  );
}
