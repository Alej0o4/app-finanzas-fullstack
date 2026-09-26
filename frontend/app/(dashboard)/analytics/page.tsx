'use client';

import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import type { CashflowItem, CategoryDistributionItem } from '@/types/api';
import { api } from '@/lib/api';
import { useCurrentUser } from '@/lib/hooks/useCurrentUser';
import { useAccounts } from '@/lib/hooks/useAccounts';
import { useState, useMemo, Suspense } from 'react';
import { useQueryParamState, useQueryParamsBatch } from '@/hooks/useQueryParamState';
import {
  type AnalyticsPeriod,
  buildDateRange,
  formatPeriodLabel,
  normalizeRef,
  shiftPeriodRef,
  utcDayKey,
} from '@/lib/dateRanges';
import CashflowChart, { type AnalyticsSeries } from '@/components/CashflowChart';
import CategoryDonutChart, {
  type CategoryType,
  type ReferenceMode,
} from '@/components/CategoryDonutChart';
import AnalyticsSummary from '@/components/AnalyticsSummary';
import Input from '@/components/ui/Input';
import Select from '@/components/ui/Select';
import SegmentedControl from '@/components/ui/SegmentedControl';
import PeriodNavigator from '@/components/PeriodNavigator';
import Skeleton from '@/components/ui/Skeleton';

const PERIOD_OPTIONS: { value: AnalyticsPeriod; label: string }[] = [
  { value: 'week', label: 'Esta semana' },
  { value: 'month', label: 'Este mes' },
  { value: 'year', label: 'Este año' },
  { value: 'custom', label: 'Personalizado' },
];

// Fase 13 §13.6: validadores read-time de los query params de analytics. Un link inválido
// (?period=abc) devolvía strings crudos que luego se casteaban a ciegas; ahora el hook devuelve
// el valor ya validado y tipado por estos validators, sin casts en la página. El tipo de retorno
// del validator es lo que el hook infiere como tipo del valor.
const validatePeriod = (raw: string): AnalyticsPeriod =>
  (['week', 'month', 'year', 'custom'] as const).includes(raw as AnalyticsPeriod)
    ? (raw as AnalyticsPeriod)
    : 'month';

// Mismo patrón que transactions/page.tsx: whitelist de formato para start/end (rango
// personalizado), sin reescribir la URL con el valor corregido.
const validateDateParam = (raw: string) => (/^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : '');

// Fase 29 §F6.1 (Q36): `?ref=YYYY-MM-DD` es el inicio **absoluto** del período, no un offset
// relativo, para que el enlace siga apuntando al mismo período mañana. Reusa el validador de
// fecha: el formato es el mismo y la normalización al inicio del período la hace
// `buildDateRange`/`normalizeRef` en lectura (la URL no se reescribe con el valor corregido, Fase
// 13 §13.6).
const validateRef = validateDateParam;

// Fase 29 §F6.2 (Q14): ISO 4217 en mayúsculas. Lo que no matchea cae a `''`, que equivale a la
// moneda preferida (ver `effectiveCurrency`), así que un link con `?currency=btl` no rompe la vista.
const validateCurrency = (raw: string) => (/^[A-Z]{3}$/.test(raw) ? raw : '');

const validateSeriesMode = (raw: string): AnalyticsSeries =>
  (['both', 'income', 'expense'] as const).includes(raw as AnalyticsSeries)
    ? (raw as AnalyticsSeries)
    : 'both';

const validateCategoryType = (raw: string): CategoryType =>
  (['expense', 'income'] as const).includes(raw as CategoryType)
    ? (raw as CategoryType)
    : 'expense';

// Fase 19 §19.3: whitelist del denominador de porcentaje del donut (mismo criterio de
// Fase 13 §13.6 que validateCategoryType). 'expense-total' = % de mis gastos (comportamiento
// original); 'income-total' = % de mi ingreso total del período (Decisión 19.3.1/19.3.4).
const validateReferenceMode = (raw: string): ReferenceMode =>
  (['expense-total', 'income-total'] as const).includes(raw as ReferenceMode)
    ? (raw as ReferenceMode)
    : 'expense-total';

const validateNeto = (raw: string): 'true' | 'false' => (raw === 'true' ? 'true' : 'false');

