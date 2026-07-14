'use client';

import { forwardRef } from 'react';
import { Plus } from 'lucide-react';
import type { ReactNode } from 'react';

interface FloatingActionButtonProps {
  isOpen: boolean;
  onToggle: () => void;
  children: ReactNode;
}

const FloatingActionButton = forwardRef<HTMLDivElement, FloatingActionButtonProps>(
  ({ isOpen, onToggle, children }, ref) => {
    return (
      <div ref={ref} className="fixed right-6 bottom-6 z-30 flex flex-col items-end gap-3">
        {isOpen && (
          <div className="bg-surface border-border animate-in fade-in slide-in-from-bottom-2 min-w-[200px] rounded-2xl border p-2 shadow-2xl duration-200">
            {children}
          </div>
        )}
        <button
          type="button"
          onClick={onToggle}
          className={`flex h-14 w-14 cursor-pointer items-center justify-center rounded-2xl shadow-lg transition-all duration-200 ${
            isOpen
              ? 'bg-surface-elevated border-border text-text rotate-45 border shadow-none'
              : 'bg-primary hover:bg-primary-dark text-background shadow-primary/20 hover:shadow-primary/30'
          }`}
        >
          <Plus className="h-6 w-6" />
        </button>
      </div>
    );
  }
);

FloatingActionButton.displayName = 'FloatingActionButton';

export default FloatingActionButton;
