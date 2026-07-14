'use client';

import { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowRight, Wallet } from 'lucide-react';
import { api } from '@/lib/api';
import Input from '@/components/ui/Input';
import Button from '@/components/ui/Button';

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const registered = searchParams.get('registered');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      // OAuth2 exige enviar los datos como URLSearchParams (x-www-form-urlencoded)
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      // Petición al backend
      const response = await api.post('/api/auth/login', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      // Guardamos los tokens en localStorage
      const { access_token, refresh_token } = response.data;
      localStorage.setItem('jwt_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);

      // Redirigimos al Dashboard (la fuente de verdad)
      router.push('/');
    } catch (err: unknown) {
      const error = err as { response?: { status?: number } };
      if (error.response?.status === 401 || error.response?.status === 403) {
        setError('Credenciales inválidas. Por favor verifica tus datos.');
      } else {
        setError('Error de conexión. Inténtalo más tarde.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-surface border-border/70 w-full max-w-md rounded-3xl border p-8 shadow-2xl">
      {/* Cabecera */}
      <div className="mb-8 flex flex-col items-center">
        <div className="bg-primary/10 text-primary mb-4 flex h-12 w-12 items-center justify-center rounded-full">
          <Wallet size={24} />
        </div>
        <h1 className="text-text font-sans text-2xl font-bold tracking-tight">
          Bienvenido a Oikos
        </h1>
        <p className="text-text-muted mt-1 text-center text-sm">Ingresa a tu entorno financiero</p>
      </div>

      {/* Mensaje de éxito post-registro */}
      {registered === 'true' && (
        <div className="bg-success/10 border-success/20 text-success mb-6 rounded-xl border p-3 text-center text-sm">
          Cuenta creada exitosamente. Ahora puedes iniciar sesión.
        </div>
      )}

      {/* Mensaje de Error */}
      {error && (
        <div className="bg-danger/10 border-danger/20 text-danger mb-6 rounded-xl border p-3 text-center text-sm">
          {error}
        </div>
      )}

      {/* Formulario */}
      <form onSubmit={handleLogin} className="space-y-5">
        <Input
          label="Correo Electrónico"
          type="email"
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="bg-background py-3"
          placeholder="alejandro@ejemplo.com"
        />

        <Input
          label="Contraseña"
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="bg-background py-3"
          placeholder="••••••••"
        />

        <Button
          type="submit"
          variant="primary"
          size="lg"
          loading={isLoading}
          className="mt-2 w-full"
        >
          Iniciar Sesión
          {!isLoading && <ArrowRight size={16} />}
        </Button>
      </form>

      <p className="text-text-muted mt-6 text-center text-sm">
        ¿No tienes cuenta?{' '}
        <Link
          href="/register"
          className="text-primary hover:text-primary-dark font-medium transition-colors"
        >
          Regístrate
        </Link>
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
