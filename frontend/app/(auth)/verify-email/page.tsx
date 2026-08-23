'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, Loader2, MailWarning } from 'lucide-react';
import { api } from '@/lib/api';
import Button from '@/components/ui/Button';

function extractErrorMessage(error: unknown, fallback: string): string {
  const err = error as { response?: { data?: { detail?: string } } };
  return err.response?.data?.detail || fallback;
}

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const verifyQuery = useQuery({
    queryKey: ['verify-email', token],
    queryFn: async () => (await api.get('auth/verify-email', { params: { token } })).data,
    enabled: !!token,
    retry: false,
  });

  if (!token) {
    return (
      <div className="mb-8 flex flex-col items-center">
        <div className="bg-danger/10 text-danger mb-4 flex h-12 w-12 items-center justify-center rounded-full">
          <MailWarning size={24} />
        </div>
        <h1 className="text-text font-sans text-2xl font-bold tracking-tight">Enlace inválido</h1>
        <p className="text-text-muted mt-2 text-center text-sm">
          Este enlace de verificación no incluye un token válido.
        </p>
      </div>
    );
  }

  if (verifyQuery.isPending) {
    return (
      <div className="mb-8 flex flex-col items-center">
        <div className="bg-primary/10 text-primary mb-4 flex h-12 w-12 items-center justify-center rounded-full">
          <Loader2 size={24} className="animate-spin" />
        </div>
        <h1 className="text-text font-sans text-2xl font-bold tracking-tight">
          Verificando tu correo
        </h1>
        <p className="text-text-muted mt-2 text-center text-sm">Un momento, por favor...</p>
      </div>
    );
  }

  if (verifyQuery.isError) {
    return (
      <div className="mb-8 flex flex-col items-center">
        <div className="bg-danger/10 text-danger mb-4 flex h-12 w-12 items-center justify-center rounded-full">
          <MailWarning size={24} />
        </div>
        <h1 className="text-text font-sans text-2xl font-bold tracking-tight">
          No pudimos verificar tu correo
        </h1>
        <p className="text-text-muted mt-2 text-center text-sm">
          {extractErrorMessage(
            verifyQuery.error,
            'El enlace de verificación no es válido o ya expiró.'
          )}
        </p>
        <p className="text-text-muted mt-1 text-center text-sm">
          Podés iniciar sesión igualmente; te pediremos verificar tu correo más adelante.
        </p>
      </div>
    );
  }

  return (
    <div className="mb-8 flex flex-col items-center">
      <div className="bg-success/10 text-success mb-4 flex h-12 w-12 items-center justify-center rounded-full">
        <CheckCircle2 size={24} />
      </div>
      <h1 className="text-text font-sans text-2xl font-bold tracking-tight">
        Correo verificado
      </h1>
      <p className="text-text-muted mt-2 text-center text-sm">
        Tu correo fue verificado exitosamente.
      </p>
    </div>
  );
}

function VerifyEmailFooter() {
  return (
    <Link href="/login">
      <Button type="button" variant="primary" size="lg" className="w-full">
        Ir a iniciar sesión
      </Button>
    </Link>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="bg-surface border-border/70 w-full max-w-md rounded-3xl border p-8 shadow-2xl">
      <Suspense
        fallback={
          <div className="mb-8 flex flex-col items-center">
            <div className="bg-primary/10 text-primary mb-4 flex h-12 w-12 items-center justify-center rounded-full">
              <Loader2 size={24} className="animate-spin" />
            </div>
            <h1 className="text-text font-sans text-2xl font-bold tracking-tight">
              Verificando tu correo
            </h1>
          </div>
        }
      >
        <VerifyEmailContent />
      </Suspense>
      <VerifyEmailFooter />
    </div>
  );
}
