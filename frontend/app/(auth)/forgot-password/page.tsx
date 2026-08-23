'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useMutation } from '@tanstack/react-query';
import { ArrowLeft, ArrowRight, MailCheck, Wallet } from 'lucide-react';
import { api } from '@/lib/api';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';

const GENERIC_SUCCESS_MESSAGE =
  'Si el correo está registrado, recibirás instrucciones para restablecer tu contraseña.';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');

  const requestResetMutation = useMutation({
    mutationFn: async (payload: { email: string }) =>
      (await api.post('auth/password-reset/request', payload)).data,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    requestResetMutation.mutate({ email });
  };

  // El backend siempre responde 200 exista o no el correo (evita enumeration attacks).
  // Solo tratamos como error los fallos genuinos de conexión/servidor.
  if (requestResetMutation.isSuccess) {
    return (
      <div className="bg-surface border-border/70 w-full max-w-md rounded-3xl border p-8 shadow-2xl">
        <div className="mb-8 flex flex-col items-center">
          <div className="bg-success/10 text-success mb-4 flex h-12 w-12 items-center justify-center rounded-full">
            <MailCheck size={24} />
          </div>
          <h1 className="text-text font-sans text-2xl font-bold tracking-tight">
            Revisa tu correo
          </h1>
          <p className="text-text-muted mt-2 text-center text-sm">{GENERIC_SUCCESS_MESSAGE}</p>
        </div>

        <Link href="/login">
          <Button type="button" variant="secondary" size="lg" className="w-full">
            <ArrowLeft size={16} />
            Volver a iniciar sesión
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="bg-surface border-border/70 w-full max-w-md rounded-3xl border p-8 shadow-2xl">
      {/* Cabecera */}
      <div className="mb-8 flex flex-col items-center">
        <div className="bg-primary/10 text-primary mb-4 flex h-12 w-12 items-center justify-center rounded-full">
          <Wallet size={24} />
        </div>
        <h1 className="text-text font-sans text-2xl font-bold tracking-tight">
          ¿Olvidaste tu contraseña?
        </h1>
        <p className="text-text-muted mt-1 text-center text-sm">
          Escribe tu correo y te enviaremos instrucciones para restablecerla
        </p>
      </div>

      {/* Mensaje de error */}
      {requestResetMutation.isError && (
        <div className="bg-danger/10 border-danger/20 text-danger mb-6 rounded-xl border p-3 text-center text-sm">
          Error de conexión. Inténtalo más tarde.
        </div>
      )}

      {/* Formulario */}
      <form onSubmit={handleSubmit} className="space-y-5">
        <Input
          label="Correo Electrónico"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="bg-background py-3"
          placeholder="alejandro@ejemplo.com"
        />

        <Button
          type="submit"
          variant="primary"
          size="lg"
          loading={requestResetMutation.isPending}
          className="mt-2 w-full"
        >
          Enviar instrucciones
          {!requestResetMutation.isPending && <ArrowRight size={16} />}
        </Button>
      </form>

      <p className="text-text-muted mt-6 text-center text-sm">
        <Link
          href="/login"
          className="text-primary hover:text-primary-dark inline-flex items-center gap-1 font-medium transition-colors"
        >
          <ArrowLeft size={14} />
          Volver a iniciar sesión
        </Link>
      </p>
    </div>
  );
}
