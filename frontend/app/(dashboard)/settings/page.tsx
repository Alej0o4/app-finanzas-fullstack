'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import { Check, Copy, KeyRound, Plus } from 'lucide-react';
import Switch from '@/components/ui/Switch';
import Skeleton from '@/components/ui/Skeleton';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import ModalShell from '@/components/ui/ModalShell';
import EmptyState from '@/components/ui/EmptyState';
import { useConfirmStore } from '@/store/useConfirmStore';
import { useUserPreferences } from '@/lib/hooks/useUserPreferences';
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from '@/lib/hooks/useApiKeys';
import { getApiError } from '@/lib/utils';
import type { components } from '@/types/generated/api';

type ApiKey = components['schemas']['ApiKeyResponse'];
type ApiKeyCreateResponse = components['schemas']['ApiKeyCreateResponse'];

// Fase 14 §14.6.2: primera superficie de ajustes del producto. Fase 16 §16.1 extiende la
// página con una segunda sección (gestión de API keys) — ver Decisión 16.1.6. No es el
// lugar para anticipar ajustes de cuenta (contraseña, email, etc.) que ninguna fase pide.
export default function SettingsPage() {
  const {
    preferences,
    isLoading: loadingPreferences,
    error,
    updatePreferences,
  } = useUserPreferences();

  // Valor del switch durante una mutación en vuelo: la query aún no lo confirma, así
  // que un "override" local deja que el switch responda al instante y se descarta
  // (revirtiendo a `preferences`) si el PATCH falla. Sin esto, el switch quedaría
  // desincronizado visualmente hasta la invalidación post-mutación.
  const [optimisticValue, setOptimisticValue] = useState<boolean | null>(null);

  // El default (true) coincide con el opt-out de la Decisión 14.1.1.
  const weeklySummaryEnabled = optimisticValue ?? preferences?.weekly_summary_enabled ?? true;

  const handleToggle = (checked: boolean) => {
    setOptimisticValue(checked);
    updatePreferences.mutate(
      { weekly_summary_enabled: checked },
      {
        onError: (err) => {
          // Revertir al valor confirmado por el servidor (el cache no se optimizó,
          // así que `preferences` sigue siendo el último valor confirmado).
          setOptimisticValue(null);
          toast.error(getApiError(err));
        },
      }
    );
  };

  // --- API keys (Fase 16 §16.1) ------------------------------------------------

  const apiKeysQuery = useApiKeys();
  const createApiKey = useCreateApiKey();
  const revokeApiKey = useRevokeApiKey();

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [nameError, setNameError] = useState('');
  // La key en texto plano SOLO aparece en la respuesta del POST (Decisión 16.1.5):
  // se guarda en estado local para mostrarla una única vez, nunca se vuelve a pedir.
  const [createdKey, setCreatedKey] = useState<ApiKeyCreateResponse | null>(null);
  const [copied, setCopied] = useState(false);

  const closeCreateModal = () => {
    setIsCreateOpen(false);
    setCreatedKey(null);
    setNewKeyName('');
    setNameError('');
    setCopied(false);
  };

  const openCreateModal = () => {
    setNameError('');
    setCreatedKey(null);
    setIsCreateOpen(true);
  };

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    const name = newKeyName.trim();
    if (!name) {
      setNameError('Ingresá un nombre para la API key.');
      return;
    }
    createApiKey.mutate(name, {
      onSuccess: (data) => {
        setCreatedKey(data);
        setNewKeyName('');
        setNameError('');
        // `createApiKey` ya invalidó ['apiKeys'] — la lista se refresca detrás del
        // modal; al cerrarlo la key nueva ya aparece en la fila.
      },
      onError: (err) => toast.error(getApiError(err)),
    });
  };

  const handleCopy = async () => {
    if (!createdKey) return;
    try {
      await navigator.clipboard.writeText(createdKey.key);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('No se pudo copiar la clave. Copiala manualmente antes de cerrar.');
    }
  };

  const handleRevoke = (key: ApiKey) => {
    useConfirmStore.getState().confirm(
      `¿Revocar la API key "${key.name}"? Las automatizaciones que la usan dejarán de funcionar de inmediato.`,
      () =>
        revokeApiKey.mutate(key.id, {
          onSuccess: () => toast.success('API key revocada'),
          onError: (err) => toast.error(getApiError(err)),
        }),
      'Revocar'
    );
  };

  return (
    <div className="relative space-y-6">
      <div>
        <h1 className="text-text font-sans text-xl font-bold sm:text-2xl">Ajustes</h1>
        <p className="text-text-muted text-xs sm:text-sm">Preferencias de tu cuenta.</p>
      </div>

      <section className="bg-surface border-border/70 rounded-2xl border p-4 sm:p-5">
        {loadingPreferences ? (
          <Skeleton className="h-12 w-full" />
        ) : error ? (
          <p className="text-text-muted text-sm">
            No se pudieron cargar las preferencias. Intenta de nuevo más tarde.
          </p>
        ) : (
          <Switch
            label="Resumen semanal"
            description="Recibe cada lunes un resumen de tus gastos de la semana"
            checked={weeklySummaryEnabled}
            onChange={(e) => handleToggle(e.target.checked)}
            disabled={updatePreferences.isPending}
          />
        )}
      </section>

      <section className="bg-surface border-border/70 rounded-2xl border p-4 sm:p-5">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-text font-sans text-base font-semibold">API keys</h2>
            <p className="text-text-muted mt-0.5 text-xs sm:text-sm">
              Claves para automatizaciones (Shortcuts, scripts) que no pueden hacer el login normal.
              Cada clave tiene los mismos permisos que tu cuenta.
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={openCreateModal} className="shrink-0">
            <Plus size={16} />
            <span className="hidden sm:inline">Nueva API key</span>
            <span className="sm:hidden">Nueva</span>
          </Button>
        </div>

        {apiKeysQuery.isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : apiKeysQuery.error ? (
          <p className="text-text-muted text-sm">
            No se pudieron cargar las API keys. Intenta de nuevo más tarde.
          </p>
        ) : apiKeysQuery.data && apiKeysQuery.data.length > 0 ? (
          <ul className="divide-border/40 divide-y">
            {apiKeysQuery.data.map((key) => {
              const isRevoked = !!key.revoked_at;
              const isRevoking = revokeApiKey.isPending && revokeApiKey.variables === key.id;
              return (
                <li
                  key={key.id}
                  className={`flex items-center justify-between gap-4 py-3 ${isRevoked ? 'opacity-60' : ''}`}
                >
                  <div className="min-w-0">
                    <p className="text-text text-sm font-medium">{key.name}</p>
                    <p className="text-text-muted mt-0.5 font-mono text-xs">{key.key_prefix}***</p>
                    <p className="text-text-muted mt-0.5 text-xs">
                      Último uso:{' '}
                      {key.last_used_at ? formatRelativeTime(key.last_used_at) : 'Nunca'}
                    </p>
                  </div>
                  {isRevoked ? (
                    <span className="text-text-muted bg-surface-elevated rounded-full px-2.5 py-1 text-[11px] font-medium whitespace-nowrap">
                      Revocada
                    </span>
                  ) : (
                    <button
                      onClick={() => handleRevoke(key)}
                      disabled={isRevoking}
                      className="text-text-muted hover:text-danger hover:bg-surface-elevated shrink-0 cursor-pointer rounded-lg px-2 py-1.5 text-sm transition-colors active:scale-95 disabled:opacity-50"
                    >
                      {isRevoking ? 'Revocando…' : 'Revocar'}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <EmptyState
            icon={<KeyRound size={28} />}
            message="Todavía no tenés API keys"
            description="Creá una para conectar un Shortcut de iOS o un script a tu cuenta."
          />
        )}
      </section>

      <ModalShell isOpen={isCreateOpen} onClose={closeCreateModal} title="Nueva API key">
        {createdKey ? (
          <div className="space-y-4">
            <div className="bg-surface-elevated/70 border-border/50 rounded-xl border p-3">
              <p className="text-text-muted text-xs leading-relaxed">
                Copiá la clave ahora:{' '}
                <strong className="text-text">no se va a volver a mostrar</strong>. Si la perdés,
                vas a tener que revocarla y crear otra.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <code className="bg-background border-border/70 text-text min-w-0 flex-1 truncate rounded-xl border px-3 py-2.5 font-mono text-xs">
                {createdKey.key}
              </code>
              <Button variant="secondary" onClick={handleCopy} className="shrink-0" type="button">
                {copied ? <Check size={16} /> : <Copy size={16} />}
                {copied ? 'Copiada' : 'Copiar'}
              </Button>
            </div>
            <div className="flex justify-end">
              <Button variant="primary" onClick={closeCreateModal} type="button">
                Listo
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleCreate} className="space-y-4" noValidate>
            <Input
              label="Nombre"
              placeholder="Ej: Shortcut iPhone"
              value={newKeyName}
              onChange={(e) => {
                setNewKeyName(e.target.value);
                if (nameError) setNameError('');
              }}
              error={nameError}
              maxLength={100}
              autoFocus
              className="bg-background"
            />
            <p className="text-text-muted text-xs">
              Elegí un nombre que te ayude a recordar dónde se va a usar la clave.
            </p>
            <div className="mt-6 flex gap-3">
              <Button type="button" variant="ghost" onClick={closeCreateModal} className="flex-1">
                Cancelar
              </Button>
              <Button
                type="submit"
                variant="primary"
                loading={createApiKey.isPending}
                className="flex-1"
              >
                Crear
              </Button>
            </div>
          </form>
        )}
      </ModalShell>
    </div>
  );
}

/** Tiempo relativo simple en español (no existe helper en lib/ — formateador local,
 *  mismo patrón que NotificationBell.tsx). */
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
