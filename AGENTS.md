# AGENTS.md — Oikos

## Propósito

Este repositorio contiene Oikos, una aplicación web de finanzas personales con:

- Backend en FastAPI + SQLAlchemy + Pydantic + JWT.
- Frontend en Next.js App Router + React 19 + TypeScript + TanStack Query + Zustand + Recharts + Tailwind CSS 4.
- Base de datos SQLite en desarrollo.

La regla principal para cualquier agente es no saturar este archivo con detalles de implementación. Úsalo como mapa de navegación y consulta la documentación específica solo cuando la tarea lo requiera.

## Cómo leer este repo

1. Empieza por este archivo para entender el contexto general.
2. Consulta la documentación especializada solo del área que vas a tocar.
3. Si una regla ya está documentada en el backend o en el frontend, respétala como fuente de verdad.
4. Si cambias un contrato compartido, actualiza la documentación correspondiente en ambos lados.

## Mapa de documentación

### Backend

- [README del backend](backend/README.md): entrada breve del backend y alcance general.
- [Arquitectura del backend](backend/docs/ARCHITECTURE.md): capas, flujo de autenticación y limitaciones.
- [Referencia de API](backend/docs/API_REFERENCE.md): endpoints, payloads, parámetros y respuestas.
- [Reglas de negocio](backend/docs/BUSINESS_RULES.md): invariantes del dominio y restricciones.
- [Integración con frontend](backend/docs/FRONTEND_INTEGRATION.md): contratos y reglas para el cliente web.
- [Despliegue y operación](backend/docs/DEPLOYMENT.md): variables, riesgos operativos y recomendaciones.

### Frontend

- [README del frontend](frontend/README.md): entrada breve del frontend y estructura general.
- [Arquitectura del frontend](frontend/docs/ARCHITECTURE.md): layouts, providers, estado y composición.
- [Contrato de API del frontend](frontend/docs/API_CONTRACT.md): cómo consumir el backend desde Next.js.
- [Sistema UI](frontend/docs/UI_SYSTEM.md): tokens visuales, tipografía, gráficos y patrones de diseño.
- [Estado y fetching](frontend/docs/STATE_AND_FETCHING.md): React Query, Zustand, query keys e invalidaciones.
- [Guía de componentes](frontend/docs/COMPONENTS_GUIDE.md): componentes reutilizables y reglas de composición.
- [Despliegue del frontend](frontend/docs/DEPLOYMENT.md): variables de entorno, scripts y supuestos de operación.

### Deuda técnica consciente

- [Deuda técnica](TODO_TECH_DEBT.md): lista viva de atajos aceptados durante el MVP.

## Reglas de arquitectura

- El backend es la fuente de verdad para saldos, presupuestos, agregados y reglas contables.
- El frontend no debe recalcular métricas financieras que ya devuelve el backend.
- Las categorías con `user_id = null` son compartidas del sistema y no se editan ni eliminan.
- Las mutaciones deben invalidar las queries relacionadas para mantener sincronía entre vistas.
- Mantén los routers FastAPI delgados; si una regla crece, considera extraerla antes de duplicarla.

## Convenciones de trabajo

- Prioriza cambios pequeños y focalizados.
- No reescribas documentación general si existe una doc específica para ese tema.
- Antes de tocar UI o fetching, revisa la arquitectura del frontend y el contrato de API.
- Antes de tocar reglas de dominio o validación, revisa las reglas de negocio del backend.
- No elimines ni sobreescribas documentación existente sin una razón clara.

## Cuándo consultar documentación

- Cambios de endpoint o payload: revisar [backend/docs/API_REFERENCE.md](backend/docs/API_REFERENCE.md) y [frontend/docs/API_CONTRACT.md](frontend/docs/API_CONTRACT.md).
- Cambios de reglas de negocio: revisar [backend/docs/BUSINESS_RULES.md](backend/docs/BUSINESS_RULES.md).
- Cambios de layout, estado, queries o componentes: revisar [frontend/docs/ARCHITECTURE.md](frontend/docs/ARCHITECTURE.md), [frontend/docs/STATE_AND_FETCHING.md](frontend/docs/STATE_AND_FETCHING.md) y [frontend/docs/COMPONENTS_GUIDE.md](frontend/docs/COMPONENTS_GUIDE.md).
- Cambios visuales: revisar [frontend/docs/UI_SYSTEM.md](frontend/docs/UI_SYSTEM.md).
- Cambios operativos o de entorno: revisar [backend/docs/DEPLOYMENT.md](backend/docs/DEPLOYMENT.md) y [frontend/docs/DEPLOYMENT.md](frontend/docs/DEPLOYMENT.md).

## Validación mínima

- Backend: valida el archivo tocado y, si aplica, ejecuta pruebas o chequeos focalizados.
- Frontend: valida el archivo tocado con lint o checks específicos.
- Documentación: confirma que los enlaces, nombres de archivos y contratos coinciden con el código actual.

## Estado del proyecto

- El frontend ya tiene documentación propia y no debe depender del README genérico.
- El backend mantiene la documentación canónica del dominio y del contrato de API.
- Este archivo debe permanecer breve; si una tarea necesita más detalle, consulta la doc especializada correspondiente.