// 'all' o un id numérico de cuenta como string; cualquier otro valor cae a 'all'.
const validateAccountParam = (raw: string) => (raw === 'all' || /^\d+$/.test(raw) ? raw : 'all');

function AnalyticsPageContent() {
  // Decisión 11.1.1 (Fase 11): se pasa `currency` explícito a los endpoints de dashboard
  // aunque el backend ya defaultea a la moneda preferida — deja la intención explícita.
  const { data: user } = useCurrentUser();
  // Fase 12 §12.1, Decisión 12.1.2: la vista vive en la URL, no en localStorage — se
  // abandona usePersistedState (un link limpio vuelve a defaults; esa es la semántica
  // esperada de un link compartible). hiddenCategories sigue en useState (Decisión 12.1.3).
  // Fase 13 §13.6: cada valor sale validado del hook (whitelist tipada), sin casts locales.
  const [period] = useQueryParamState('period', 'month', validatePeriod);
  const [ref] = useQueryParamState('ref', '', validateRef);
  const [customStart] = useQueryParamState('start', '', validateDateParam);
  const [customEnd] = useQueryParamState('end', '', validateDateParam);
  const setPeriodParams = useQueryParamsBatch();
  // Segundo batch para cuenta + moneda: un solo `router.replace` para los dos params. Dos setters
  // de `useQueryParamState` seguidos en el mismo handler se pisan (ambos parten del mismo snapshot
  // de `searchParams` capturado por closure) — de ahí el hook.
  const setAccountParams = useQueryParamsBatch();
  const [currencyParam, setCurrencyParam] = useQueryParamState('currency', '', validateCurrency);
  const [seriesMode, setSeriesMode] = useQueryParamState('series', 'both', validateSeriesMode);
  const [categoryType, setCategoryType] = useQueryParamState(
    'type',
    'expense',
    validateCategoryType
  );
  const [netoRaw, setNetMode] = useQueryParamState('neto', 'false', validateNeto);
  const [referenceMode, setReferenceMode] = useQueryParamState(
    'reference',
    'expense-total',
    validateReferenceMode
  );
  const [hiddenCategories, setHiddenCategories] = useState<Set<string>>(new Set());
  // Fase de correcciones post-onboarding: antes analítica no tenía forma de elegir cuenta y
  // siempre agregaba todas — ahora es explícito y en la URL (link compartible, mismo criterio
  // de Decisión 12.1.2 que el resto de los filtros de esta página).
  const [accountFilter] = useQueryParamState('account', 'all', validateAccountParam);

  const netMode = netoRaw === 'true';
  const accountId = accountFilter !== 'all' ? Number(accountFilter) : undefined;

  const { data: accounts, isPending: accountsPending } = useAccounts();

  // `currency` y `account_id` son ortogonales en el backend (Fase 17 §17.1.3) — al
  // filtrar por una cuenta hay que pasar SU moneda explícita, si no la vista se queda
  // pidiendo la moneda preferida del usuario y una cuenta en otra moneda siempre da $0.
  const selectedAccount = accounts?.find((account) => account.id === accountId);
  const preferredCurrency = user?.preferred_currency;

  // Fase 29 §F6.2 (Q14, User Story 42): las monedas en las que el usuario tiene cuentas, más la
  // preferida — sin sumar la preferida, alguien que solo tiene cuentas USD (con preferencia COP)
  // no podría elegir la moneda que sí puede consultar. Va primera para que el chip arranque donde
  // siempre (User Story 23); el resto en orden alfabético para que las opciones no bailen.
  const currencyOptions = useMemo(() => {
    const codes = new Set(accounts?.map((account) => account.currency));
    if (preferredCurrency) codes.add(preferredCurrency);
    return [...codes].sort((a, b) => {
      if (a === preferredCurrency) return -1;
      if (b === preferredCurrency) return 1;
      return a.localeCompare(b);
    });
  }, [accounts, preferredCurrency]);

  // Con una cuenta elegida manda la moneda de esa cuenta y los chips desaparecen (User Story 43).
  // Un `?currency=` que no está entre las opciones —moneda ajena, o de una cuenta que ya no
  // existe— cae a la preferida en vez de pedir una vista vacía.
  const effectiveCurrency =
    selectedAccount?.currency ??
    (currencyOptions.includes(currencyParam) ? currencyParam : preferredCurrency);

  // Fase 29 §F6.2: con `?currency=` en la URL y `/accounts/` todavía en vuelo, `currencyOptions`
  // solo conoce la preferida, así que la moneda efectiva sería un chute — las queries dispararían
  // un fetch en una moneda que no es la elegida y después habría que corregirlo con un segundo
  // fetch. Lo mismo con `?account=<id>`: sin `/accounts/` no se conoce la moneda de la cuenta,
  // `selectedAccount` es `undefined` y la moneda efectiva cae a la preferida (un fetch en $0 COP
  // para una cuenta USD, y luego el correcto). En los dos casos se espera a que las cuentas
  // resuelvan (o fallen: si fallan, se sigue con la preferida en vez de dejar la vista colgada).
  //
  // El primer término conserva el `enabled` que ya estaba: esperar a que `effectiveCurrency`
  // estuviera resuelto (depende de /users/me y /accounts/, que llegan en paralelo) era el fix
  // del bug de la vista en $0 al seleccionar una cuenta USD.
  const waitingForAccounts = (!!currencyParam || accountFilter !== 'all') && accountsPending;
  const queriesEnabled = !!effectiveCurrency && !waitingForAccounts;

  // Un solo reloj para toda la vista: `buildDateRange` y `formatPeriodLabel` lo reciben
  // inyectado (módulo puro, testeable) y, además, el `end_date` del período en curso va dentro de
  // las query keys — si `now` cambiara en cada render, la key cambiaría también y TanStack
  // vería una query nueva por render (refetch en loop).
  //
  // Por eso `now` es el inicio del día UTC y no el instante: se recalcula en cada render pero
  // solo cambia de identidad cuando cambia el día (memo sobre `utcDayKey`). El período en curso
  // termina al FIN de ese día (`endOfUtcDay`, dentro de `buildDateRange`), así que una
  // transacción capturada por el FAB después de montar —el backend la guarda con `now()` real—
  // entra en el refetch que dispara su invalidación. Antes `now` quedaba congelado al montar y
  // el techo del período nunca avanzaba.
  const todayKey = utcDayKey(new Date());
  const now = useMemo(() => new Date(`${todayKey}T00:00:00Z`), [todayKey]);

  // Un solo rango de fechas para las 3 secciones (KPIs, barras, dona) — ver `buildDateRange`.
  const dateRange = useMemo(
    () => buildDateRange(period, ref, customStart, customEnd, now),
    [period, ref, customStart, customEnd, now]
  );

  // El rango personalizado no tiene período de calendario que navegar (User Story 39).
  const navigablePeriod = period === 'custom' ? null : period;
  const activeRef = navigablePeriod ? normalizeRef(navigablePeriod, ref, now) : '';
  const isCurrentPeriod = !!navigablePeriod && activeRef === normalizeRef(navigablePeriod, '', now);
  const periodLabel = useMemo(
    () => formatPeriodLabel(period, ref, customStart, customEnd, now),
    [period, ref, customStart, customEnd, now]
  );

  const handlePeriodChange = (next: string) => {
    // `SegmentedControl` es genérico y devuelve `string`; el valor solo puede salir de
    // `PERIOD_OPTIONS`, que es lo que hace segura la conversión.
    const nextPeriod = next as AnalyticsPeriod;
    // `ref: null` en las dos ramas: cambiar de preset vuelve al período actual (User Story 38), y
    // un `ref` de otro período no debería sobrevivir en un link a un preset que no lo usa.
    setPeriodParams(
      nextPeriod === 'custom'
        ? { period: 'custom', ref: null }
        : { period: nextPeriod === 'month' ? null : nextPeriod, start: null, end: null, ref: null }
    );
  };

  const handleShiftPeriod = (delta: -1 | 1) => {
    if (!navigablePeriod) return;
    const nextRef = shiftPeriodRef(navigablePeriod, activeRef, delta, now);
    // El período actual va sin `ref` (default nunca escrito en la URL, Fase 13 §13.6): si `▶`
    // aterriza en él se borra el param, igual que "Volver al período actual". Escribirlo dejaría
    // el link fijado a este período después de que termine.
    const landsOnCurrent = nextRef === normalizeRef(navigablePeriod, '', now);
    setPeriodParams({ ref: landsOnCurrent ? null : nextRef });
  };

  const handleAccountChange = (next: string) => {
    // La moneda se limpia en el mismo batch: con una cuenta elegida la moneda es la suya (Fase
    // 17 §17.1.3), así que un `?currency=` anterior describiría un período que ya no se está
    // mirando. Se borra también al volver a "Todas las cuentas", donde el param vuelve a ser
    // opcional.
    // "Todas las cuentas" es el default: se borra el param en vez de escribir `?account=all`.
    setAccountParams({ account: next === 'all' ? null : next, currency: null });
  };

  const handleCurrencyChange = (next: string) => {
    // Elegir la preferida borra el param en vez de escribirlo: equivale a "sin `currency`" (el
    // default nunca se escribe en la URL, Fase 13 §13.6) y deja el link del caso por defecto
    // limpio.
    setCurrencyParam(next === preferredCurrency ? '' : next);
  };

  const {
    data: trendData,
    isLoading: loadingTrends,
    isError: trendError,
  } = useQuery({
    queryKey: queryKeys.analytics.cashflow(
      dateRange.start_date,
      dateRange.end_date,
      dateRange.granularity,
      accountFilter,
      effectiveCurrency
    ),
    enabled: queriesEnabled,
    queryFn: async () => {
      const res = await api.get('dashboard/cashflow-series', {
        params: {
          start_date: dateRange.start_date,
          end_date: dateRange.end_date,
          period: dateRange.granularity,
          currency: effectiveCurrency,
          account_id: accountId,
        },
      });
      return res.data;
    },
  });

  const {
    data: categoryData,
    isLoading: loadingCategories,
    isFetching: fetchingCategories,
    isError: categoryError,
  } = useQuery({
    queryKey: queryKeys.analytics.categories(
      dateRange.start_date,
      dateRange.end_date,
      categoryType,
      netMode,
      accountFilter,
      effectiveCurrency
    ),
    enabled: queriesEnabled,
    queryFn: async () => {
      const res = await api.get('dashboard/category-distribution', {
        params: {
          start_date: dateRange.start_date,
          end_date: dateRange.end_date,
          type: netMode ? 'expense' : categoryType,
          neto: netMode || undefined,
          currency: effectiveCurrency,
          account_id: accountId,
        },
      });
      return res.data;
    },
  });

  const parsedTrendData = useMemo(() => {
    return (
      (trendData as CashflowItem[])?.map((item) => ({
        ...item,
        expense: Number(item.expense),
        income: Number(item.income),
      })) || []
    );
  }, [trendData]);

  const visibleTrendData = useMemo(() => {
    return parsedTrendData.map((item) => ({
      ...item,
      income: seriesMode === 'expense' ? 0 : item.income,
      expense: seriesMode === 'income' ? 0 : item.expense,
    }));
  }, [parsedTrendData, seriesMode]);

  const totals = useMemo(() => {
    const totalIncome = parsedTrendData.reduce((sum, item) => sum + item.income, 0);
    const totalExpense = parsedTrendData.reduce((sum, item) => sum + item.expense, 0);
    return { totalIncome, totalExpense };
  }, [parsedTrendData]);

  // Mientras la moneda del URL (o la de la cuenta elegida) no se puede resolver contra las
  // cuentas, las queries están apagadas
  // (`queriesEnabled`) y `isLoading` es false: sin este cierre la página pintaría un frame con los
  // totales en 0 y los gráficos vacíos antes de llegar a los datos correctos.
  if ((loadingTrends && loadingCategories) || waitingForAccounts) {
    return (
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Skeleton className="h-96 rounded-2xl" />
        <Skeleton className="h-96 rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="animate-in fade-in space-y-8 duration-500">
      <div>
        <h1 className="text-text text-2xl font-semibold">Analítica Financiera</h1>
        <p className="text-text-muted mt-1 text-sm">
          Visualiza el flujo de tu dinero y la distribución de tus finanzas.
        </p>
      </div>

      {/* Selector de período único: controla la tarjeta de KPIs, el gráfico de barras y la
          dona a la vez — antes cada gráfico tenía su propio selector y solo uno de ellos
          afectaba los números de arriba, lo cual generaba confusión. */}
      <div className="flex flex-wrap items-center gap-3">
        <SegmentedControl
          options={PERIOD_OPTIONS}
          value={period}
          onChange={handlePeriodChange}
          ariaLabel="Período"
        />

        {/* Fase 29 §F6.1 (User Stories 33-40): `◀ ▶` sobre el preset elegido — semana, mes o año.
            `▶` se corta en el período actual (User Story 35) y "Volver al período actual" solo
            aparece fuera de él. No lleva cota inferior como el del dashboard: estos endpoints no
            devuelven `first_transaction_month` (a diferencia de `/dashboard/summary`, B2), así que
            un período sin datos se ve vacío en vez de bloquear la flecha. */}
        {navigablePeriod && (
          <PeriodNavigator
            label={periodLabel}
            onPrev={() => handleShiftPeriod(-1)}
            onNext={() => handleShiftPeriod(1)}
            prevDisabled={false}
            nextDisabled={isCurrentPeriod}
            prevLabel="Período anterior"
            nextLabel="Período siguiente"
            onReset={isCurrentPeriod ? undefined : () => setPeriodParams({ ref: null })}
            resetLabel="Volver al período actual"
          />
        )}

        {period === 'custom' && (
          <div className="flex flex-wrap items-center gap-2">
            <Input
              type="date"
              value={customStart}
              onChange={(event) =>
                setPeriodParams({ period: 'custom', start: event.target.value || null })
              }
              className="bg-background"
              aria-label="Fecha inicial"
            />
            <span className="text-text-muted text-sm">a</span>
            <Input
              type="date"
              value={customEnd}
              onChange={(event) =>
                setPeriodParams({ period: 'custom', end: event.target.value || null })
              }
              className="bg-background"
              aria-label="Fecha final"
            />
          </div>
        )}

        <Select
          value={accountFilter}
          onChange={(event) => handleAccountChange(event.target.value)}
          className="bg-background"
          aria-label="Cuenta"
        >
          <option value="all">Todas las cuentas</option>
          {accounts?.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name} ({account.currency})
            </option>
          ))}
        </Select>

        {/* Fase 29 §F6.2 (User Stories 41-43): chips de moneda solo con "Todas las cuentas" y
            ocultos si hay una sola opción — mismo criterio que los chips de "Gastos por categoría"
            del dashboard. Con una cuenta concreta la moneda es la suya y no hay nada que elegir.
            El aviso de "cuentas en otra moneda no incluidas" que vivía acá desapareció: las cuentas
            en otra moneda se ven eligiendo su moneda (User Story 45). */}
        {accountFilter === 'all' && currencyOptions.length > 1 && (
          <SegmentedControl
            options={currencyOptions.map((code) => ({ value: code, label: code }))}
            value={effectiveCurrency ?? ''}
            onChange={handleCurrencyChange}
            ariaLabel="Moneda"
          />
        )}
      </div>

      <AnalyticsSummary
        totalIncome={totals.totalIncome}
        totalExpense={totals.totalExpense}
        currency={effectiveCurrency}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <CashflowChart
          data={visibleTrendData}
          isLoading={loadingTrends}
          isError={trendError}
          seriesMode={seriesMode}
          onSeriesModeChange={setSeriesMode}
          periodType={dateRange.granularity}
          currency={effectiveCurrency}
        />

        <CategoryDonutChart
          data={categoryData as CategoryDistributionItem[]}
          isFetching={fetchingCategories}
          isError={categoryError}
          categoryType={categoryType}
          onCategoryTypeChange={setCategoryType}
          netMode={netMode}
          onNetModeChange={(net) => setNetMode(String(net))}
          hiddenCategories={hiddenCategories}
          onHiddenCategoriesChange={setHiddenCategories}
          referenceMode={referenceMode}
          onReferenceModeChange={setReferenceMode}
          totalIncomeForPeriod={totals.totalIncome}
          currency={effectiveCurrency}
        />
      </div>
    </div>
  );
}

// Fase 12 §12.1: useSearchParams requiere Suspense (mismo patrón que login/reset-password).
export default function AnalyticsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 rounded-2xl" />}>
      <AnalyticsPageContent />
    </Suspense>
  );
}
