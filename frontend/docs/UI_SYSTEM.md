# Sistema UI del Frontend

## Objetivo

Este proyecto usa un sistema visual sobrio, fintech y de alto contraste. La UI debe sentirse consistente entre páginas, gráficos, modales y navegación.

## Fundamento visual

### Tipografía

- Fuente principal: `Plus Jakarta Sans`.
- Definida en `app/layout.tsx` y expuesta por CSS variables.
- Uso recomendado:
  - títulos: peso semibold o bold;
  - textos secundarios: peso regular con color muted;
  - números financieros: preferiblemente con `font-sans` y peso medio o bold.

### Paleta semántica

Los tokens principales viven en `app/globals.css`.

- `background`: fondo general.
- `surface`: tarjetas y paneles.
- `surface-elevated`: hover, overlays y estados resaltados.
- `border`: líneas y separadores.
- `primary`: acento principal.
- `success`: resultados positivos.
- `warning`: alertas de presupuesto.
- `danger`: estados críticos y errores.
- `info`: soporte visual secundario.
- `text`: texto principal.
- `text-muted`: texto secundario.
- `text-soft`: texto intermedio.

## Tema base

El frontend opera sobre una paleta oscura fintech. La documentación y el código deben asumir ese marco visual, no el look por defecto de Next.js o Tailwind.

Reglas:

- Evitar colores hardcodeados fuera de los casos donde SVG/Recharts los requieran explícitamente.
- Mantener contraste alto entre texto y fondo.
- No introducir purple bias ni layouts genéricos de marketing.

## Componentes visuales de referencia

### Tarjetas

- Bordes redondeados amplios.
- Sombras sutiles.
- Fondo `surface` o `surface-elevated`.
- Uso de hover suave, no abrupto.

### Sidebar

- Barra lateral fija con estado expandido/colapsado.
- Se apoya en `useUiStore`.
- El item activo usa `primary` como estado dominante.

### Modales

- Overlay oscuro semitransparente.
- Backdrop blur ligero.
- Caja central con bordes amplios y sombra elevada.
- Botones de acción secundarios y primarios claramente diferenciados.

### Gráficos

- Recharts para analítica y distribuciones.
- Los colores deben definirse de forma explícita para evitar problemas con SVG y CSS variables.
- La paleta de categorías usa varios tonos del sistema para soportar más de cinco categorías.

## Tokens de gráfico

`app/globals.css` define una familia de colores de gráfico:

- `chart-1`
- `chart-2`
- `chart-3`
- `chart-4`
- `chart-5`
- `chart-6`
- `chart-7`
- `chart-8`
- `chart-9`
- `chart-10`

Uso recomendado:

- Distribuciones por categoría.
- Series múltiples en analytics.
- Leyendas con colores consistentes y deterministas.

## Patrones de interacción

- Estados de hover discretos y útiles.
- Feedback inmediato en botones y acciones destructivas.
- Formularios con labels pequeños, uppercased y espaciado claro.
- Acciones destructivas siempre deben ser explícitas.

## Reglas para pantallas de negocio

- Dashboard, cuentas, categorías, transacciones y presupuestos deben compartir el mismo lenguaje visual.
- Las páginas de detalle deben reutilizar patrones de lista y tarjeta.
- Las acciones de crear, editar y eliminar deben verse coherentes entre dominios.

## Accesibilidad mínima

- El texto principal debe mantener contraste alto sobre `background` y `surface`.
- Los iconos no deben ser la única señal de estado.
- Los botones necesitan texto, tooltip o contexto visible.
- Los filtros y selectores deben seguir siendo utilizables en viewport estrecho.

## Reglas de implementación

- Preferir tokens semánticos antes que valores arbitrarios.
- Usar `className` consistente con el sistema de colores.
- Si una pantalla necesita un nuevo patrón visual, documentarlo aquí antes de replicarlo en varias páginas.
