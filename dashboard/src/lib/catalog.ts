import { z } from 'zod';
import { isStale, type ProviderStatus } from './data';

const sourceUrl = z.url().refine((s) => {
  const u = new URL(s);
  return u.protocol === 'https:' && !u.username && !u.password && ![...u.searchParams.keys()].some((key) =>
    !['pageToken', 'page_token', '$skiptoken'].includes(key) && /key|token|secret|signature|credential|authorization/i.test(key));
});
const object = z.record(z.string(), z.unknown());
const time = z.iso.datetime();
export const MAX_CATALOG_CHUNK_BYTES = 512 * 1024;
export const recordKinds = ['model', 'provider_route', 'model_flavor', 'document_row', 'document_page', 'meter', 'sku', 'sku_dimension'] as const;
export const accessKinds = ['Direct API', 'Gateway', 'Managed cloud', 'Platform'] as const;
export const billingBases = ['Tokens', 'Images', 'Audio / video', 'Requests', 'Compute', 'Storage / memory', 'Capacity', 'Credits / native units', 'Mixed', 'Other', 'Unknown'] as const;
export type BillingBasis = typeof billingBases[number];
const chunkPath = z.string().regex(/^catalog\/chunks\/[a-f0-9]{64}\.json$/);
export const chunkRefSchema = z.object({
  path: chunkPath, sha256: z.string().regex(/^[a-f0-9]{64}$/), count: z.number().int().positive(),
  bytes: z.number().int().positive().max(MAX_CATALOG_CHUNK_BYTES),
}).refine((r) => r.path === `catalog/chunks/${r.sha256}.json`, 'Chunk path and hash differ.');
export const nativeRateSchema = z.object({
  dimension: z.string(), amount: z.string().regex(/^\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/),
  currency: z.string().nullable(), unit: z.string().nullable(), conditions: object,
});
export const nativeRecordSchema = z.object({
  id: z.string(), provider: z.string(), native_id: z.string(), kind: z.enum(recordKinds), label: z.string(),
  scope: object, billing: object, rates: z.array(nativeRateSchema), metadata: object,
  comparison_eligible: z.literal(false), source_url: sourceUrl, reviewed_model_ids: z.array(z.string()),
  google_pricing_time_mode: z.literal('latest').optional(),
});
const counts = z.record(z.string(), z.number().int().nonnegative());
export const catalogProviderSchema = z.object({
  id: z.string().regex(/^[a-z0-9_-]+$/), name: z.string(), access: z.enum(accessKinds),
  record_count: z.number().int().nonnegative(), model_listing_count: z.number().int().nonnegative(), kind_counts: counts,
  source_url: sourceUrl, source_urls: z.array(sourceUrl), source_kind: z.string(),
  currencies: z.array(z.string()), revision: z.number().int().positive(), catalog_sha256: z.string(), source_sha256: z.string(),
  first_seen_at: time, last_seen_at: time, changed_at: time,
  detail_path: z.string().regex(/^catalog\/providers\/[a-z0-9_-]+\.json$/), history_path: z.string().regex(/^catalog\/history\/[a-z0-9_-]+\.json$/),
});
export const coverageSchema = z.object({
  reviewed_model_count: z.number().int().nonnegative(), reviewed_offering_count: z.number().int().nonnegative(),
  active_reviewed_offering_count: z.number().int().nonnegative(), reviewed_provider_count: z.number().int().nonnegative(),
  model_listing_count: z.number().int().nonnegative(), kind_counts: counts, billing_basis_counts: counts, pricing_state_counts: counts,
  single_provider_model_count: z.number().int().nonnegative(), gateway_only_model_count: z.number().int().nonnegative(),
  unknown_context_offering_count: z.number().int().nonnegative(), reviewed_price_change_count: z.number().int().nonnegative(),
});
export const catalogIndexSchema = z.object({
  schema_version: z.literal(2), updated_at: time, record_count: z.number().int().nonnegative(),
  providers: z.array(catalogProviderSchema), change_counts: counts, coverage: coverageSchema,
});
export const googlePricingObservationSchema = z.object({
  mode: z.literal('latest'), observed_at: time, source_sha256: z.string().regex(/^[a-f0-9]{64}$/),
  default_effective_time: time, record_count: z.number().int().positive(),
  older_than_documented_window_count: z.number().int().nonnegative().default(0),
  exceptions: z.record(z.string().regex(/^vertex-[a-f0-9]{24}$/), time),
});
export const listingSchema = nativeRecordSchema.pick({ id: true, provider: true, native_id: true, kind: true, label: true, reviewed_model_ids: true }).extend({
  scope_label: z.string(), pricing_state: z.string(), billing_basis: z.enum(billingBases), modalities: z.array(z.string()),
});
export const recordSummarySchema = listingSchema.extend({
  comparison_eligible: z.literal(false), currencies: z.array(z.string()), units: z.array(z.string()),
  rate_count: z.number().int().nonnegative(), rate_preview: z.array(nativeRateSchema.omit({ conditions: true })).max(2), detail_path: chunkPath,
});
export const providerCatalogSchema = z.object({
  schema_version: z.literal(2), provider: z.string(), catalog_sha256: z.string(), revision: z.number().int().positive(),
  billing_notes: z.array(z.string()), source_evidence: z.array(z.object({ source_url: sourceUrl, response_sha256: z.string() })),
  record_count: z.number().int().nonnegative(), index_chunks: z.array(chunkRefSchema), record_chunks: z.array(chunkRefSchema),
  pricing_observation: googlePricingObservationSchema.optional(),
}).refine((d) => d.index_chunks.reduce((n, r) => n + r.count, 0) === d.record_count &&
  d.record_chunks.reduce((n, r) => n + r.count, 0) === d.record_count, 'Incomplete provider manifest.');
