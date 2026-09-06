'use client';

import { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import TransactionCaptureForm from '@/components/forms/TransactionCaptureForm';
import OnboardingIncomeStep from '@/components/forms/OnboardingIncomeStep';
import { useCurrentUser } from '@/lib/hooks/useCurrentUser';

/**
 * Pantalla de captura como ruta principal (Fase 10, ítem 10.1). Fase 15 agrega un
 * wizard de dos pasos SOLO cuando se llega desde el registro (`?onboarding=1`,
 * Decisión 15.0.2): primero el ingreso mensual (si aún no está fijado, Decisión
 * 15.3.2), después la captura guiada con copy explícito. Un login normal
 * (Decisión 10.1.4, sin cambios) sigue viendo la pantalla de siempre.
 */
function CaptureScreen() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isOnboarding = searchParams.get('onboarding') === '1';
  const { data: user } = useCurrentUser();

  // Estado local, no persistido (Decisión 15.0.1/15.3.2): un refresh a mitad del
  // wizard puede volver a mostrar el paso de ingreso si `monthly_income` sigue
  // null — edge case aceptado, mismo criterio que el resto de esta fase.
  const [incomeStepDone, setIncomeStepDone] = useState(false);
  const showIncomeStep = isOnboarding && user?.monthly_income == null && !incomeStepDone;

  return (
    <div className="bg-surface border-border/70 shadow-background/40 w-full max-w-md rounded-3xl border p-8 shadow-2xl">
      {showIncomeStep ? (
        <OnboardingIncomeStep onDone={() => setIncomeStepDone(true)} />
      ) : (
        <>
          {isOnboarding && (
            <p className="text-text-muted mb-4 text-sm">
              Ya casi. Registra tu primer gasto para ver el impacto en tu dashboard.
            </p>
          )}
          <TransactionCaptureForm
            onSuccess={() => router.push(isOnboarding ? '/?onboarding=1' : '/')}
          />
        </>
      )}
    </div>
  );
}

export default function CapturePage() {
  return (
    <Suspense fallback={null}>
      <CaptureScreen />
    </Suspense>
  );
}
