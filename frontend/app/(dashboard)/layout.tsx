"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import { useUiStore } from "@/store/useUiStore";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { isSidebarOpen } = useUiStore();

  useEffect(() => {
    const token = localStorage.getItem("jwt_token");
    if (!token) {
      router.replace("/login");
    }
  }, [router]);

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <ConfirmDialog />

      <div 
        className={`transition-all duration-300 ease-in-out min-h-screen flex flex-col
          ${isSidebarOpen ? "pl-64" : "pl-20"}`}
      >
        <main className="flex-1 p-8 lg:p-12max-w-[1600px] w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}