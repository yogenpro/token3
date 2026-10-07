import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  accessKind, billingBasis, catalogIndexSchema, jsonText, modelListingsSchema, nativeChangesSchema,
  nativeRecordSchema, pricingState, providerCatalogSchema, scopeLabel,
  type CatalogProvider, type NativeChange, type NativeRecord,
} from '../dashboard/src/lib/catalog';

type ObjectValue = Record<string, any>;
const same = (a: unknown, b: unknown): boolean => stable(a) === stable(b);
function stable(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stable).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => `${JSON.stringify(k)}:${stable(v)}`).join(',')}}`;
  return JSON.stringify(value) ?? 'null';
}
const metadataKeys = new Set(['source_model_id', 'type', 'max_tokens', 'quantization', 'input_modalities', 'output_modalities', 'context_length', 'kind', 'pricing_mode', 'service_tier', 'model_type', 'context_size', 'max_output_tokens', 'status', 'name', 'canonical_slug', 'hugging_face_id', 'architecture', 'top_provider', 'expiration_date', 'knowledge_cutoff', 'available', 'category', 'owned_by', 'context_window', 'modalities', 'model_type', 'model_name', 'max_model_len', 'context_window_k', 'external_provider', 'vendor', 'size_b', 'meterName', 'skuName', 'productName', 'armSkuName', 'location', 'serviceName', 'serviceFamily', 'sku', 'attributes', 'productFamily', 'displayName', 'serviceCategory', 'product', 'variant', 'description', 'service_category', 'product_category', 'table_alignment_verified']);
const scopeKeys = new Set(['table', 'headings', 'tabs', 'headers', 'source_url', 'skuId', 'armRegionName', 'type', 'tierMinimumUnits', 'effectiveStartDate', 'feed', 'term_type', 'offer_id', 'begin_range', 'end_range', 'effective_date', 'serving_mode', 'upstream_provider', 'flavor', 'region', 'price_model', 'locality', 'page', 'service', 'regions']);
const billingKeys = new Set(['cells', 'columns', 'alignment_verified', 'interpretation', 'retailPrice', 'unitPrice', 'unitOfMeasure', 'currencyCode', 'reservationTerm', 'unit', 'prices', 'applies_to', 'term_attributes', 'description', 'state', 'rules', 'currency', 'unknown_price_dimensions', 'source_scope', 'native_rates', 'currency_state', 'unit_of_measure', 'text', 'pricing_info', 'geo_taxonomy']);
const pick = (value: ObjectValue = {}, keys: Set<string>): ObjectValue => Object.fromEntries(Object.entries(value).filter(([key]) => keys.has(key)));
function checkedUrl(value: string): string {
  const url = new URL(value);
  if (url.protocol !== 'https:' || url.username || url.password || [...url.searchParams.keys()].some((key) => !['pageToken', 'page_token', '$skiptoken'].includes(key) && /key|token|secret|signature|credential|authorization/i.test(key))) throw new Error('Unsafe dashboard source URL');
  return url.href;
}
export function projectRecord(raw: ObjectValue, sourceUrl: string, offerings: ObjectValue[] = []): NativeRecord {
  const ids = new Set([raw.native_id, raw.metadata?.source_model_id].filter(Boolean));
  const models = offerings.filter((o) => o.provider === raw.provider && ids.has(o.provider_model_id)).map((o) => o.model_id);
  const scope = pick(raw.scope, scopeKeys);
  if (scope.source_url) scope.source_url = checkedUrl(scope.source_url);
  return nativeRecordSchema.parse({
    id: raw.id, provider: raw.provider, native_id: raw.native_id, kind: raw.kind, label: raw.label,
    scope, billing: pick(raw.billing, billingKeys), rates: raw.rates ?? [], metadata: pick(raw.metadata, metadataKeys),
    comparison_eligible: false, source_url: checkedUrl(raw.scope?.source_url ?? sourceUrl), reviewed_model_ids: [...new Set(models)].sort(),
  });
}
export function classifyRecordChange(before: NativeRecord, after: NativeRecord): Array<Pick<NativeChange, 'category' | 'title' | 'details'>> {
  const changes: Array<Pick<NativeChange, 'category' | 'title' | 'details'>> = [];
  // Only equal, explicit billing bases can describe a native amount change. Source-cell
  // extractions, changed currencies/units/conditions, and changed scopes are rule changes.
  const rateKey = (r: NativeRecord['rates'][number]) => stable([r.dimension, r.currency, r.unit, r.conditions]);
  const usable = (r: NativeRecord['rates'][number]) => r.currency && r.unit && r.conditions.unit_verified !== false && !r.conditions.active_rate_not_inferred;
  const oldRates = new Map(before.rates.map((r) => [rateKey(r), r]));
  const stableBasis = same(before.scope, after.scope) && before.rates.length === after.rates.length &&
    before.rates.length > 0 && oldRates.size === before.rates.length && after.rates.every((r) => oldRates.has(rateKey(r)) && usable(r));
  const amounts = stableBasis ? after.rates.filter((r) => oldRates.get(rateKey(r))!.amount !== r.amount).map((r) => ({
    field: r.dimension, before: `${r.currency} ${oldRates.get(rateKey(r))!.amount} / ${r.unit}`, after: `${r.currency} ${r.amount} / ${r.unit}`,
  })) : [];
  if (amounts.length) changes.push({ category: 'price', title: 'Published native amount changed', details: amounts });
  const withoutAmounts = (r: NativeRecord) => {
    const b = structuredClone(r.billing);
    // Flat API price fields merely mirror rates. Do not duplicate them as rule changes.
    if (b.rules && !Array.isArray(b.rules) && typeof b.rules === 'object') for (const rate of r.rates) delete (b.rules as ObjectValue)[rate.dimension];
    for (const rate of r.rates) delete b[rate.dimension];
    return b;
  };
  if (!same(before.rates, after.rates) && !amounts.length || !same(amounts.length ? withoutAmounts(before) : before.billing, amounts.length ? withoutAmounts(after) : after.billing) || !same(before.scope, after.scope)) {
    changes.push({ category: 'rule', title: 'Billing rules or price basis changed', details: [{ field: 'Billing basis', before: `${pricingState(before)} · ${billingBasis(before)}`, after: `${pricingState(after)} · ${billingBasis(after)}` }] });
  }
  if (!same(before.metadata, after.metadata) || before.label !== after.label) changes.push({ category: 'catalog', title: 'Listing metadata changed', details: [{ field: 'Listing', before: before.label, after: after.label }] });
  if (!changes.length) changes.push({ category: 'catalog', title: 'Source record changed', details: [] });
  return changes;
}

export function buildDashboardAssets(dataDir: string): Map<string, string> {
  const read = (file: string) => JSON.parse(readFileSync(join(dataDir, file), 'utf8')) as any;
  const inventory = read('provider_inventory.json');
  const offerings = read('offerings.json');
  const assets = new Map<string, string>();
  const put = (path: string, value: unknown) => assets.set(path, JSON.stringify(value));
  const providers: CatalogProvider[] = [];
  const recordSources = new Map<string, string>();
  const listings: any[] = [];
  for (const p of inventory.providers) {
    if (!/^[a-z0-9_-]+$/.test(p.id) || p.latest_path !== `provider_catalogs/${p.id}.json`) throw new Error('Unsafe provider catalog path');
    const c = read(p.latest_path);
    if (c.provider !== p.id || c.records.length !== p.record_count || c.catalog_sha256 !== p.catalog_sha256) throw new Error(`Inconsistent provider catalog: ${p.id}`);
    const records = c.records.map((r: ObjectValue) => projectRecord(r, p.source_url, offerings));
    if (new Set(records.map((r: NativeRecord) => r.id)).size !== records.length) throw new Error('Duplicate native records');
    const kindCounts: Record<string, number> = {};
    for (const r of records) {
      kindCounts[r.kind] = (kindCounts[r.kind] ?? 0) + 1;
      recordSources.set(r.id, r.source_url);
      // Named API entries are listings, not inferred canonical models. Document labels
      // and cloud SKUs cannot safely stand in for model identities.
      if (['model', 'provider_route', 'model_flavor'].includes(r.kind)) {
        const m = r.metadata;
        listings.push({ id: r.id, provider: r.provider, native_id: r.native_id, kind: r.kind, label: r.label,
          reviewed_model_ids: r.reviewed_model_ids, scope_label: scopeLabel(r), pricing_state: pricingState(r), billing_basis: billingBasis(r),
          modalities: [...new Set([...(m.input_modalities as string[] ?? []), ...((m.architecture as any)?.input_modalities ?? []), ...(m.output_modalities as string[] ?? []), ...((m.architecture as any)?.output_modalities ?? [])])],
        });
      }
    }
    providers.push({
      id: p.id, name: p.name, access: accessKind(p.id), record_count: records.length,
      model_listing_count: records.filter((r: NativeRecord) => ['model', 'provider_route', 'model_flavor'].includes(r.kind)).length, kind_counts: kindCounts,
      source_url: checkedUrl(p.source_url), source_urls: [...new Set((c.source_urls ?? [p.source_url]).map(checkedUrl))] as string[],
      source_kind: p.source_kind, currencies: [...new Set(records.flatMap((r: NativeRecord) => r.rates.map((rate) => rate.currency).filter(Boolean)))] as string[],
      revision: c.revision, catalog_sha256: c.catalog_sha256, source_sha256: p.source_sha256,
      first_seen_at: p.first_seen_at, last_seen_at: p.last_seen_at, changed_at: c.changed_at,
      detail_path: `catalog/providers/${p.id}.json`, history_path: `catalog/history/${p.id}.json`,
    });
    put(`catalog/providers/${p.id}.json`, providerCatalogSchema.parse({ schema_version: 1, provider: p.id, catalog_sha256: c.catalog_sha256, revision: c.revision,
      billing_notes: c.billing_notes ?? [], source_evidence: (c.source_evidence ?? []).map((e: any) => ({ source_url: checkedUrl(e.source_url), response_sha256: e.response_sha256 })), records }));
  }
  const providerMap = new Map(providers.map((p) => [p.id, p]));
  const previous = new Map<string, NativeRecord>();
  const everSeen = new Set<string>();
  const notesSeen = new Set<string>();
  const events: NativeChange[] = [];
  const eventIds = new Set<string>();
  // Replay append-only history in its recorded order, never fabricate earlier states.
  for (const line of readFileSync(join(dataDir, 'inventory_history.jsonl'), 'utf8').split('\n')) {
    if (!line.trim()) continue;
    const e = JSON.parse(line);
    const p = providerMap.get(e.provider);
    if (!p) throw new Error('History references an unknown provider');
    if (eventIds.has(e.id)) throw new Error('Duplicate inventory history event');
    eventIds.add(e.id);
    const before = previous.get(e.record_id);
    const after = e.after ? projectRecord(e.after, p.source_url, offerings) : null;
    const fields: Array<Pick<NativeChange, 'category' | 'title' | 'details'>> = [];
    if (e.kind === 'billing_notes_changed') {
      fields.push({ category: 'rule', title: notesSeen.has(e.provider) ? 'Billing guide changed' : 'Billing guide first observed', details: [] }); notesSeen.add(e.provider);
    } else if (e.kind === 'record_added') fields.push({ category: 'catalog', title: everSeen.has(e.record_id) ? 'Source listing reappeared' : 'First observed listing', details: [] });
    else if (e.kind === 'record_no_longer_listed') fields.push({ category: 'catalog', title: 'No longer in selected source', details: [] });
    else if (e.kind === 'record_changed' && before && after) fields.push(...classifyRecordChange(before, after));
    else fields.push({ category: 'catalog', title: 'Source record changed', details: [] });
    const r = after ?? before;
    for (const field of fields) events.push({ ...field, id: `native-${e.id}-${field.category}`, provider: e.provider,
      record_id: e.record_id ?? null, observed_at: e.observed_at, revision: e.revision,
      label: r?.label ?? (e.kind === 'billing_notes_changed' ? 'Provider billing guide' : e.record_id),
      source_url: r?.source_url ?? recordSources.get(e.record_id) ?? p.source_url,
    });
    if (after) { previous.set(e.record_id, after); everSeen.add(e.record_id); }
    else if (e.kind === 'record_no_longer_listed') previous.delete(e.record_id);
  }
  events.sort((a, b) => b.observed_at.localeCompare(a.observed_at) || a.id.localeCompare(b.id));
  const changeCounts: Record<string, number> = {};
  for (const category of ['price', 'rule', 'catalog'] as const) {
    const selected = events.filter((e) => e.category === category); changeCounts[category] = selected.length;
    put(`catalog/changes/${category}.json`, nativeChangesSchema.parse({ schema_version: 1, events: selected }));
  }
  for (const p of providers) put(p.history_path, nativeChangesSchema.parse({ schema_version: 1, events: events.filter((e) => e.provider === p.id) }));
  put('catalog/index.json', catalogIndexSchema.parse({ schema_version: 1, updated_at: inventory.updated_at,
    record_count: providers.reduce((sum, p) => sum + p.record_count, 0), providers, change_counts: changeCounts }));
  put('catalog/models.json', modelListingsSchema.parse({ schema_version: 1, listings: listings.sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id)) }));
  return assets;
}
