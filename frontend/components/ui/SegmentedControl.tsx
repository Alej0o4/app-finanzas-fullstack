'use client';

export interface SegmentedOption {
  value: string;
  label: string;
}

interface SegmentedControlProps {
  options: SegmentedOption[];
  value: string;
  onChange: (value: string) => void;
  /** Nombre accesible del grupo: los chips de moneda y los presets de período se ven idénticos
   *  en pantalla, así que sin esto un lector de pantalla no dice qué son. */
  ariaLabel?: string;
  className?: string;
}

/**
 * Grupo de opciones excluyentes (Fase 29 §F4), extraído del selector de período inline de
 * Analítica y reutilizado por los chips de moneda del dashboard y de Analítica.
 *
 * Cada botón es un toggle con `aria-pressed` (no un `radiogroup`): el estado vive en la URL de la
 * página, no en el DOM, y un grupo de botones con `aria-pressed` se anuncia sin ids que sincronizar.
 * El caller decide qué hacer con el valor (`useQueryParamState`, `useState`…): el control no sabe
 * de meses ni de monedas.
 */
export default function SegmentedControl({
  options,
  value,
  onChange,
  ariaLabel,
  className = '',
}: SegmentedControlProps) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={`border-border/70 bg-background/40 flex items-center gap-1 rounded-lg border p-0.5 ${className}`}
    >
      {options.map((option) => {
        const isActive = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={isActive}
            onClick={() => onChange(option.value)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              isActive ? 'bg-primary text-background' : 'text-text-muted hover:text-text'
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
