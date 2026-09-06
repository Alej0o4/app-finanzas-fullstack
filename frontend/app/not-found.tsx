import Link from 'next/link';
import { Compass } from 'lucide-react';
import Button from '@/components/ui/Button';

export default function NotFound() {
  return (
    <div className="bg-background flex min-h-screen items-center justify-center p-4">
      <div className="bg-surface border-border/70 shadow-background/40 w-full max-w-md rounded-3xl border p-8 text-center shadow-2xl">
        <div className="bg-primary/10 text-primary mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full">
          <Compass size={24} />
        </div>
        <h1 className="text-text font-sans text-2xl font-bold tracking-tight">
          Página no encontrada
        </h1>
        <p className="text-text-muted mt-2 text-sm">
          La página que buscas no existe o cambió de dirección.
        </p>
        <Link href="/" className="mt-6 block">
          <Button type="button" variant="primary" size="lg" className="w-full">
            Volver al dashboard
          </Button>
        </Link>
      </div>
    </div>
  );
}
