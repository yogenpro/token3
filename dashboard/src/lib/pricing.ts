import type { Dataset, Offering, Price } from './data';

export type Workload = { inputTokens: number; outputTokens: number; cacheHitPercent: number; requests: number };
export const defaultWorkload: Workload = { inputTokens: 1200, outputTokens: 400, cacheHitPercent: 0, requests: 1_000_000 };
export function boundedNumber(value: number, max = 1_000_000_000) {
  return Number.isFinite(value) ? Math.max(0, Math.min(max, Math.floor(value))) : 0;
}
export function normalizeWorkload(workload: Workload): Workload {
  return {
    inputTokens: boundedNumber(workload.inputTokens), outputTokens: boundedNumber(workload.outputTokens),
    cacheHitPercent: boundedNumber(workload.cacheHitPercent, 100), requests: boundedNumber(workload.requests),
  };
}
export function estimateCost(offering: Offering, price: Price, raw: Workload) {
  const workload = normalizeWorkload(raw);
  const cached = workload.inputTokens * workload.cacheHitPercent / 100;
  const uncached = workload.inputTokens - cached;
  const fitsContext = offering.context_window === null || workload.inputTokens + workload.outputTokens <= offering.context_window;
  const fitsInputRange = workload.inputTokens >= (offering.min_input_tokens ?? 0) && (offering.max_input_tokens == null || workload.inputTokens <= offering.max_input_tokens);
  const fitsOutputLimit = offering.max_output_tokens == null || workload.outputTokens <= offering.max_output_tokens;
  const perRequest = (uncached * price.input_per_million + cached * (price.cache_read_per_million ?? price.input_per_million) + workload.outputTokens * price.output_per_million) / 1_000_000;
  return {
    perRequest, total: perRequest * workload.requests, perMillionRequests: perRequest * 1_000_000,
    fitsContext, fitsInputRange, fitsOutputLimit, eligible: fitsContext && fitsInputRange && fitsOutputLimit,
    contextUnverified: offering.context_window === null,
    cacheFallback: cached > 0 && price.cache_read_per_million === null,
  };
}
export type RankedOffering = { offering: Offering; price: Price; cost: ReturnType<typeof estimateCost> };
export function rankOfferings(dataset: Dataset, modelId: string, workload: Workload, tier = 'standard'): RankedOffering[] {
  const prices = new Map(dataset.prices.map((price) => [price.offering_id, price]));
  return dataset.offerings.filter((o) => o.active && o.model_id === modelId && (tier === 'all' || o.service_tier === tier))
    .flatMap((offering) => {
      const price = prices.get(offering.id);
      return price ? [{ offering, price, cost: estimateCost(offering, price, workload) }] : [];
    }).sort((a, b) => Number(b.cost.eligible) - Number(a.cost.eligible) || a.cost.perRequest - b.cost.perRequest || a.offering.id.localeCompare(b.offering.id));
}
export function isBestCost(row: RankedOffering, best: RankedOffering | undefined) {
  return !!best?.cost.eligible && row.cost.eligible && Math.abs(row.cost.perRequest - best.cost.perRequest) < 1e-12;
}
export function money(value: number, small = false) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: small || (value > 0 && value < 0.01) ? 8 : (value < 1 ? 4 : 2) }).format(value);
}
export function tokens(value: number | null) {
  return value === null ? '—' : new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}
export function dateLabel(value: string, time = false) {
  const date = new Date(value);
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', ...(time ? { hour: '2-digit', minute: '2-digit', hour12: false } : {}), timeZone: 'UTC' }).format(date) + (time ? ' UTC' : '');
}
export function exactDate(value: string) { return value.replace('T', ' ').replace('Z', ' UTC'); }
export function offeringLabel(offering: Offering) {
  return [offering.quantization?.toUpperCase() || 'Unspecified', offering.variant !== 'standard' ? offering.variant : null].filter(Boolean).join(' · ');
}

export function inputBandLabel(offering: Offering) {
  const min = offering.min_input_tokens ?? 0;
  const max = offering.max_input_tokens;
  if (min === 0 && max == null) return null;
  return min > 0 ? `Prompt >${tokens(min - 1)}${max != null ? `, ≤${tokens(max)}` : ''}` : `Prompt ≤${tokens(max ?? null)}`;
}
export function eligibilityReason(cost: ReturnType<typeof estimateCost>) {
  return !cost.fitsContext ? 'Exceeds context limit' : !cost.fitsOutputLimit ? 'Exceeds output limit' : !cost.fitsInputRange ? 'Outside prompt band' : '';
}

export function historyRows(history: Price[], offerings: Offering[], field: keyof Pick<Price, 'input_per_million' | 'output_per_million' | 'cache_read_per_million'>, days: number, now = Date.now()) {
  const ids = new Set(offerings.map((o) => o.id));
  const points = new Map<number, Record<string, number | null>>();
  for (const price of history) {
    const timestamp = new Date(price.observed_at).getTime();
    if (!ids.has(price.offering_id) || (days > 0 && timestamp < now - days * 86400000)) continue;
    const point = points.get(timestamp) ?? { timestamp };
    point[price.offering_id] = price[field];
    points.set(timestamp, point);
  }
  return [...points.values()].sort((a, b) => (a.timestamp ?? 0) - (b.timestamp ?? 0));
}

function csvCell(value: unknown) {
  let text = value == null ? '' : String(value);
  // Neutralize spreadsheet formula injection in text/IDs from public sources.
  if (/^[=+@-]/.test(text) && typeof value !== 'number') text = `'${text}`;
  return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}
export function comparisonCsv(rows: RankedOffering[], rawWorkload: Workload = defaultWorkload) {
  const w = normalizeWorkload(rawWorkload);
  const header = ['canonical_model', 'provider', 'provider_model_id', 'tier', 'region', 'quantization', 'variant', 'context_window', 'input_tokens', 'output_tokens', 'cache_hit_percent', 'requests', 'input_usd_per_million', 'output_usd_per_million', 'cache_read_usd_per_million', 'cache_write_usd_per_million', 'estimated_usd_per_request', 'estimated_usd_per_million_requests', 'estimated_workload_usd', 'fits_context', 'context_unverified', 'cache_fallback', 'min_input_tokens', 'max_input_tokens', 'max_output_tokens', 'fits_input_range', 'fits_output_limit', 'eligible', 'pricing_notes', 'observed_at', 'source_url'];
  const values = rows.map(({ offering: o, price: p, cost: c }) => [o.model_id, o.provider, o.provider_model_id, o.service_tier, o.region, o.quantization, o.variant, o.context_window, w.inputTokens, w.outputTokens, w.cacheHitPercent, w.requests, p.input_per_million, p.output_per_million, p.cache_read_per_million, p.cache_write_per_million, c.eligible ? c.perRequest : null, c.eligible ? c.perMillionRequests : null, c.eligible ? c.total : null, c.fitsContext, c.contextUnverified, c.cacheFallback, o.min_input_tokens ?? 0, o.max_input_tokens, o.max_output_tokens, c.fitsInputRange, c.fitsOutputLimit, c.eligible, o.pricing_notes, p.observed_at, p.source_url]);
  return [header, ...values].map((row) => row.map(csvCell).join(',')).join('\n') + '\n';
}
export function downloadFile(content: string, filename: string, type = 'text/csv;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
