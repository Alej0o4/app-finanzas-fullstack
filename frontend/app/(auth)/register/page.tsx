"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowRight, Loader2, Wallet } from "lucide-react";
import { api } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    if (password !== confirmPassword) {
      setError("Las contraseñas no coinciden.");
      setIsLoading(false);
      return;
    }

    if (password.length < 6) {
      setError("La contraseña debe tener al menos 6 caracteres.");
      setIsLoading(false);
      return;
    }

    try {
      await api.post("/api/users/", {
        full_name: fullName,
        email,
        password,
      });

      router.push("/login?registered=true");
    } catch (err: any) {
      if (err.response?.status === 400) {
        setError(err.response?.data?.detail || "El correo electrónico ya está registrado.");
      } else {
        setError("Error de conexión. Inténtalo más tarde.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md bg-surface border border-border/70 rounded-3xl p-8 shadow-2xl">
      <div className="flex flex-col items-center mb-8">
        <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mb-4 text-primary">
          <Wallet size={24} />
        </div>
        <h1 className="text-2xl font-bold font-sans tracking-tight text-text">Crear tu cuenta</h1>
        <p className="text-text-muted text-sm mt-1 text-center">
          Comienza a gestionar tus finanzas
        </p>
      </div>

      {error && (
        <div className="mb-6 p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-sm text-center">
          {error}
        </div>
      )}

      <form onSubmit={handleRegister} className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">
            Nombre Completo
          </label>
          <input
            type="text"
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full bg-background border border-border/70 rounded-xl px-4 py-3 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
            placeholder="Alejandro Martínez"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">
            Correo Electrónico
          </label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full bg-background border border-border/70 rounded-xl px-4 py-3 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
            placeholder="alejandro@ejemplo.com"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">
            Contraseña
          </label>
          <input
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-background border border-border/70 rounded-xl px-4 py-3 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
            placeholder="Mínimo 6 caracteres"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">
            Confirmar Contraseña
          </label>
          <input
            type="password"
            required
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="w-full bg-background border border-border/70 rounded-xl px-4 py-3 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
            placeholder="Repite la contraseña"
          />
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-primary hover:bg-primary-dark text-background font-semibold rounded-xl px-4 py-3 text-sm transition-colors flex items-center justify-center disabled:opacity-70 mt-2 cursor-pointer"
        >
          {isLoading ? (
            <Loader2 size={18} className="animate-spin" />
          ) : (
            <>
              Crear Cuenta
              <ArrowRight size={16} className="ml-2" />
            </>
          )}
        </button>
      </form>

      <p className="text-center text-sm text-text-muted mt-6">
        ¿Ya tienes cuenta?{" "}
        <Link href="/login" className="text-primary hover:text-primary-dark font-medium transition-colors">
          Inicia sesión
        </Link>
      </p>
    </div>
  );
}
