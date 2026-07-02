# Frontend de Finanzas Personales

Interfaz web para Oikos, construida con Next.js App Router, React, TypeScript, TanStack Query y Tailwind CSS.

## Alcance funcional

- Autenticación con JWT contra el backend FastAPI.
- Dashboard con métricas agregadas, gráfico de flujo y resumen visual.
- Gestión de cuentas, categorías, presupuestos y transacciones.
- Detalles por cuenta y categoría con historial asociado.
- Filtros de feed, modales reutilizables y componentes compartidos.

## Stack

- Next.js 16
- React 19
- TypeScript
- TanStack Query
- Axios
- Zustand
- Recharts
- Tailwind CSS 4
- lucide-react

## Estructura principal

- `app/`: rutas y layouts por dominio.
- `components/`: componentes reutilizables, gráficos y modales.
- `lib/`: cliente HTTP, utilidades y hooks compartidos.
- `store/`: estado UI global con Zustand.
- `public/`: assets estáticos.

## Puntos de entrada

- Auth: `app/(auth)/login/page.tsx`
- Dashboard: `app/(dashboard)/page.tsx`
- Transacciones: `app/(dashboard)/transactions/page.tsx`
- Cuentas: `app/(dashboard)/accounts/page.tsx`
- Categorías: `app/(dashboard)/categories/page.tsx`
- Presupuestos: `app/(dashboard)/budgets/page.tsx`
- Analítica: `app/(dashboard)/analytics/page.tsx`

## Arranque local

1. Instalar dependencias con `pnpm install`.
2. Definir `NEXT_PUBLIC_API_URL` apuntando al backend, por ejemplo `http://localhost:8000`.
3. Ejecutar `pnpm dev`.
4. Abrir `http://localhost:3000`.

## Scripts

- `pnpm dev`: desarrollo.
- `pnpm build`: build de producción.
- `pnpm start`: servidor de producción.
- `pnpm lint`: lint del frontend.

## Integración con backend

- El token JWT se lee desde `localStorage` y se envía como `Authorization: Bearer <token>`.
- El frontend no recalcula saldos, progreso de presupuestos ni totales del dashboard.
- Las categorías con `user_id = null` son compartidas del sistema.
- Las transacciones y sus detalles se consumen desde el backend como fuente de verdad.

## Documentación relacionada

- Arquitectura del frontend: `docs/ARCHITECTURE.md`
- Contrato de API: `docs/API_CONTRACT.md`
- Sistema UI: `docs/UI_SYSTEM.md`
- Estado y fetching: `docs/STATE_AND_FETCHING.md`
- Despliegue: `docs/DEPLOYMENT.md`
