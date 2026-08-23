'use client';

import { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useMutation } from '@tanstack/react-query';
import { ArrowRight, KeyRound, ShieldAlert, Wallet } from 'lucide-react';
import { api } from '@/lib/api';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';

interface PydanticErrorDetail {
  msg: string;
}

function extractErrorMessage(error: unknown, fallback: string): string {
  const err = error as {
    response?: { status?: number; data?: { detail?: string | PydanticErrorDetail[] } };
  };
  const detail = err.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((d) => d.msg).join(' ');
  }
  return fallback;
}

function InvalidLinkPanel() {
  return (
    <div className="bg-surface border-border/70 w-full max-w-md rounded-3xl border p-8 shadow-2xl">
      <div className="mb-8 flex flex-col items-center">
        <div className="bg-danger/10 text-danger mb-4 flex h-12 w-12 items-center justify-center rounded-full">
          <ShieldAlert size={24} />
        </div>
        <h1 className="text-text font-sans text-2xl font-bold tracking-tight">Enlace inválido</h1>
        <p className="text-text-muted mt-2 text-center text-sm">
          Este enlace para restablecer tu contraseña no es válido o ya expiró. Solicita uno nuevo
          para continuar.
        </p>
      </div>

      <Link href="/forgot-password">
        <Button type="button" variant="primary" size="lg" className="w-full">
          Solicitar nuevo enlace
        </Button>
      </Link>

      <p className="text-text-muted mt-6 text-center text-sm">
        <Link
          href="/login"
          className="text-primary hover:text-primary-dark font-medium transition-colors"
        >
          Volver a iniciar sesión
        </Link>
      </p>
    </div>
  );
}

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const resetMutation = useMutation({
    mutationFn: async (payload: { token: string; new_password: string }) =>
      (await api.post('auth/password-reset/confirm', payload)).data,
    onSuccess: () => {
      router.push('/login?reset=true');
    },
  });

  if (!token) {
    return <InvalidLinkPanel />;
  }

  const isTokenInvalid =
    resetMutation.isError &&
    (resetMutation.error as { response?: { status?: number } })?.response?.status === 400;

  if (isTokenInvalid) {
    return <InvalidLinkPanel />;
  }

  const submissionError = resetMutation.isError
    ? extractErrorMessage(resetMutation.error, 'Error de conexión. Inténtalo más tarde.')
    : null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (newPassword !== confirmPassword) {
      setFormError('Las contraseñas no coinciden.');
      return;
    }

    resetMutation.mutate({ token, new_password: newPassword });
  };

  return (
    <div className="bg-surface border-border/70 w-full max-w-md rounded-3xl border p-8 shadow-2xl">
      {/* Cabecera */}
      <div className="mb-8 flex flex-col items-center">
        <div className="bg-primary/10 text-primary mb-4 flex h-12 w-12 items-center justify-center rounded-full">
          <KeyRound size={24} />
        </div>
        <h1 className="text-text font-sans text-2xl font-bold tracking-tight">
          Restablece tu contraseña
        </h1>
        <p className="text-text-muted mt-1 text-center text-sm">
          Elige una nueva contraseña para tu cuenta
        </p>
      </div>

      {/* Mensaje de error */}
      {(formError || submissionError) && (
        <div
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className="bg-danger/10 border-danger/20 text-danger mb-6 rounded-xl border p-3 text-center text-sm"
        >
          {formError || submissionError}
        </div>
      )}

      {/* Formulario */}
      <form onSubmit={handleSubmit} className="space-y-5">
        <Input
          label="Nueva Contraseña"
          type="password"
          autoComplete="new-password"
          required
          minLength={10}
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          className="bg-background py-3"
          placeholder="Mínimo 10 caracteres, letras y números"
        />

        <Input
          label="Confirmar Contraseña"
          type="password"
          autoComplete="new-password"
          required
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          className="bg-background py-3"
          placeholder="Repite la contraseña"
        />

        <Button
          type="submit"
          variant="primary"
          size="lg"
          loading={resetMutation.isPending}
          className="mt-2 w-full"
        >
          Restablecer contraseña
          {!resetMutation.isPending && <ArrowRight size={16} />}
        </Button>
      </form>

      <p className="text-text-muted mt-6 text-center text-sm">
        <Link
          href="/login"
          className="text-primary hover:text-primary-dark font-medium transition-colors"
        >
          Volver a iniciar sesión
        </Link>
      </p>
    </div>
  );
}

function ResetPasswordFallback() {
  return (
    <div className="bg-surface border-border/70 w-full max-w-md rounded-3xl border p-8 shadow-2xl">
      <div className="flex flex-col items-center">
        <div className="bg-primary/10 text-primary mb-4 flex h-12 w-12 items-center justify-center rounded-full">
          <Wallet size={24} />
        </div>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<ResetPasswordFallback />}>
      <ResetPasswordForm />
    </Suspense>
  );
}
