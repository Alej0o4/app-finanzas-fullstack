'use client';

import { useEffect, useRef, useState } from 'react';
import { ArrowDownLeft, ArrowLeftRight } from 'lucide-react';
import FloatingActionButton from '@/components/FloatingActionButton';
import QuickTransactionModal from '@/components/modals/QuickTransactionModal';
import TransactionModal from '@/components/modals/TransactionModal';

export default function FabManager() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isQuickModalOpen, setIsQuickModalOpen] = useState(false);
  const [isFullModalOpen, setIsFullModalOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isMenuOpen) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isMenuOpen]);

  const handleQuickExpense = () => {
    setIsMenuOpen(false);
    setIsQuickModalOpen(true);
  };

  const handleFullTransaction = () => {
    setIsMenuOpen(false);
    setIsFullModalOpen(true);
  };

  return (
    <>
      <FloatingActionButton
        ref={menuRef}
        isOpen={isMenuOpen}
        onToggle={() => setIsMenuOpen(!isMenuOpen)}
      >
        <button
          type="button"
          onClick={handleQuickExpense}
          className="text-success hover:bg-surface-elevated flex w-full cursor-pointer items-center gap-3 rounded-xl px-4 py-2.5 text-sm font-medium transition-colors"
        >
          <ArrowDownLeft className="h-4 w-4 shrink-0" />
          <span>Gasto rápido</span>
        </button>
        <button
          type="button"
          onClick={handleFullTransaction}
          className="text-primary hover:bg-surface-elevated flex w-full cursor-pointer items-center gap-3 rounded-xl px-4 py-2.5 text-sm font-medium transition-colors"
        >
          <ArrowLeftRight className="h-4 w-4 shrink-0" />
          <span>Nueva transacción</span>
        </button>
      </FloatingActionButton>

      <QuickTransactionModal isOpen={isQuickModalOpen} onClose={() => setIsQuickModalOpen(false)} />

      <TransactionModal isOpen={isFullModalOpen} onClose={() => setIsFullModalOpen(false)} />
    </>
  );
}
