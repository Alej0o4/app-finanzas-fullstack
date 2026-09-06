import Link from 'next/link';
import { FileText } from 'lucide-react';

export default function TerminosPage() {
  return (
    <div className="text-text space-y-8">
      <header className="flex items-center gap-3">
        <div className="bg-primary/10 text-primary flex h-10 w-10 shrink-0 items-center justify-center rounded-full">
          <FileText size={20} />
        </div>
        <div>
          <h1 className="font-sans text-2xl font-bold tracking-tight">Términos de Servicio</h1>
          <p className="text-text-muted mt-0.5 text-sm">
            Última actualización: pendiente de revisión legal
          </p>
        </div>
      </header>

      <section className="space-y-3">
        <h2 className="text-text font-sans text-lg font-semibold">Uso del servicio</h2>
        <p className="text-text-muted text-sm leading-relaxed">
          Al usar Oikos aceptas proporcionar información veraz y utilizar la aplicación únicamente
          para la gestión de tus finanzas personales. No está permitido emplear el servicio para
          actividades ilícitas ni para operar con fondos de terceros sin autorización.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-text font-sans text-lg font-semibold">Responsabilidad</h2>
        <p className="text-text-muted text-sm leading-relaxed">
          Oikos se ofrece «tal cual», sin garantías de disponibilidad ininterrumpida. Los saldos y
          reportes se calculan con base en la información que tú registras: eres responsable de la
          exactitud de tus movimientos. No somos una entidad financiera y no ofrecemos asesoría de
          inversión.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-text font-sans text-lg font-semibold">Contacto</h2>
        <p className="text-text-muted text-sm leading-relaxed">
          Para consultas sobre estos términos, escríbenos a soporte@oikos.app.
        </p>
      </section>

      <p className="text-text-muted/60 border-border/40 border-t pt-4 text-xs">
        Este contenido es un placeholder estructural. La redacción legal definitiva requiere
        revisión de cumplimiento.
      </p>

      <Link
        href="/"
        className="text-primary hover:text-primary-dark text-sm font-medium transition-colors"
      >
        ← Volver al dashboard
      </Link>
    </div>
  );
}