export const recordChunkSchema = z.object({ schema_version: z.literal(1), records: z.array(nativeRecordSchema) });
export const recordIndexChunkSchema = z.object({ schema_version: z.literal(1), records: z.array(recordSummarySchema) });
export const modelListingsSchema = z.object({ schema_version: z.literal(1), listings: z.array(listingSchema) });
export const modelDirectorySchema = z.object({ schema_version: z.literal(2), listing_count: z.number().int().nonnegative(), chunks: z.array(chunkRefSchema) })
  .refine((d) => d.chunks.reduce((n, r) => n + r.count, 0) === d.listing_count, 'Incomplete model directory.');
const detailSchema = z.object({ field: z.string(), before: z.string().nullable(), after: z.string().nullable() });
export const nativeChangeSchema = z.object({
  id: z.string(), provider: z.string(), record_id: z.string().nullable(), observed_at: time, revision: z.number().int().positive(),
  category: z.enum(['price', 'rule', 'catalog']), title: z.string(), label: z.string(), source_url: sourceUrl,
  details: z.array(detailSchema),
});
export const nativeChangesSchema = z.object({ schema_version: z.literal(1), events: z.array(nativeChangeSchema) });
export const eventBatchSchema = z.object({
  id: z.string(), provider: z.string(), observed_at: time, category: z.enum(['price', 'rule', 'catalog']),
  event_count: z.number().int().positive(), chunks: z.array(chunkRefSchema),
}).refine((b) => b.chunks.reduce((n, r) => n + r.count, 0) === b.event_count, 'Incomplete event batch.');
export const historyManifestSchema = z.object({ schema_version: z.literal(2), event_count: z.number().int().nonnegative(), batches: z.array(eventBatchSchema) })
  .refine((d) => d.batches.reduce((n, b) => n + b.event_count, 0) === d.event_count, 'Incomplete history manifest.');
export type ChunkRef = z.infer<typeof chunkRefSchema>;
export type NativeRate = z.infer<typeof nativeRateSchema>;
export type NativeRecord = z.infer<typeof nativeRecordSchema>;
export type RecordSummary = z.infer<typeof recordSummarySchema>;
export type CatalogProvider = z.infer<typeof catalogProviderSchema>;
export type CatalogIndex = z.infer<typeof catalogIndexSchema>;
export type ProviderCatalog = z.infer<typeof providerCatalogSchema>;
export type ModelListing = z.infer<typeof listingSchema>;
export type NativeChange = z.infer<typeof nativeChangeSchema>;
export type EventBatch = z.infer<typeof eventBatchSchema>;
export type ChangeCategory = NativeChange['category'];

