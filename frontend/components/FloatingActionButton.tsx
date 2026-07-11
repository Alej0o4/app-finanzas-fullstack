"use client";

import { forwardRef } from "react";
import { Plus } from "lucide-react";
import type { ReactNode } from "react";

interface FloatingActionButtonProps {
  isOpen: boolean;
  onToggle: () => void;
  children: ReactNode;
}

const FloatingActionButton = forwardRef<HTMLDivElement, FloatingActionButtonProps>(
  ({ isOpen, onToggle, children }, ref) => {
    return (
      <div ref={ref} className="fixed bottom-6 right-6 z-30 flex flex-col items-end gap-3">
        {isOpen && (
          <div className="bg-surface border border-border rounded-2xl shadow-2xl p-2 min-w-[200px] animate-in fade-in slide-in-from-bottom-2 duration-200">
            {children}
          </div>
        )}
        <button
          type="button"
          onClick={onToggle}
          className={`w-14 h-14 rounded-2xl flex items-center justify-center shadow-lg transition-all duration-200 cursor-pointer ${
            isOpen
              ? "bg-surface-elevated border border-border text-text rotate-45 shadow-none"
              : "bg-primary hover:bg-primary-dark text-background shadow-primary/20 hover:shadow-primary/30"
          }`}
        >
          <Plus className="h-6 w-6" />
        </button>
      </div>
    );
  }
);

FloatingActionButton.displayName = "FloatingActionButton";

export default FloatingActionButton;
