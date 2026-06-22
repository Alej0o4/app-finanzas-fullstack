"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2, Wallet } from "lucide-react";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      // OAuth2 exige enviar los datos como URLSearchParams (x-www-form-urlencoded)
      const formData = new URLSearchParams();
      formData.append("username", username);
      formData.append("password", password);

      // Petición al backend
      const response = await api.post("/api/auth/login", formData, {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      });

      // Guardamos el token en localStorage
      const { access_token } = response.data;
      localStorage.setItem("jwt_token", access_token);

      // Redirigimos al Dashboard (la fuente de verdad)
      router.push("/");
      
    } catch (err: any) {
      // Manejo de errores basado en tus reglas de backend
      if (err.response?.status === 401 || err.response?.status === 403) {
        setError("Credenciales inválidas. Por favor verifica tus datos.");
      } else {
        setError("Error de conexión. Inténtalo más tarde.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md bg-surface border border-neutral-800/40 rounded-3xl p-8 shadow-2xl">
      {/* Cabecera */}
      <div className="flex flex-col items-center mb-8">
        <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mb-4 text-primary">
          <Wallet size={24} />
        </div>
        <h1 className="text-2xl font-bold font-sans tracking-tight text-text">Bienvenido a Oikos</h1>
        <p className="text-text-muted text-sm mt-1 text-center">
          Ingresa a tu entorno financiero
        </p>
      </div>

      {/* Mensaje de Error */}
      {error && (
        <div className="mb-6 p-3 rounded-xl bg-danger/10 border border-danger/20 text-danger text-sm text-center">
          {error}
        </div>
      )}

      {/* Formulario */}
      <form onSubmit={handleLogin} className="space-y-5">
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-text-muted uppercase tracking-wider pl-1">
            Correo Electrónico
          </label>
          <input
            type="email"
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full bg-background border border-neutral-800/60 rounded-xl px-4 py-3 text-sm text-text placeholder:text-neutral-600 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
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
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-background border border-neutral-800/60 rounded-xl px-4 py-3 text-sm text-text placeholder:text-neutral-600 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
            placeholder="••••••••"
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
              Iniciar Sesión
              <ArrowRight size={16} className="ml-2" />
            </>
          )}
        </button>
      </form>
    </div>
  );
}