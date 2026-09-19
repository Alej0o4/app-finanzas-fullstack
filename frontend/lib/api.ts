import axios from 'axios';

export const api = axios.create({
  baseURL: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1`,
  withCredentials: true, // 🆕 Fase 26 — manda/recibe los cookies httpOnly de sesión
});

// 🆕 Fase 26: lee el cookie NO-httpOnly csrf_token (Decisión B1/B5 del backend — mismo
// nombre, contrato compartido) para el patrón double-submit. No hay librería de cookies en
// el proyecto todavía; un regex sobre document.cookie alcanza para un solo valor.
function leerCsrfTokenDeCookie(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(/(?:^|; )csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

let isRefreshing = false;
let failedQueue: Array<{ resolve: () => void; reject: (error: unknown) => void }> = [];

function processQueue(error: unknown) {
  failedQueue.forEach(({ resolve, reject }) => (error ? reject(error) : resolve()));
  failedQueue = [];
}

// 🆕 Fase 26: reemplaza al interceptor de Authorization — ya no arma el header del JWT
// (el cookie viaja solo), solo agrega X-CSRF-Token en mutaciones.
api.interceptors.request.use((config) => {
  const metodo = (config.method || 'get').toUpperCase();
  if (metodo !== 'GET' && metodo !== 'HEAD') {
    const csrfToken = leerCsrfTokenDeCookie();
    if (csrfToken) config.headers['X-CSRF-Token'] = csrfToken;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // La propia llamada de refresh pasa por este mismo interceptor (usa `api`, no `axios`
    // crudo — Hallazgo 3/Decisión F1). Si el refresh token ya expiró, el backend le
    // responde 401 a ESTA request: sin este guard, entraría de nuevo al bloque de abajo,
    // se encolaría en failedQueue esperando a que `processQueue` la resuelva — pero
    // `processQueue` solo corre después de que el `await api.post('auth/refresh')` de más
    // abajo se resuelva, que es justo lo que está esperando. Deadlock: ninguna de las dos
    // promesas se resuelve nunca y el usuario queda con la UI colgada en vez de ir a
    // /login. Se corta acá para que rechace normal y el catch de abajo la maneje.
    if (originalRequest.url === 'auth/refresh') {
      return Promise.reject(error);
    }

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise<void>((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(() => api(originalRequest));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // 🆕 Fase 26 (Hallazgo 3): usa `api`, no `axios` crudo — si no, withCredentials
        // no aplica y el cookie refresh_token nunca viaja acá.
        await api.post('auth/refresh');
        processQueue(null);
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError);
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);
