'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { Check, Copy, KeyRound, Plus, Trash2 } from 'lucide-react';
import Switch from '@/components/ui/Switch';
import Skeleton from '@/components/ui/Skeleton';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import ModalShell from '@/components/ui/ModalShell';
import EmptyState from '@/components/ui/EmptyState';
import Select from '@/components/ui/Select';
import { useConfirmStore } from '@/store/useConfirmStore';
import { useUserPreferences } from '@/lib/hooks/useUserPreferences';
import { useCurrentUser } from '@/lib/hooks/useCurrentUser';
import { useSetMonthlyIncome } from '@/lib/hooks/useSetMonthlyIncome';
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from '@/lib/hooks/useApiKeys';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import { getApiError } from '@/lib/utils';
import type { components } from '@/types/generated/api';

type ApiKey = components['schemas']['ApiKeyResponse'];
type ApiKeyCreateResponse = components['schemas']['ApiKeyCreateResponse'];
// Código nuevo usa tipos generados (Decisión 16.3.2): AccountResponse, no el Account
// manual de types/api.ts que budgets/page.tsx todavía usa.
type Account = components['schemas']['AccountResponse'];

// Fase 14 §14.6.2: primera superficie de ajustes del producto. Fase 16 §16.1 agrega la
// gestión de API keys — ver Decisión 16.1.6. Fase 21 §21.1/§21.2 suma la moneda principal
// y la baja de cuenta — ver docs/specs/fase_21_spec.md.
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

  // Fase 21 §21.1 (Decisión 21.1.1): monedas del selector derivadas de las cuentas
  // reales del usuario (misma queryKey que accounts/, ya en cache si visitó /accounts
  // o /budgets antes) — nunca una lista fija.
  const { data: accounts } = useQuery<Account[]>({
    queryKey: queryKeys.accounts.all(),
    queryFn: async () => (await api.get('accounts/')).data,
  });
  const availableCurrencies = Array.from(new Set(accounts?.map((a) => a.currency) ?? []));

  // --- Ingreso mensual (Fase 22 §22.3, Decisión 22.3.1) -----------------------------
  // El salario es un campo numérico de texto libre: pedir un PATCH en cada tecla sería
  // ruidoso, así que usa el patrón de OnboardingIncomeStep (Input + submit explícito),
  // no el de "cambio = guardado" del selector de moneda y el switch.
  const { data: currentUser } = useCurrentUser();
  const setMonthlyIncome = useSetMonthlyIncome();
  const [incomeValue, setIncomeValue] = useState('');
  // `currentUser` carga async — `monthly_income` puede llegar después del primer render.
  // Se precarga ajustando estado durante el render con el patrón oficial de React
  // ("storing information from previous renders", react.dev/reference/react/useState):
  // `prevMonthlyIncome` recuerda el último valor visto de la query y `incomeValue === ''`
  // evita pisar lo que el usuario esté tipeando si la query se refresca.
  const [prevMonthlyIncome, setPrevMonthlyIncome] = useState<number | null>(null);
  // `undefined ?? null` normaliza la query sin cargar (currentUser undefined) a null,
  // igual que `prevMonthlyIncome` — si se comparara `undefined !== null` el estado
  // nunca se estabilizaría y React entraría en bucle (rompió el prerender de /settings).
  const currentIncome = currentUser?.monthly_income ?? null;
  if (currentIncome !== prevMonthlyIncome) {
    setPrevMonthlyIncome(currentIncome);
    if (currentIncome != null && incomeValue === '') {
      setIncomeValue(String(currentIncome));
    }
  }

  const handleIncomeSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const parsed = Number(incomeValue);
    if (!incomeValue.trim() || Number.isNaN(parsed) || parsed < 0) return;
    setMonthlyIncome.mutate(parsed, {
      onSuccess: () => toast.success('Ingreso mensual actualizado.'),
      onError: (err) => toast.error(getApiError(err)),
    });
  };

  // --- Baja de cuenta (Fase 21 §21.2) ---------------------------------------------

  const queryClient = useQueryClient();
  const router = useRouter();

  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [password, setPassword] = useState('');
  const [passwordError, setPasswordError] = useState('');

  const deleteAccount = useMutation({
    mutationFn: async (password: string) => {
      await api.delete('users/me', { data: { password } });
    },
    onSuccess: () => {
      localStorage.removeItem('jwt_token');
      localStorage.removeItem('refresh_token');
      // queryClient.clear(), no invalidar: no debe quedar ningún dato del usuario
      // borrado accesible en memoria aunque el navegador quede abierto.
      queryClient.clear();
      toast.success('Tu cuenta fue eliminada.');
      router.push('/login');
    },
    onError: (err) => setPasswordError(getApiError(err)),
  });

  // Fase 22 §22.4 (Decisión 22.4.2): default seguro mientras carga — el campo de
  // contraseña solo se oculta cuando el backend confirma que la cuenta no tiene
  // (`has_password: false`, cuenta Google-only).
  const requiresPassword = currentUser?.has_password !== false;

  const closeDeleteModal = () => {
    setIsDeleteOpen(false);
    setPassword('');
    setPasswordError('');
  };

  const handleDeleteSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (requiresPassword && !password) return;
    // Para cuentas Google-only el backend saltea el chequeo de contraseña (Hallazgo 6) —
    // se envía vacío sin pedirla.
    deleteAccount.mutate(requiresPassword ? password : '');
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
        <div className="mb-4">
          <h2 className="text-text font-sans text-base font-semibold">Cuenta</h2>
          <p className="text-text-muted mt-0.5 text-xs sm:text-sm">
            La moneda que usás para ver tus balances y métricas del dashboard.
          </p>
        </div>
        {/* Fase 21 §21.1 (Decisión 21.1.1): se muestra siempre, aunque haya una sola
            moneda — mismo criterio que el selector de presupuestos (17.2.4). */}
        <Select
          label="Moneda principal"
          value={preferences?.preferred_currency ?? ''}
          onChange={(e) =>
            updatePreferences.mutate(
              { preferred_currency: e.target.value },
              { onError: (err) => toast.error(getApiError(err)) }
            )
          }
          disabled={updatePreferences.isPending}
          className="bg-background"
        >
          {availableCurrencies.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </Select>
      </section>

      {/* Fase 22 §22.3 (Decisión 22.3.1): salario editable, contiguo a la moneda — agrupa
          los dos datos financieros de perfil en vez de intercalarlos con ajustes técnicos.
          Sin historial (Decisión C2): un único valor, sobreescrito. */}
      <section className="bg-surface border-border/70 rounded-2xl border p-4 sm:p-5">
        <div className="mb-4">
          <h2 className="text-text font-sans text-base font-semibold">Ingreso mensual</h2>
          <p className="text-text-muted mt-0.5 text-xs sm:text-sm">
            Se usa para calcular cuánto te queda cada mes en el dashboard.
          </p>
        </div>
        <form onSubmit={handleIncomeSubmit} className="flex items-end gap-3">
          <Input
            type="number"
            inputMode="decimal"
            min={0}
            step="0.01"
            label="Monto mensual aproximado"
            value={incomeValue}
            onChange={(e) => setIncomeValue(e.target.value)}
            className="bg-background"
          />
          <Button type="submit" variant="secondary" loading={setMonthlyIncome.isPending}>
            Guardar
          </Button>
        </form>
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

      {/* Zona de peligro (Fase 21 §21.2, Decisión 21.2.6) — al final, después de API keys */}
      <section className="bg-surface border-border/70 rounded-2xl border p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-text font-sans text-base font-semibold">Zona de peligro</h2>
            <p className="text-text-muted mt-0.5 text-xs sm:text-sm">
              Acciones irreversibles sobre tu cuenta.
            </p>
          </div>
          <Button
            variant="danger"
            size="sm"
            onClick={() => setIsDeleteOpen(true)}
            className="shrink-0"
          >
            <Trash2 size={16} />
            Eliminar mi cuenta
          </Button>
        </div>
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

      <ModalShell isOpen={isDeleteOpen} onClose={closeDeleteModal} title="Eliminar mi cuenta">
        <form onSubmit={handleDeleteSubmit} className="space-y-4" noValidate>
          <div className="bg-danger/10 border-danger/30 rounded-xl border p-3">
            <p className="text-danger text-xs leading-relaxed">
              Esta acción es <strong>irreversible</strong>: se van a eliminar tus cuentas,
              transacciones, presupuestos y categorías propias de forma permanente.
            </p>
          </div>
          {/* Fase 22 §22.4 (Decisión 22.4.2): una cuenta Google-only no tiene contraseña que
              confirmar — el backend saltea el chequeo (Hallazgo 6), pedirla solo confunde. */}
          {requiresPassword ? (
            <Input
              label="Contraseña"
              type="password"
              placeholder="Confirmá tu contraseña"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (passwordError) setPasswordError('');
              }}
              error={passwordError}
              autoFocus
              className="bg-background"
            />
          ) : (
            <p className="text-text-muted text-xs leading-relaxed">
              Tu cuenta usa Google para iniciar sesión — no hace falta contraseña para confirmar
              esta acción.
            </p>
          )}
          <div className="mt-6 flex gap-3">
            <Button type="button" variant="ghost" onClick={closeDeleteModal} className="flex-1">
              Cancelar
            </Button>
            <Button
              type="submit"
              variant="danger"
              loading={deleteAccount.isPending}
              disabled={requiresPassword && !password}
              className="flex-1"
            >
              Eliminar definitivamente
            </Button>
          </div>
        </form>
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
