# Guía de Componentes

## Objetivo

Este documento resume los componentes reutilizables del frontend y las reglas para extenderlos sin romper consistencia visual o de datos.

## Principio general

Antes de crear un nuevo componente, revisar si ya existe una pieza reutilizable para:

- navegación;
- modales;
- gráficos;
- layout de listas;
- formularios de alta y edición.

## Componentes principales

### `components/QueryProvider.tsx`

Responsabilidad:

- Proveer `QueryClientProvider` a toda la app.

Cuándo tocarlo:

- Solo si cambian las reglas globales de caché o refetch.

### `components/Sidebar.tsx`

Responsabilidad:

- Navegación principal del dashboard.
- Toggle de colapso/expansión.
- Resaltar ruta activa.

Reglas:

- No meter lógica de negocio en el sidebar.
- Mantener el mapa de rutas alineado con el dashboard real.

### `components/modals/TransactionModal.tsx`

Responsabilidad:

- Crear transacciones desde un modal reutilizable.

Props principales:

- `isOpen`
- `onClose`
- `onSuccess?`
- `defaultType?`
- `title?`

Comportamiento:

- Carga cuentas y categorías solo cuando el modal está abierto.
- Filtra categorías por tipo de transacción.
- Invalida las queries afectadas al guardar.

Reglas:

- No duplicar este formulario en otras pantallas.
- Si se modifica el payload, actualizar también la documentación de API.

### `components/charts/BudgetRing.tsx`

Responsabilidad:

- Pintar el estado de ejecución de un presupuesto.

Props principales:

- `categoryName`
- `budgetAmount`
- `spentAmount`

Comportamiento:

- Calcula porcentaje consumido.
- Limita el porcentaje entre 0 y 100.
- Usa colores semánticos para estados normal, warning y danger.

Reglas:

- No pasarle cadenas sin convertir a número.
- No depender de variables CSS dentro de SVG si el render es inestable; preferir colores compatibles con SVG/Recharts.

## Componentes por dominio

### Dashboard

- Usa `BudgetRing`.
- Puede incluir bloques de métricas y transacciones recientes.
- Debe delegar el formulario de creación a `TransactionModal`.

### Analytics

- Usa Recharts directamente.
- La lógica de colores para categorías debe mantenerse local a la vista mientras no exista un componente compartido.

### Cuentas y categorías

- Usan tarjetas con lista y acciones flotantes.
- Los modales de creación/edición todavía son específicos de cada pantalla, salvo que se extraigan en una iteración futura.

## Reglas de diseño para nuevos componentes

- Deben usar tokens semánticos del sistema visual.
- Deben recibir props claras y serializables.
- Deben evitar lógica de negocio pesada.
- Si necesitan datos del servidor, hacerlo mediante React Query y no con fetch suelto.

## Convenciones de composición

- Las páginas deben componer componentes pequeños en lugar de contener JSX repetido.
- Los componentes reutilizables deben tener responsabilidad única.
- Los componentes con side effects deben documentar sus invalidaciones de queries.

## Recomendación práctica

Si una UI aparece dos veces, primero pensar en un componente compartido. Si una regla de negocio aparece dos veces, primero pensar en una abstracción de contrato o una query compartida.
