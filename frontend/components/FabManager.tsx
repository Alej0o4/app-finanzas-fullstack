"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowDownLeft, ArrowLeftRight } from "lucide-react";
import FloatingActionButton from "@/components/FloatingActionButton";
import QuickTransactionModal from "@/components/modals/QuickTransactionModal";
import TransactionModal from "@/components/modals/TransactionModal";

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

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
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
          className="flex items-center gap-3 w-full px-4 py-2.5 rounded-xl text-sm font-medium text-success hover:bg-surface-elevated transition-colors cursor-pointer"
        >
          <ArrowDownLeft className="h-4 w-4 shrink-0" />
          <span>Gasto rápido</span>
        </button>
        <button
          type="button"
          onClick={handleFullTransaction}
          className="flex items-center gap-3 w-full px-4 py-2.5 rounded-xl text-sm font-medium text-primary hover:bg-surface-elevated transition-colors cursor-pointer"
        >
          <ArrowLeftRight className="h-4 w-4 shrink-0" />
          <span>Nueva transacción</span>
        </button>
      </FloatingActionButton>

      <QuickTransactionModal
        isOpen={isQuickModalOpen}
        onClose={() => setIsQuickModalOpen(false)}
      />

      <TransactionModal
        isOpen={isFullModalOpen}
        onClose={() => setIsFullModalOpen(false)}
      />
    </>
  );
}
