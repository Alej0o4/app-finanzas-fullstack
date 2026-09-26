'use client';

import { ChevronLeft, ChevronRight } from 'lucide-react';
import Button from '@/components/ui/Button';

interface PeriodNavigatorProps {
  /** Rótulo del período visible, p. ej. `"Agosto 2026"`. */
  label: string;
  onPrev: () => void;
  onNext: () => void;
  prevDisabled: boolean;
  nextDisabled: boolean;
  /** `aria-label` de la flecha hacia atrás. El default es el del dashboard; Analítica pasa
   *  "Período anterior" porque navega semana, mes o año según el preset. */
  prevLabel?: string;
  /** `aria-label` de la flecha hacia adelante. */
  nextLabel?: string;
  /** Botón de vuelta al período actual. Si no se pasa, no se renderiza. */
  onReset?: () => void;
  /** Texto del botón de reset ("Volver a este mes" en el dashboard, "Volver al período actual"
   *  en Analítica). */
  resetLabel?: string;
}

/**
 * Navegador de períodos `◀ label ▶` (Fase 29 §F4), compartido por el dashboard (mes) y por
 * Analítica (semana, mes o año según el preset).
 *
 * No sabe de fechas: solo dispara los handlers y los límites deshabilitados se los pasa el
 * caller (el dashboard los saca de `first_transaction_month` y del mes actual, Analítica de la
 * posición del período en la URL). El componente es el que dibuja el rótulo para que ambos
 * lugares se lean igual.
 */
export default function PeriodNavigator({
  label,
  onPrev,
  onNext,
  prevDisabled,
  nextDisabled,
  prevLabel = 'Mes anterior',
  nextLabel = 'Mes siguiente',
  onReset,
  resetLabel = 'Volver a este mes',
}: PeriodNavigatorProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant="ghost"
        size="sm"
        onClick={onPrev}
        disabled={prevDisabled}
        aria-label={prevLabel}
        className="px-2"
      >
        <ChevronLeft size={16} />
      </Button>
      {/* min-w para que el control no dance de ancho al cambiar de período ("Agosto 2026" vs
          "Septiembre 2026") mientras se navega. */}
      <span className="text-text min-w-32 text-center text-sm font-semibold whitespace-nowrap">
        {label}
      </span>
      <Button
        variant="ghost"
        size="sm"
        onClick={onNext}
        disabled={nextDisabled}
        aria-label={nextLabel}
        className="px-2"
      >
        <ChevronRight size={16} />
      </Button>
      {onReset && (
        <Button variant="ghost" size="sm" onClick={onReset}>
          {resetLabel}
        </Button>
      )}
    </div>
  );
}
