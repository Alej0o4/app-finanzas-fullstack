import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import QueryProvider from "@/components/QueryProvider";
import { AppConfigProvider } from "@/providers/AppConfigProvider";
import { UserPreferencesSync } from "@/providers/UserPreferencesSync";
import { Toaster } from "sonner";

const plusJakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-plus-jakarta",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Oikos | Finanzas Personales",
  description: "Dashboard financiero minimalista y orgánico",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className={`${plusJakarta.variable}`}>
      <body>
        <AppConfigProvider>
          {/* Envolvemos toda la app con el proveedor de datos */}
          <QueryProvider>
            {children}
            <UserPreferencesSync />
            <Toaster richColors position="top-right" closeButton />
          </QueryProvider>
        </AppConfigProvider>
      </body>
    </html>
  );
}