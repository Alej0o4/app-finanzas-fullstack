'use client';

import { useCallback, useState, useRef, useEffect, useLayoutEffect } from 'react';
import { createPortal } from 'react-dom';
import Link from 'next/link';
import {
  Bell,
  CheckCheck,
  BellOff,
  Loader2,
  X,
  Trash2,
  CalendarDays,
  AlertTriangle,
} from 'lucide-react';
import {
  useNotifications,
  useUnreadCount,
  useMarkAsRead,
  useMarkAllAsRead,
  useDeleteNotification,
  useDeleteReadNotifications,
} from '@/hooks/useNotifications';
import PushOptIn from '@/components/PushOptIn';
import { useEscapeToClose } from '@/lib/hooks/useEscapeToClose';
import type { AppNotification } from '@/types/api';

/** Tiempo relativo simple en español (no existe helper en lib/ — formateador local). */
function formatRelativeTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const diffMs = Date.now() - date.getTime();
  const minutes = Math.floor(diffMs / 60_000);

  if (minutes < 1) return 'ahora mismo';
  if (minutes < 60) return `hace ${minutes} min`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `hace ${days} d`;

  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `hace ${weeks} sem`;

  const months = Math.floor(days / 30);
  if (months < 12) return `hace ${months} mes${months > 1 ? 'es' : ''}`;

  const years = Math.floor(days / 365);
  return `hace ${years} año${years > 1 ? 's' : ''}`;
}

/**
 * Ícono de la fila según el tipo de aviso (Fase 14 §14.5.1, cosmético): calendario para
 * el resumen semanal, alerta para los umbrales de presupuesto de Fase 13.
 */
function NotificationTypeIcon({ type }: { type: string }) {
  const Icon = type === 'weekly_summary' ? CalendarDays : AlertTriangle;
  return (
    <span className="text-text-muted shrink-0" aria-hidden="true">
      <Icon size={14} />
    </span>
  );
}

/**
 * Campana de notificaciones del shell del dashboard (Fase 13 §13.5, Decisión 13.5.3):
 * ícono + badge numérico (oculto si 0) + popover con la bandeja. Mismo patrón
 * estructural que ChartControlsPopover (botón + panel absoluto + click-outside),
 * no su contenido. El poll corto del badge vive en su propia query (Decisión 13.5.4).
 */
