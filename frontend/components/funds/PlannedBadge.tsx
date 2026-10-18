/** Insignia "Planeado" (Fase 36, D9) para un gasto enlazado a un sobre. Lleva texto, no solo
 *  color; `whitespace-nowrap` + `shrink-0` para que no se parta. En filas angostas (390 px) el
 *  llamador la pone en la línea secundaria con `className`, que define el `display` (no puede ir
 *  en la base: `inline-flex` pisaría a `hidden`). */
export default function PlannedBadge({ className = 'inline-flex' }: { className?: string }) {
  return (
    <span
      className={`bg-primary/10 text-primary border-primary/30 shrink-0 items-center rounded-full border px-1.5 py-0.5 text-[10px] leading-none font-medium whitespace-nowrap ${className}`}
    >
      Planeado
    </span>
  );
}