export function accessKind(provider: string): CatalogProvider['access'] {
  if (['openrouter', 'vercel', 'huggingface'].includes(provider)) return 'Gateway';
  if (['azure', 'vertex', 'bedrock', 'oracle'].includes(provider)) return 'Managed cloud';
  if (['snowflake', 'databricks', 'cloudflare', 'scaleway'].includes(provider)) return 'Platform';
  return 'Direct API';
}
export function jsonText(value: unknown): string {
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2) ?? 'Not published';
}
export function scopeLabel(record: Pick<NativeRecord, 'scope'>): string {
  return Object.entries(record.scope).filter(([key]) => !['table', 'headers', 'source_url', 'skuId', 'offer_id'].includes(key))
    .map(([key, value]) => `${key.replaceAll('_', ' ')}: ${Array.isArray(value) ? value.join(' › ') : jsonText(value)}`).join(' · ');
}
export function pricingState(record: Pick<NativeRecord, 'rates' | 'billing' | 'kind'>): string {
  if (record.billing.currency_state === 'unknown' || String(record.billing.state).includes('currency_unverified') || record.rates.some((r) => !r.currency)) return 'Currency unverified';
  if (record.kind === 'document_page') return 'Source evidence';
  if (record.rates.length) {
    if (record.billing.alignment_verified === false || record.rates.some((r) => r.conditions.active_rate_not_inferred)) return 'Rule-based';
    return record.rates.some((r) => !r.unit || r.conditions.unit_verified === false) ? 'Unit unverified' : 'Published native rate';
  }
  if (record.billing.cells || record.billing.text || record.billing.pricing_info || record.billing.rules && Object.keys(record.billing.rules as object).length) return 'Rule-based';
  return 'Price not published';
}
export function billingBasis(record: Pick<NativeRecord, 'rates' | 'billing' | 'scope'>): BillingBasis {
  const units = [...record.rates.map((r) => r.unit ?? ''), ...[record.billing.unit, record.billing.unitOfMeasure, record.billing.unit_of_measure].filter((v): v is string => typeof v === 'string')].join(' ').toLowerCase();
  const text = JSON.stringify([record.billing, record.scope.headers, record.scope.headings]).toLowerCase();
  const bases: BillingBasis[] = [];
  // Display facets only: these labels never convert units or authorize a quote.
  if (/\btpm\b|model\/month|ai unit per hour|custom model unit/.test(units)) bases.push('Capacity');
  else if (/\btoken/.test(units) || (!units.trim() || /^(?:1k|1m|1|100)$/i.test(units.trim())) && /\btoken/.test(text)) bases.push('Tokens');
  if (/\bimage/.test(units)) bases.push('Images');
  if (/\b(audio|video)\b|(?:input|output) second|frame unit|minutes processed/.test(units)) bases.push('Audio / video');
  if (/\b(request|call|query|queries|transaction|search|message|event|textunit)/.test(units)) bases.push('Requests');
  if (/\bgiby|\bgby|gigabyte|\bgb[ -]|\/ gb\b/.test(units)) bases.push('Storage / memory');
  if (!bases.includes('Capacity') && !bases.includes('Audio / video') && !bases.includes('Storage / memory') && /\bhour|\bsecond|\bnode|\bh\b|\bs\b/.test(units)) bases.push('Compute');
  if (/\b(dbu|credit|neuron)/.test(units + ' ' + text)) bases.push('Credits / native units');
  return bases.length > 1 ? 'Mixed' : bases[0] ?? (record.rates.length ? 'Other' : 'Unknown');
}
export function nativeRateText(rate: Pick<NativeRate, 'amount' | 'currency' | 'unit'>): string {
  return `${rate.currency ?? 'Currency unknown'} ${rate.amount} / ${rate.unit ?? 'unit unverified'}`;
}
export function sourceFreshness(status?: ProviderStatus): { label: string; warning: boolean } {
  if (!status) return { label: 'Check unavailable', warning: true };
  if (status.state === 'error') return { label: 'Failed · last good retained', warning: true };
  if (isStale(status.last_success_at)) return { label: 'Stale', warning: true };
  return { label: status.coverage_state === 'limited' ? 'Limited source' : 'Current', warning: status.coverage_state === 'limited' };
}
export function kindLabel(kind: string): string {
  return ({ model: 'Model listing', provider_route: 'Provider route', model_flavor: 'Model flavor', document_row: 'Document row', document_page: 'Document page', meter: 'Cloud meter', sku: 'SKU', sku_dimension: 'SKU dimension' } as Record<string, string>)[kind] ?? kind;
}
export function summarySearch(record: ModelListing & { units?: string[]; currencies?: string[] }): string {
  return [record.label, record.native_id, record.scope_label, record.pricing_state, record.billing_basis,
    ...record.modalities, ...(record.units ?? []), ...(record.currencies ?? [])].join(' ').toLowerCase();
}
export async function loadCatalogAsset<T>(path: string, schema: z.ZodType<T>, signal?: AbortSignal): Promise<T> {
  if (!/^catalog\/(?:index|models|changes\/(?:price|rule|catalog)|providers\/[a-z0-9_-]+|history\/[a-z0-9_-]+|historical\/[a-z0-9_-]+)\.json$/.test(path)) throw new Error('Invalid catalog asset path.');
  const response = await fetch(`${import.meta.env.BASE_URL}${path}`, { cache: 'no-store', signal: signal ?? AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error(`Unable to load catalog (HTTP ${response.status}). Please retry.`);
  return schema.parse(await response.json());
}
export async function loadCatalogChunk<T>(ref: ChunkRef, schema: z.ZodType<T>, signal?: AbortSignal): Promise<T> {
  chunkRefSchema.parse(ref);
  if (!globalThis.crypto?.subtle) throw new Error('Native chunk verification requires HTTPS or localhost. Unverified data was not loaded.');
  const response = await fetch(`${import.meta.env.BASE_URL}${ref.path}`, { signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error(`Unable to load catalog chunk (HTTP ${response.status}). Please retry.`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes.byteLength !== ref.bytes || bytes.byteLength > MAX_CATALOG_CHUNK_BYTES) throw new Error('Catalog chunk and manifest differ. Refresh the published dataset.');
  const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map((b) => b.toString(16).padStart(2, '0')).join('');
  if (hash !== ref.sha256) throw new Error('Catalog chunk and manifest differ. Refresh the published dataset.');
  return schema.parse(JSON.parse(new TextDecoder().decode(bytes)));
}
