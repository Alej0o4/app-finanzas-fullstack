'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { Bell, CheckCheck, BellOff, Loader2 } from 'lucide-react';
import {
  useNotifications,
  useUnreadCount,
  useMarkAsRead,
  useMarkAllAsRead,
} from '@/hooks/useNotifications';
import PushOptIn from '@/components/PushOptIn';
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
 * Campana de notificaciones del shell del dashboard (Fase 13 §13.5, Decisión 13.5.3):
 * ícono + badge numérico (oculto si 0) + popover con la bandeja. Mismo patrón
 * estructural que ChartControlsPopover (botón + panel absoluto + click-outside),
 * no su contenido. El poll corto del badge vive en su propia query (Decisión 13.5.4).
 */
export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const { data: unreadData } = useUnreadCount();
  const { data: notificationsData, isLoading, isError } = useNotifications();
  const markAsRead = useMarkAsRead();
  const markAllAsRead = useMarkAllAsRead();

  const unreadCount = unreadData?.count ?? 0;
  const notifications = notificationsData?.items ?? [];

  useEffect(() => {
    if (!open) return;

    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  const handleRowClick = (notification: AppNotification) => {
    if (!notification.read_at) {
      markAsRead.mutate(notification.id);
    }
  };

  const hasUnread = unreadCount > 0;

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

      {open && (
        <div className="border-border bg-surface-elevated shadow-background/40 absolute bottom-full left-0 z-50 mb-2 flex max-h-[70vh] w-80 flex-col overflow-hidden rounded-xl border shadow-xl backdrop-blur-sm">
          <div className="border-border/40 flex items-center justify-between gap-2 border-b px-3 py-2">
            <span className="text-text text-sm font-semibold">Notificaciones</span>
            <button
              type="button"
              onClick={() => markAllAsRead.mutate()}
              disabled={!hasUnread || markAllAsRead.isPending}
              className="text-text-muted hover:text-text hover:bg-surface flex cursor-pointer items-center gap-1 rounded-md px-1.5 py-1 text-[11px] transition-colors disabled:pointer-events-none disabled:opacity-40"
            >
              <CheckCheck size={12} />
              Marcar todas
            </button>
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
                        {!notification.read_at && (
                          <span className="bg-primary h-1.5 w-1.5 shrink-0 rounded-full" />
                        )}
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
      )}
    </div>
  );
}
