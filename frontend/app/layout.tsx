import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import QueryProvider from "@/components/QueryProvider";

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
        {/* Envolvemos toda la app con el proveedor de datos */}
        <QueryProvider>
          {children}
        </QueryProvider>
      </body>
    </html>
  );
}