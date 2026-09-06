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
 *
 * `validate` (opcional, Fase 13 §13.6) normaliza valores inválidos del query string a
 * lectura: un link con `?category=abc` (o cualquier valor fuera de la whitelist) devuelve
 * el fallback en vez de un string crudo que después se castea a ciegas. La URL no se
 * reescribe con el valor corregido — el re-normalizado en cada render alcanza (el setter
 * sigue escribiendo solo valores que el propio UI produce, y el next render valida igual).
 * Cuando `validate` devuelve un tipo de unión concreta (p. ej. `BarPeriod`), el hook lo
 * infiere como tipo del valor; sin `validate`, se comporta como antes y devuelve `string`.
 */
export function useQueryParamState<T extends string = string>(
  key: string,
  defaultValue: string,
  validate?: (raw: string) => T
): [T, (value: string) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const rawValue = searchParams.get(key) ?? defaultValue;
  const value = (validate ? validate(rawValue) : rawValue) as T;

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

/**
 * Actualiza varios query params en una sola operación (un único `router.replace`).
 *
 * `useQueryParamState` por sí solo es seguro para un handler que toca un solo parámetro,
 * pero se rompe si un mismo handler llama a varios de sus setters seguidos: cada `setValue`
 * parte del mismo snapshot de `searchParams` capturado por closure, así que solo sobrevive
 * el último `router.replace` de la tanda y los demás parámetros nunca llegan a la URL. Este
 * hook existe para esos casos (presets que fijan fecha de inicio/fin/preset a la vez,
 * "limpiar filtros", etc.) — construye un único `URLSearchParams` con todos los cambios
 * antes de navegar.
 *
 * `updates[key] === null` (o `''`) borra ese parámetro de la URL; cualquier otro string lo fija.
 */
export function useQueryParamsBatch() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  return useCallback(
    (updates: Record<string, string | null>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === null || value === '') {
          params.delete(key);
        } else {
          params.set(key, value);
        }
      }
      const query = params.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [pathname, router, searchParams]
  );
}
