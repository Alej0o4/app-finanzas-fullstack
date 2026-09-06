'use client';

import { useCallback } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';

/**
 * Sincroniza un valor de string con un query param de la URL vía router.replace
 * (shallow, sin recargar ni apilar historial por cada cambio). El valor por defecto
 * nunca se escribe en la URL — una URL sin el param equivale a "usa el default".
 *
 * Requiere que el componente que lo usa esté envuelto en <Suspense> (mismo requisito
 * de Next.js App Router que ya aplica a useSearchParams en login/page.tsx y
 * reset-password/page.tsx).
 */
export function useQueryParamState(
  key: string,
  defaultValue: string
): [string, (value: string) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const value = searchParams.get(key) ?? defaultValue;

  const setValue = useCallback(
    (next: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (next === defaultValue || next === '') {
        params.delete(key);
      } else {
        params.set(key, next);
      }
      const query = params.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [key, defaultValue, pathname, router, searchParams]
  );

  return [value, setValue];
}
