/** Insignia "Planeado" (Fase 36, D9) para un gasto enlazado a un sobre. Lleva texto, no solo
 *  color; `whitespace-nowrap` + `shrink-0` para no romper filas a 390 px. */
export default function PlannedBadge() {
  return (
    <span className="bg-primary/10 text-primary border-primary/30 inline-flex shrink-0 items-center rounded-full border px-1.5 py-0.5 text-[10px] leading-none font-medium whitespace-nowrap">
      Planeado
    </span>
  );
}
