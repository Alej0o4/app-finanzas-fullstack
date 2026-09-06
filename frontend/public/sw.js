/* Oikos — Service Worker (Fase 13 §13.1/§13.2).
 *
 * Escrito a mano, sin next-pwa/Workbox (Decisión 13.1.1): el alcance es acotado a
 * propósito — cachear el app shell mínimo para que la app sea instalable y recibir
 * push. No se busca funcionalidad offline compleja (está en el backlog de baja
 * prioridad "Sincronización offline" del ROADMAP).
 *
 * Estrategia de cache: network-first con fallback a cache. NUNCA cache-first —
 * los datos financieros no deben servirse obsoletos silenciosamente.
 */

const CACHE_NAME = 'oikos-shell-v1';

const APP_SHELL = ['/', '/capture', '/manifest.json'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Las respuestas de la API (datos financieros) jamás se cachean: la red manda
  // siempre, incluso offline no se sirve un saldo viejo en silencio (Decisión 13.1.1).
  if (url.pathname.startsWith('/api/v1')) return;

  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok && url.origin === self.location.origin) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(() => caches.match(request))
  );
});

/* Push + notificationclick (Fase 13 §13.2): el payload push es el mismo aviso que
 * ya quedó persistido en la bandeja in-app (el push es un canal adicional sobre la
 * misma fila, no un canal paralelo con su propio dato). */

self.addEventListener('push', (event) => {
  if (!event.data) return;

  let title = 'Oikos';
  let body = '';

  try {
    const data = event.data.json();
    title = data.title || title;
    body = data.body || '';
  } catch {
    body = event.data.text() || '';
  }

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: '/icons/icon-512.png',
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ('focus' in client) return client.focus();
      }
      return self.clients.openWindow('/budgets');
    })
  );
});
