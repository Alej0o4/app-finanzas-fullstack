"use client";

import { Settings2 } from "lucide-react";
import { useState, useRef, useEffect, type ReactNode } from "react";

interface ChartControlsPopoverProps {
  children: ReactNode;
}

export default function ChartControlsPopover({ children }: ChartControlsPopoverProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex items-center justify-center rounded-lg border border-border/70 bg-background/40 p-2 text-text-muted hover:text-text hover:bg-surface-elevated transition-colors"
        aria-label="Configurar visualización"
      >
        <Settings2 className="h-4 w-4" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 z-50 min-w-[180px] rounded-xl border border-border bg-surface-elevated p-3 shadow-xl backdrop-blur-sm">
          {children}
        </div>
      )}
    </div>
  );
}
