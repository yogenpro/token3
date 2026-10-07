import { z } from 'zod';
import { isStale, type ProviderStatus } from './data';

const sourceUrl = z.url().refine((s) => { const u = new URL(s); return u.protocol === 'https:' && !u.username && !u.password; });
const object = z.record(z.string(), z.unknown());
const time = z.iso.datetime();
export const recordKinds = ['model', 'provider_route', 'model_flavor', 'document_row', 'document_page', 'meter', 'sku', 'sku_dimension'] as const;
export const accessKinds = ['Direct API', 'Gateway', 'Managed cloud', 'Platform'] as const;
export const billingBases = ['Tokens', 'Compute', 'Credits / native units', 'Mixed', 'Other', 'Unknown'] as const;
export type BillingBasis = typeof billingBases[number];
export const nativeRateSchema = z.object({
  dimension: z.string(), amount: z.string().regex(/^\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/),
  currency: z.string().nullable(), unit: z.string().nullable(), conditions: object,
});
export const nativeRecordSchema = z.object({
  id: z.string(), provider: z.string(), native_id: z.string(), kind: z.enum(recordKinds), label: z.string(),
  scope: object, billing: object, rates: z.array(nativeRateSchema), metadata: object,
  comparison_eligible: z.literal(false), source_url: sourceUrl, reviewed_model_ids: z.array(z.string()),
});
const counts = z.record(z.string(), z.number().int().nonnegative());
export const catalogProviderSchema = z.object({
  id: z.string().regex(/^[a-z0-9_-]+$/), name: z.string(), access: z.enum(accessKinds),
  record_count: z.number().int().nonnegative(), model_listing_count: z.number().int().nonnegative(), kind_counts: counts,
  source_url: sourceUrl, source_urls: z.array(sourceUrl), source_kind: z.string(),
  currencies: z.array(z.string()), revision: z.number().int().positive(), catalog_sha256: z.string(), source_sha256: z.string(),
  first_seen_at: time, last_seen_at: time, changed_at: time,
  detail_path: z.string(), history_path: z.string(),
});
export const catalogIndexSchema = z.object({
  schema_version: z.literal(1), updated_at: time, record_count: z.number().int().nonnegative(),
  providers: z.array(catalogProviderSchema), change_counts: counts,
});
export const providerCatalogSchema = z.object({
  schema_version: z.literal(1), provider: z.string(), catalog_sha256: z.string(), revision: z.number().int().positive(),
  billing_notes: z.array(z.string()), source_evidence: z.array(z.object({ source_url: sourceUrl, response_sha256: z.string() })),
  records: z.array(nativeRecordSchema),
});
export const listingSchema = nativeRecordSchema.pick({ id: true, provider: true, native_id: true, kind: true, label: true, reviewed_model_ids: true }).extend({
  scope_label: z.string(), pricing_state: z.string(), billing_basis: z.enum(billingBases), modalities: z.array(z.string()),
});
export const modelListingsSchema = z.object({ schema_version: z.literal(1), listings: z.array(listingSchema) });
const detailSchema = z.object({ field: z.string(), before: z.string().nullable(), after: z.string().nullable() });
export const nativeChangeSchema = z.object({
  id: z.string(), provider: z.string(), record_id: z.string().nullable(), observed_at: time, revision: z.number().int().positive(),
  category: z.enum(['price', 'rule', 'catalog']), title: z.string(), label: z.string(), source_url: sourceUrl,
  details: z.array(detailSchema),
});
export const nativeChangesSchema = z.object({ schema_version: z.literal(1), events: z.array(nativeChangeSchema) });
export type NativeRate = z.infer<typeof nativeRateSchema>;
export type NativeRecord = z.infer<typeof nativeRecordSchema>;
export type CatalogProvider = z.infer<typeof catalogProviderSchema>;
export type CatalogIndex = z.infer<typeof catalogIndexSchema>;
export type ProviderCatalog = z.infer<typeof providerCatalogSchema>;
export type ModelListing = z.infer<typeof listingSchema>;
export type NativeChange = z.infer<typeof nativeChangeSchema>;
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
  const text = JSON.stringify([record.rates.map((r) => r.unit), record.billing, record.scope.headers, record.scope.headings]).toLowerCase();
  const bases: BillingBasis[] = [];
  if (/\btoken|\btpm\b/.test(text)) bases.push('Tokens');
  if (/\bdbu|\bcredit|\bneuron/.test(text)) bases.push('Credits / native units');
  if (/\bhour|\bsecond|\bgiby|\bnode.hour|"h"|"s"/.test(text)) bases.push('Compute');
  return bases.length > 1 ? 'Mixed' : bases[0] ?? (record.rates.length ? 'Other' : 'Unknown');
}
export function nativeRateText(rate: NativeRate): string {
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
export async function loadCatalogAsset<T>(path: string, schema: z.ZodType<T>, signal?: AbortSignal): Promise<T> {
  if (!/^catalog\/(?:index|models|changes\/(?:price|rule|catalog)|providers\/[a-z0-9_-]+|history\/[a-z0-9_-]+)\.json$/.test(path)) throw new Error('Invalid catalog asset path.');
  const response = await fetch(`${import.meta.env.BASE_URL}${path}`, { cache: 'no-store', signal: signal ?? AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error(`Unable to load catalog (HTTP ${response.status}). Please retry.`);
  return schema.parse(await response.json());
}
