'use client';

import { useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowRight, Wallet } from 'lucide-react';
import { api } from '@/lib/api';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Fase 12 §12.8: errores por campo (no globo nativo del navegador) + foco en el primero.
  const [fieldErrors, setFieldErrors] = useState<{
    fullName?: string;
    email?: string;
    password?: string;
    confirmPassword?: string;
  }>({});
  const fullNameRef = useRef<HTMLInputElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const confirmRef = useRef<HTMLInputElement>(null);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const errors: typeof fieldErrors = {};
    if (!fullName.trim()) errors.fullName = 'Ingresa tu nombre completo.';
    if (!/^\S+@\S+\.\S+$/.test(email)) errors.email = 'Ingresa un correo válido.';
    if (password.length < 10) errors.password = 'Debe tener al menos 10 caracteres.';
    if (password !== confirmPassword) errors.confirmPassword = 'Las contraseñas no coinciden.';
    setFieldErrors(errors);

    if (errors.fullName) return fullNameRef.current?.focus();
    if (errors.email) return emailRef.current?.focus();
    if (errors.password) return passwordRef.current?.focus();
    if (errors.confirmPassword) return confirmRef.current?.focus();

    setIsLoading(true);

    try {
      await api.post('users/', {
        full_name: fullName,
        email,
        password,
      });

      router.push('/login?registered=true');
    } catch (err: unknown) {
      const error = err as {
        response?: { status?: number; data?: { detail?: string | { msg: string }[] } };
      };
      if (error.response?.status === 400) {
        const detail = error.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'El correo electrónico ya está registrado.');
      } else if (error.response?.status === 422) {
        const detail = error.response?.data?.detail;
        const msg = Array.isArray(detail)
          ? detail[0]?.msg || 'Datos inválidos.'
          : 'Datos inválidos.';
        setError(msg);
      } else {
        setError('Error de conexión. Inténtalo más tarde.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-surface border-border/70 shadow-background/40 w-full max-w-md rounded-3xl border p-8 shadow-2xl">
      <div className="mb-8 flex flex-col items-center">
        <div className="bg-primary/10 text-primary mb-4 flex h-12 w-12 items-center justify-center rounded-full">
          <Wallet size={24} />
        </div>
        <h1 className="text-text font-sans text-2xl font-bold tracking-tight">Crear tu cuenta</h1>
        <p className="text-text-muted mt-1 text-center text-sm">
          Comienza a gestionar tus finanzas
        </p>
      </div>

      {error && (
        <div
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className="bg-danger/10 border-danger/20 text-danger mb-6 rounded-xl border p-3 text-center text-sm"
        >
          {error}
        </div>
      )}

      <form onSubmit={handleRegister} className="space-y-4" noValidate>
        <Input
          ref={fullNameRef}
          label="Nombre Completo"
          type="text"
          autoComplete="name"
          required
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          error={fieldErrors.fullName}
          className="bg-background py-3"
          placeholder="Alejandro Martínez"
        />

        <Input
          ref={emailRef}
          label="Correo Electrónico"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={fieldErrors.email}
          className="bg-background py-3"
          placeholder="alejandro@ejemplo.com"
        />

        <Input
          ref={passwordRef}
          label="Contraseña"
          type="password"
          autoComplete="new-password"
          required
          minLength={10}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={fieldErrors.password}
          className="bg-background py-3"
          placeholder="Mínimo 10 caracteres, con letras y números"
        />

        <Input
          ref={confirmRef}
          label="Confirmar Contraseña"
          type="password"
          autoComplete="new-password"
          required
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          error={fieldErrors.confirmPassword}
          className="bg-background py-3"
          placeholder="Repite la contraseña"
        />

        <Button
          type="submit"
          variant="primary"
          size="lg"
          loading={isLoading}
          className="mt-2 w-full"
        >
          Crear Cuenta
          {!isLoading && <ArrowRight size={16} />}
        </Button>
      </form>

      <p className="text-text-muted mt-6 text-center text-sm">
        ¿Ya tienes cuenta?{' '}
        <Link
          href="/login"
          className="text-primary hover:text-primary-dark font-medium transition-colors"
        >
          Inicia sesión
        </Link>
      </p>
    </div>
  );
}
