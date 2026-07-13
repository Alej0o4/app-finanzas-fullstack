# Despliegue del Frontend

## Objetivo

Este archivo resume las variables, comandos y supuestos operativos del frontend de Oikos.

## Variables de entorno

### `NEXT_PUBLIC_API_URL`

- URL base del backend.
- Ejemplo local: `http://localhost:8000`
- Si no está definida, el cliente cae a `http://localhost:8000`.

## Scripts del proyecto

- `pnpm dev`: desarrollo local.
- `pnpm build`: build de producción.
- `pnpm start`: arranque de producción.
- `pnpm lint`: revisión estática.

## Flujo de despliegue recomendado

### Con Docker (recomendado)

```sh
# Producción
docker compose up -d --build

# Desarrollo (hot-reload, sin rebuilds)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

`NEXT_PUBLIC_API_URL` se inyecta como build-time arg en `docker-compose.yml`. Para cambiarla, reconstruir con `--build`.

### Sin Docker

1. Definir la URL del backend en `NEXT_PUBLIC_API_URL`.
2. Ejecutar `pnpm install`.
3. Ejecutar `pnpm build` para validar el bundle.
4. Iniciar con `pnpm start` o desplegar en el proveedor elegido.

## Supuestos operativos

- El backend debe estar disponible y autenticable antes de usar el frontend.
- El JWT se guarda en `localStorage` y se envía por interceptor Axios.
- Un `401` fuerza limpieza del token y retorno al login.
- La app espera que las rutas protegidas existan detrás de un backend funcional.

## Consideraciones para producción

- Usar HTTPS.
- Asegurar que `NEXT_PUBLIC_API_URL` apunte al backend correcto.
- Verificar que el backend permita el origen del frontend en CORS.
- Revalidar la política de almacenamiento del token si se migra a cookies seguras.

## Riesgos actuales

- El token vive en `localStorage`.
- No hay observabilidad ni logging de frontend centralizado.
- No hay feature flagging ni despliegue por entornos múltiples.

## Checklist previo a release

- `pnpm lint`
- `pnpm build`
- Login funcional contra el backend real.
- Dashboard carga datos protegidos correctamente.
- Navegación entre cuentas, categorías, transacciones y presupuestos funciona con el backend conectado.
