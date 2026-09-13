import Script from 'next/script';

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-background flex min-h-screen items-center justify-center p-4">
      {/* Punto único de carga del SDK de Google Identity Services para login y register
          (Fase 20 §20.3, Decisión 20.3.6). afterInteractive: no bloquea el hidratado. */}
      <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" />
      {children}
    </div>
  );
}
