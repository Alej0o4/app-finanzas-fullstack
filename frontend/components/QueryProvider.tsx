'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { useState } from 'react';

// QA-018c: el retry por defecto de TanStack (3 reintentos con backoff, ~7 s) también reintentaba
// 404/403/422, así que el detalle de un recurso ajeno o inexistente quedaba en skeleton ~7 s
// antes de mostrar "no se encontró". Un 4xx es una respuesta definitiva del backend: no se
// reintenta (salvo 408/429); errores de red y 5xx conservan los reintentos por defecto.
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (isAxiosError(error)) {
    const status = error.response?.status;
    if (status && status >= 400 && status < 500 && status !== 408 && status !== 429) return false;
  }
  return failureCount < 3;
}

export default function QueryProvider({ children }: { children: React.ReactNode }) {
  // Inicializamos el cliente una sola vez por sesión
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // Los datos se consideran "frescos" por 1 minuto
            retry: shouldRetry,
            refetchOnWindowFocus: false, // Evita peticiones excesivas al cambiar de pestaña
          },
        },
      })
  );

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
