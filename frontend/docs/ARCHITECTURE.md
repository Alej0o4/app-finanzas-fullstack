# Arquitectura del Frontend

## Resumen

El frontend de Oikos está construido con Next.js App Router, React 19, TypeScript, TanStack Query, Axios, Zustand, Recharts y Tailwind CSS 4.

La aplicación está organizada por dominios funcionales y separa explícitamente la experiencia pública de autenticación de la experiencia protegida del dashboard.

## Estructura de alto nivel

- `app/`: rutas, layouts y páginas por dominio.
- `components/`: UI reutilizable, gráficos, modales y navegación.
- `lib/`: cliente HTTP, utilidades y hooks compartidos.
- `store/`: estado global de UI con Zustand.
- `public/`: assets estáticos.

## Flujo de renderizado

1. `app/layout.tsx` monta el layout raíz, la tipografía global y el `QueryProvider`.
2. `QueryProvider` crea una única instancia de `QueryClient` para toda la sesión.
3. `app/(auth)/layout.tsx` centra y simplifica la experiencia de acceso.
4. `app/(dashboard)/layout.tsx` monta la navegación lateral y el contenedor principal de la aplicación autenticada.
5. Las páginas de dominio consumen datos desde el backend a través de `lib/api.ts`.

## Layout raíz

### `app/layout.tsx`

Responsabilidades:

- Definir metadata base.
- Cargar la fuente `Plus Jakarta Sans`.
- Aplicar estilos globales desde `globals.css`.
- Envolver toda la app con `QueryProvider`.

Decisión importante:

- El provider de React Query vive en el layout raíz para compartir caché, invalidaciones y estado de red entre todas las rutas.

## Separación de layouts

### `app/(auth)/layout.tsx`

- Sirve como layout minimalista para login y futuras pantallas públicas de autenticación.
- Centra el contenido y aplica el fondo global.
- No monta sidebar ni navegación del dashboard.

### `app/(dashboard)/layout.tsx`

- Es el shell principal de la aplicación autenticada.
- Monta el `Sidebar` fijo.
- Ajusta el padding del contenido según si el sidebar está abierto o colapsado.
- Encapsula todas las rutas protegidas del negocio.

## Cliente de datos

### `components/QueryProvider.tsx`

- Crea el `QueryClient` una sola vez por sesión.
- Configura una política base de caché con `staleTime` de 1 minuto.
- Desactiva `refetchOnWindowFocus` para evitar tráfico innecesario al cambiar de pestaña.

### `lib/api.ts`

- Crea la instancia Axios base.
- Usa `NEXT_PUBLIC_API_URL` como backend target y cae a `http://localhost:8000` en desarrollo.
- Inserta automáticamente el JWT desde `localStorage` en `Authorization: Bearer <token>`.
- Ante un `401`, limpia el token y redirige a `/login`.

Regla importante:

- La app trata al backend como fuente de verdad. El frontend no recalcula saldos, progreso de presupuestos ni totales agregados.

## Estado de UI

### `store/useUiStore.ts`

- Guarda estado global de interfaz, hoy centrado en el sidebar.
- Controla `isSidebarOpen` y `toggleSidebar`.
- Se usa para coordinar el ancho del layout del dashboard y el estado visual de navegación.

Convención:

- Zustand se reserva para estado de UI; el estado de servidor se maneja con React Query.

## Navegación principal

### `components/Sidebar.tsx`

- Define la navegación del dashboard.
- Usa rutas agrupadas por dominio: dashboard, analítica, cuentas, transacciones, presupuestos y categorías.
- Lee `usePathname()` para resaltar la ruta activa.
- Se apoya en `useUiStore()` para expandir/colapsar la barra lateral.

## Hooks compartidos

### `lib/hooks/useCurrentUser.ts`

- Consulta el usuario autenticado mediante `GET /api/users/me`.
- Centraliza la lectura del perfil actual para no repetir la misma lógica en múltiples páginas.
- Debe usarse solo dentro de la experiencia autenticada.

## Componentes compartidos

### `components/modals/TransactionModal.tsx`

- Modal reutilizable para crear transacciones.
- Consulta cuentas y categorías solo cuando está abierto.
- Filtra categorías por tipo de transacción.
- Invalida las queries afectadas al guardar.

### `components/charts/BudgetRing.tsx`

- Visualiza el avance de presupuesto por categoría.
- Usa SVG y colores semánticos del sistema visual.
- Debe mantenerse agnóstico al origen de los datos; solo consume números ya validados.

## Páginas de dominio

Las páginas del dashboard deben limitarse a composición, fetching y UX local.

- `app/(dashboard)/page.tsx`: dashboard principal, resumen, presupuestos y transacciones recientes.
- `app/(dashboard)/analytics/page.tsx`: analítica financiera, cashflow y distribución por categorías.
- `app/(dashboard)/transactions/page.tsx`: feed de transacciones con filtros.
- `app/(dashboard)/accounts/page.tsx`: listado de cuentas.
- `app/(dashboard)/accounts/[id]/page.tsx`: detalle de cuenta.
- `app/(dashboard)/categories/page.tsx`: listado de categorías.
- `app/(dashboard)/categories/[id]/page.tsx`: detalle de categoría.
- `app/(dashboard)/budgets/page.tsx`: gestión de presupuestos.
- `app/(auth)/login/page.tsx`: acceso al sistema.

## Reglas de arquitectura

- Las páginas deben componer componentes y queries, no contener lógica de negocio financiera.
- Los cálculos de saldo, presupuesto y métricas agregadas viven en el backend.
- React Query es la fuente de verdad para estado remoto.
- Zustand solo debe usarse para estado de UI o preferencia local.
- Los modales y vistas detalladas deben invalidar queries al mutar datos.
- Los filtros del frontend deben transformarse a parámetros de consulta, no a cálculos locales.
- Las categorías base del sistema llegan con `user_id = null` y se tratan como datos compartidos.

## Sistema visual

- La tipografía global se define desde `app/layout.tsx`.
- Los tokens visuales se centralizan en `globals.css`.
- Las páginas de dominio deben respetar los tokens semánticos existentes.
- Los gráficos deben usar colores explícitos compatibles con SVG/Recharts.

## Validación recomendada

Cuando se cambie esta capa, validar en este orden:

1. `pnpm lint` en el frontend.
2. Verificación manual de login y dashboard.
3. Revisión de caché e invalidaciones en las páginas que mutan datos.
4. Confirmar que el layout del dashboard responde bien en colapsado/expandido.

## Relación con el backend

El frontend consume estos contratos como fuente de verdad:

- `GET /api/auth/login`
- `GET /api/users/me`
- `GET /api/accounts/`
- `GET /api/categories/`
- `GET /api/transactions/`
- `GET /api/budgets/`
- `GET /api/dashboard/summary`
- `GET /api/dashboard/budgets-progress`
- `GET /api/dashboard/cashflow-series`
- `GET /api/dashboard/category-distribution`

Cualquier cambio en esos contratos debe reflejarse en la documentación del backend y en esta arquitectura de frontend al mismo tiempo.
