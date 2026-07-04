"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useUiStore } from "@/store/useUiStore";
import { useCurrentUser } from "@/lib/hooks/useCurrentUser";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { 
  LayoutDashboard, 
  TrendingUp,
  Wallet, 
  ArrowLeftRight, 
  PieChart, 
  Tags, 
  ChevronLeft, 
  ChevronRight,
  LogOut
} from "lucide-react";

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { isSidebarOpen, toggleSidebar } = useUiStore();
  const { data: user } = useCurrentUser();
  const queryClient = useQueryClient();

  const handleLogout = async () => {
    const refreshToken = localStorage.getItem("refresh_token");
    if (refreshToken) {
      try {
        await api.post("/api/auth/logout", { refresh_token: refreshToken });
      } catch {
        // Si falla la revocación, el token expirará solo
      }
    }
    localStorage.removeItem("jwt_token");
    localStorage.removeItem("refresh_token");
    queryClient.clear();
    router.push("/login");
  };

  // Enlaces basados estrictamente en tus contratos del backend
  const navItems = [
    { name: "Dashboard", href: "/", icon: LayoutDashboard },
    { name: "Analítica", href: "/analytics", icon: TrendingUp }, // <- Nueva ruta agregada
    { name: "Cuentas", href: "/accounts", icon: Wallet },
    { name: "Transacciones", href: "/transactions", icon: ArrowLeftRight },
    { name: "Presupuestos", href: "/budgets", icon: PieChart },
    { name: "Categorías", href: "/categories", icon: Tags },
  ];

  return (
    <aside 
      className={`fixed top-0 left-0 h-screen bg-surface border-r border-border/70 flex flex-col justify-between transition-all duration-300 ease-in-out z-40
        ${isSidebarOpen ? "w-64" : "w-20"}`}
    >
      {/* Parte Superior: Logo / Nombre */}
      <div>
        <div className="h-20 flex items-center justify-between px-6 border-b border-border/40">
          <span className={`font-semibold tracking-wider text-primary transition-opacity duration-200 ${isSidebarOpen ? "opacity-100" : "opacity-0 hidden"}`}>
            OIKOS .
          </span>
          <button 
            onClick={toggleSidebar}
            className="p-1.5 rounded-lg bg-background hover:bg-surface-elevated border border-border/70 text-text-muted hover:text-text transition-colors cursor-pointer"
          >
            {isSidebarOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
          </button>
        </div>

        {/* Navegación Principal */}
        <nav className="mt-6 px-3 space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center space-x-3 px-4 py-3 rounded-xl font-medium text-sm transition-all duration-200 group relative
                  ${isActive 
                    ? "bg-primary text-background font-semibold shadow-lg shadow-primary/10" 
                    : "text-text-muted hover:text-text hover:bg-surface-elevated"
                  }`}
              >
                <Icon size={20} className={isActive ? "text-background" : "text-text-muted group-hover:text-primary transition-colors"} />
                <span className={`transition-opacity duration-200 ${isSidebarOpen ? "opacity-100" : "opacity-0 hidden"}`}>
                  {item.name}
                </span>

                {/* Tooltip flotante si el sidebar está colapsado */}
                {!isSidebarOpen && (
                  <div className="absolute left-24 scale-0 group-hover:scale-100 bg-surface-elevated text-text text-xs px-2.5 py-1.5 rounded-md border border-border transition-all origin-left shadow-xl duration-150 font-sans z-50">
                    {item.name}
                  </div>
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Parte Inferior: Perfil / Cerrar Sesión */}
      <div className="p-3 border-t border-border/40">
        {isSidebarOpen ? (
          <div className="flex items-center justify-between px-3 p-2 rounded-xl bg-background/40 border border-border/40">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 rounded-full bg-surface-elevated border border-border flex items-center justify-center text-xs font-semibold text-primary uppercase">
                {user?.full_name?.split(" ").map((n: string) => n[0]).join("") || "U"}
              </div>
              <div className="flex flex-col">
                <span className="text-xs font-medium text-text">{user?.full_name || "Usuario"}</span>
                <span className="text-[10px] text-text-muted capitalize">{user?.email || ""}</span>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="text-text-muted hover:text-danger p-1.5 rounded-lg transition-colors cursor-pointer"
              title="Cerrar sesión"
            >
              <LogOut size={16} />
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-surface-elevated border border-border flex items-center justify-center text-xs font-semibold text-primary uppercase">
              {user?.full_name?.split(" ").map((n: string) => n[0]).join("") || "U"}
            </div>
            <button
              onClick={handleLogout}
              className="text-text-muted hover:text-danger p-1.5 rounded-lg transition-colors cursor-pointer"
              title="Cerrar sesión"
            >
              <LogOut size={16} />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}