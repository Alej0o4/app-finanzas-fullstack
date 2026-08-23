'use client';

import { useRouter } from 'next/navigation';
import TransactionCaptureForm from '@/components/forms/TransactionCaptureForm';

/**
 * Pantalla de captura como ruta principal (Fase 10, ítem 10.1). Solo compone:
 * el formulario maneja queries, mutación, invalidaciones e idempotencia por sí
 * solo; al guardar navega al dashboard, donde las queries ya invalidadas
 * muestran la transacción nueva.
 */
export default function CapturePage() {
  const router = useRouter();

  return (
    <div className="bg-surface border-border/70 w-full max-w-md rounded-3xl border p-8 shadow-2xl">
      <TransactionCaptureForm onSuccess={() => router.push('/')} />
    </div>
  );
}
