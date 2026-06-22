import axios from 'axios';

// Creamos la instancia base
export const api = axios.create({
  // En desarrollo usaremos localhost, en producción usaremos la variable de entorno
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
});

// Interceptor: Antes de que salga cualquier petición, revisa si hay un token
api.interceptors.request.use((config) => {
  // Para este MVP guardaremos el token en el LocalStorage
  const token = typeof window !== 'undefined' ? localStorage.getItem('jwt_token') : null;
  
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Interceptor: Si el backend devuelve un error 401 (token expirado/inválido), deslogueamos al usuario
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('jwt_token');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);