export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  // Inicializar con el valor correcto en cliente para evitar que el primer click
  // vea `false` en móvil (el `useEffect` corre después del primer render/hidratación).
  // En servidor no hay `window`, así que SSR renderiza `false` (popover).
  const [isMobileSheet, setIsMobileSheet] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia('(max-width: 639.98px)').matches : false
  );
  const ref = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const { data: unreadData } = useUnreadCount();
  const { data: notificationsData, isLoading, isError } = useNotifications();
  const markAsRead = useMarkAsRead();
  const markAllAsRead = useMarkAllAsRead();
  const deleteNotification = useDeleteNotification();
  const deleteRead = useDeleteReadNotifications();

  const unreadCount = unreadData?.count ?? 0;
  const notifications = notificationsData?.items ?? [];
  const hasRead = notifications.some((n) => n.read_at !== null);

  // Fase 33 F7 (QA-036, US 20/21): sincronizar con el viewport usando `useLayoutEffect`
  // para que el valor esté listo **antes** del primer paint y no haya mismatch de hidratación
  // ni parpadeo. `useLayoutEffect` corre sincrónicamente tras mutaciones del DOM.
  useLayoutEffect(() => {
    const mq = window.matchMedia('(max-width: 639.98px)');
    const sync = (e: MediaQueryListEvent | MediaQueryList) => setIsMobileSheet(e.matches);
    sync(mq);
    mq.addEventListener('change', sync);
    return () => mq.removeEventListener('change', sync);
  }, []);

  // Fase 33 F7 (QA-036, US 22): Escape cierra el panel en los dos formatos (hoja en móvil,
  // popover en desktop), combinado con el click-outside de abajo. `close` va en `useCallback`
  // porque el hook de Escape lo tiene como dependencia: un arrow inline re-registraría el
  // listener en cada render.
  const close = useCallback(() => setOpen(false), []);
  useEscapeToClose(open, close);

  useEffect(() => {
    if (!open) return;

    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node;
      // En la hoja de móvil el panel está en un portal (ver `panel` más abajo), así que
      // `ref` —la campana— no lo contiene: sin esta segunda comprobación, cualquier clic
      // dentro de la bandeja la cerraría antes de que el botón de esa fila actuara.
      if (ref.current?.contains(target)) return;
      if (panelRef.current?.contains(target)) return;
      close();
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open, close]);

  const handleRowClick = (notification: AppNotification) => {
    // Fase 33 F7: en la hoja de móvil una fila puede navegar (`/budgets`), y esa navegación
    // cierra el drawer del Sidebar — la hoja está en un portal, así que sobreviviría flotando
    // sobre la pantalla nueva. Solo en `<sm`: en escritorio el popover se queda como siempre.
    if (isMobileSheet) close();
    if (!notification.read_at) {
      markAsRead.mutate(notification.id);
    }
  };

  const hasUnread = unreadCount > 0;

  // Fase 33 F7 (QA-036): la hoja de móvil se monta en un portal a `document.body` porque su
  // panel es `fixed` y la campana vive dentro del `<aside>` del Sidebar, que lleva `translate`
  // (Tailwind v4 compila `translate-x-0` a la propiedad CSS `translate`): todo valor distinto
  // de `none` convierte a ese `<aside>` en bloque contenedor, así que el `fixed` se mediría
  // contra los 256 px del drawer y, con el drawer cerrado (`-translate-x-full`), la hoja
  // quedaría fuera de la pantalla. En el portal el `fixed` sí resuelve contra el viewport.
  // `document.body` solo se evalúa con el panel ya abierto, algo que en el servidor no pasa
  // (`open` arranca en `false`), así que el HTML del SSR no cambia.
  const panel = open && (
    // Fase 33 F7 (QA-036, US 20/21): en `<sm` la bandeja deja de ser un popover anclado a
    // la campana (`left-0 w-80` arrancaba en x≈160 dentro del drawer y se salía de un
    // celular de 390 px) y pasa a ser una hoja fija con 12 px de gutter a cada lado
    // (`inset-x-3`): a 390 px quedan 366 px de ancho, entera y con el `PushOptIn` del pie
    // visible. Desde `sm` vuelve a ser el popover de siempre. Los resets `sm:` son
    // obligatorios — sin `inset-x-auto`, `top-auto`, `bottom-full` y `left-0` el
    // `bottom-full` de escritorio se leería en la variante fija y el `inset-x-3` ganaría al
    // `left-0`. El `z-50` de siempre alcanza para quedar sobre el drawer (`z-40`): con
    // `max-h-[70vh]` la hoja no llega nunca a la franja del banner de instalación.
    <div
      ref={panelRef}
      className="border-border bg-surface-elevated shadow-background/40 fixed inset-x-3 top-20 z-50 flex max-h-[70vh] flex-col overflow-hidden rounded-xl border shadow-xl backdrop-blur-sm sm:absolute sm:inset-x-auto sm:top-auto sm:bottom-full sm:left-0 sm:mb-2 sm:w-80"
    >
      <div className="border-border/40 flex items-center justify-between gap-1 border-b px-3 py-2">
        <span className="text-text text-sm font-semibold">Notificaciones</span>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={() => markAllAsRead.mutate()}
            disabled={!hasUnread || markAllAsRead.isPending}
            className="text-text-muted hover:text-text hover:bg-surface flex cursor-pointer items-center gap-1 rounded-md px-1.5 py-1 text-[11px] transition-colors disabled:pointer-events-none disabled:opacity-40"
          >
            <CheckCheck size={12} />
            Marcar todas
          </button>
          <button
            type="button"
            onClick={() => deleteRead.mutate()}
            disabled={!hasRead || deleteRead.isPending}
            className="text-text-muted hover:text-danger hover:bg-surface flex cursor-pointer items-center gap-1 rounded-md px-1.5 py-1 text-[11px] transition-colors disabled:pointer-events-none disabled:opacity-40"
          >
            <Trash2 size={12} />
            Eliminar leídas
          </button>
        </div>
      </div>

      <div className="overflow-y-auto">
        {isLoading ? (
          <div className="text-text-muted flex items-center justify-center gap-2 p-6 text-sm">
            <Loader2 size={14} className="animate-spin" />
            Cargando...
          </div>
        ) : isError && notifications.length === 0 ? (
          <div className="text-text-muted p-6 text-center text-sm">
            No se pudieron cargar las notificaciones.
          </div>
        ) : notifications.length === 0 ? (
          <div className="text-text-muted flex flex-col items-center gap-2 p-6 text-center text-sm">
            <BellOff size={20} className="opacity-40" />
            <span>No tienes notificaciones todavía.</span>
          </div>
        ) : (
          <ul className="divide-border/40 divide-y">
            {notifications.map((notification) => (
              <li key={notification.id}>
                <div
                  className={`hover:bg-surface flex cursor-pointer flex-col gap-0.5 px-3 py-2.5 text-left transition-colors ${
                    notification.read_at ? '' : 'bg-background/40'
                  }`}
                  onClick={() => handleRowClick(notification)}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2">
                      <NotificationTypeIcon type={notification.type} />
                      {notification.budget_id !== null ? (
                        <Link
                          href="/budgets"
                          className="text-text hover:text-primary min-w-0 truncate text-xs font-semibold transition-colors"
                        >
                          {notification.title}
                        </Link>
                      ) : (
                        <span className="text-text min-w-0 truncate text-xs font-semibold">
                          {notification.title}
                        </span>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                      {!notification.read_at && (
                        <span className="bg-primary h-1.5 w-1.5 rounded-full" />
                      )}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteNotification.mutate(notification.id);
                        }}
                        aria-label="Eliminar notificación"
                        className="text-text-muted hover:text-danger hover:bg-background cursor-pointer rounded p-0.5 transition-colors"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  </div>
                  <p className="text-text-muted text-xs leading-snug">{notification.body}</p>
                  <span className="text-text-muted/70 text-[10px]">
                    {formatRelativeTime(notification.created_at)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
      <PushOptIn />
    </div>
  );

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="text-text-muted hover:text-text hover:bg-surface-elevated relative cursor-pointer rounded-lg p-1.5 transition-colors active:scale-95"
        aria-label={
          open
            ? 'Cerrar notificaciones'
            : `Abrir notificaciones${hasUnread ? `, ${unreadCount} sin leer` : ''}`
        }
        aria-expanded={open}
      >
        <Bell size={16} />
        {hasUnread && (
          <span className="bg-danger text-background absolute top-0 right-0 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[9px] font-bold tabular-nums">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {isMobileSheet ? createPortal(panel, document.body) : panel}
    </div>
  );
}
