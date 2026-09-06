import Link from 'next/link';
import { ShieldCheck } from 'lucide-react';

export default function PrivacidadPage() {
  return (
    <div className="text-text space-y-8">
      <header className="flex items-center gap-3">
        <div className="bg-primary/10 text-primary flex h-10 w-10 shrink-0 items-center justify-center rounded-full">
          <ShieldCheck size={20} />
        </div>
        <div>
          <h1 className="font-sans text-2xl font-bold tracking-tight">Política de Privacidad</h1>
          <p className="text-text-muted mt-0.5 text-sm">
            Última actualización: pendiente de revisión legal
          </p>
        </div>
      </header>

      <section className="space-y-3">
        <h2 className="text-text font-sans text-lg font-semibold">Qué datos recogemos</h2>
        <p className="text-text-muted text-sm leading-relaxed">
          Oikos recopila la información que nos proporcionas al crear tu cuenta (nombre, correo
          electrónico) y los datos financieros que registras voluntariamente: cuentas, transacciones
          y presupuestos. También almacenamos tus preferencias de visualización (moneda, idioma y
          tema).
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-text font-sans text-lg font-semibold">Para qué usamos tus datos</h2>
        <p className="text-text-muted text-sm leading-relaxed">
          Usamos tus datos exclusivamente para operar el servicio: calcular saldos y flujos, generar
          tus reportes y mantener tu sesión segura. No vendemos ni compartimos tu información
          personal con terceros.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-text font-sans text-lg font-semibold">Contacto</h2>
        <p className="text-text-muted text-sm leading-relaxed">
          Si tienes preguntas sobre esta política o sobre el tratamiento de tus datos, escríbenos a
          privacidad@oikos.app.
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
