import { existsSync, readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { historicalCaptureSchema, historicalEvidenceSchema, historicalCheckSchema, historicalIndexSchema, historicalIndexChunkSchema, historicalEvidenceChunkSchema, historicalManifestSchema, historicalCheckChunkSchema } from '../dashboard/src/lib/historical';
import { readNativeHistory } from './native_history';
import {
  accessKind, billingBasis, catalogIndexSchema, googlePricingObservationSchema, historyManifestSchema, MAX_CATALOG_CHUNK_BYTES,
  modelDirectorySchema, modelListingsSchema, nativeChangesSchema, nativeRecordSchema, pricingState, providerCatalogSchema,
  recordChunkSchema, recordIndexChunkSchema, scopeLabel,
  type CatalogProvider, type ChunkRef, type EventBatch, type ModelListing, type NativeChange, type NativeRecord,
} from '../dashboard/src/lib/catalog';

type ObjectValue = Record<string, any>;
const same = (a: unknown, b: unknown): boolean => stable(a) === stable(b);

/** Python verifies the complete ledger before selecting the public field allowlist.
 * Only these projections enter Vite. Raw source/warehouse files never do. */
export function buildHistoricalAssets(dataDir: string): Map<string, string> {
  const payload = JSON.parse(execFileSync('python3', ['-m', 'scripts.historical_projection', '--ledger-dir', join(dataDir, 'historical_evidence')], {
    cwd: fileURLToPath(new URL('..', import.meta.url)), maxBuffer: 256 * 1024 * 1024, timeout: 180000,
  }).toString('utf8'));
  const assets = new Map<string, string>();
  const inventory = JSON.parse(readFileSync(join(dataDir, 'provider_inventory.json'), 'utf8'));
  const captures = payload.captures.map((c: unknown) => historicalCaptureSchema.parse(c));
  const records = payload.assertions.map((r: unknown) => historicalEvidenceSchema.parse(r));
  const checks = payload.checks.map((r: unknown) => historicalCheckSchema.parse(r));
  const ids = new Set(inventory.providers.map((p: ObjectValue) => p.id));
  if ([...captures, ...records, ...checks].some((r) => !ids.has(r.provider))) throw new Error('Historical provider is not in the published source directory');
  const frequencies = (values: string[]) => Object.fromEntries([...new Set(values)].sort().map((k) => [k, values.filter((v) => v === k).length]));
  const providers = inventory.providers.map((provider: ObjectValue) => {
    const selected = records.filter((r: ObjectValue) => r.provider === provider.id);
    const source = captures.filter((c: ObjectValue) => c.provider === provider.id);
    const failed = checks.filter((c: ObjectValue) => c.provider === provider.id);
    if (!source.length) throw new Error('Historical provider has no retained public capture');
    const evidence_chunks = chunkRows(selected, 'records', assets);
    const paths = new Map<string, string>();
    for (const ref of evidence_chunks) for (const r of historicalEvidenceChunkSchema.parse(JSON.parse(assets.get(ref.path)!)).records) paths.set(r.id, ref.path);
    const summaries = selected.map((r: ObjectValue) => { const { evidence: _, source_pointer: __, extractor: ___, ...summary } = r; return { ...summary, detail_path: paths.get(r.id) }; });
    const detail_path = `catalog/historical/${provider.id}.json`;
    const assertionIds = new Set(selected.map((r: ObjectValue) => r.id));
    const manifest = historicalManifestSchema.parse({ schema_version: 2, snapshot_sha256: payload.snapshot_sha256, provider: provider.id, captures: source,
      assertion_count: selected.length, check_count: failed.length, index_chunks: chunkRows(summaries, 'records', assets), evidence_chunks,
      check_chunks: chunkRows(failed, 'records', assets), corrections: payload.corrections.filter((c: ObjectValue) => assertionIds.has(c.assertion_id)) });
    assets.set(detail_path, JSON.stringify(manifest));
    const dates = source.map((c: ObjectValue) => c.archive_capture_at).filter(Boolean).sort();
    return { id: provider.id, name: provider.name, capture_count: source.length, assertion_count: selected.length, check_count: failed.length,
      archive_from: dates[0] ?? null, archive_to: dates.at(-1) ?? null, retrieved_through: source.map((c: ObjectValue) => c.retrieved_at).sort().at(-1),
      states: frequencies(source.map((c: ObjectValue) => c.state)), check_states: frequencies(failed.map((c: ObjectValue) => c.state)), detail_path };
  });
  assets.set('catalog/historical/index.json', JSON.stringify(historicalIndexSchema.parse({ schema_version: 2, snapshot_sha256: payload.snapshot_sha256,
    capture_count: captures.length, assertion_count: records.length, check_count: checks.length, providers })));
  for (const [path, body] of assets) if (path.startsWith('catalog/chunks/')) {
    const value = JSON.parse(body);
    if (value.records[0]?.evidence) historicalEvidenceChunkSchema.parse(value);
    else if (value.records[0]?.detail_path) historicalIndexChunkSchema.parse(value);
    else historicalCheckChunkSchema.parse(value);
  }
  return assets;
}
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
function googleLatestTime(record: ObjectValue, observedAt?: string): string | null {
  const service = record.scope?.service;
  const infos = record.billing?.pricing_info;
  if (record.provider !== 'vertex' || record.kind !== 'sku' || typeof service !== 'string' || !/^services\/[A-Za-z0-9_-]+$/.test(service) ||
    typeof record.native_id !== 'string' || !record.native_id.startsWith(`${service}/skus/`) || !Array.isArray(infos) || infos.length !== 1) return null;
  const time = infos[0]?.effectiveTime;
  if (typeof time !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$/.test(time) || !googlePricingObservationSchema.shape.default_effective_time.safeParse(time).success ||
    (record.rates ?? []).some((rate: ObjectValue) => rate.conditions?.effective_time !== time)) return null;
  if (observedAt) {
    const age = Date.parse(observedAt) - Date.parse(time);
    if (!Number.isFinite(age) || age < -20 * 60 * 1000) return null;
  }
  return time;
}
function googleAsOf(record: ObjectValue, time?: string): ObjectValue {
  const billing = { ...record.billing, pricing_info: [{ ...record.billing.pricing_info[0] }] };
  if (time) billing.pricing_info[0].effectiveTime = time;
  else delete billing.pricing_info[0].effectiveTime;
  const rates = record.rates.map((rate: ObjectValue) => {
    const conditions = { ...rate.conditions };
    if (time) conditions.effective_time = time;
    else delete conditions.effective_time;
    return { ...rate, conditions };
  });
  return { ...record, billing, rates };
}
function currentGoogleRecords(catalog: ObjectValue, observation: ObjectValue | undefined): ObjectValue[] {
  if (!observation) return catalog.records;
  if (catalog.google_pricing_time_mode !== 'latest') throw new Error('Google observation lacks a latest-price catalog');
  for (const time of [observation.default_effective_time, ...Object.values(observation.exceptions)] as string[]) {
    const age = Date.parse(observation.observed_at) - Date.parse(time);
    if (age < -20 * 60 * 1000) throw new Error('Google as-of time is an unconfirmed future effective date');
  }
  const eligible = new Set<string>(catalog.records.filter((r: ObjectValue) => googleLatestTime(r, catalog.google_pricing_observed_at ?? catalog.changed_at)).map((r: ObjectValue) => r.id));
  if (eligible.size !== observation.record_count || Object.keys(observation.exceptions).some((id) => !eligible.has(id))) throw new Error('Inconsistent Google pricing observation');
  const records = catalog.records.map((r: ObjectValue) => eligible.has(r.id) ? googleAsOf(r, observation.exceptions[r.id] ?? observation.default_effective_time) : r);
  const older = records.filter((r: ObjectValue) => eligible.has(r.id) && Date.parse(observation.observed_at) - Date.parse(googleLatestTime(r)!) > 12 * 60 * 60 * 1000).length;
  if (older !== observation.older_than_documented_window_count) throw new Error('Inconsistent Google source-time warning count');
  return records;
}
export function projectRecord(raw: ObjectValue, sourceUrl: string, offerings: ObjectValue[] = [], latestGoogle = false): NativeRecord {
  const ids = new Set([raw.native_id, raw.metadata?.source_model_id].filter(Boolean));
  const models = offerings.filter((o) => o.provider === raw.provider && ids.has(o.provider_model_id)).map((o) => o.model_id);
  const scope = pick(raw.scope, scopeKeys);
  if (scope.source_url) scope.source_url = checkedUrl(scope.source_url);
  return nativeRecordSchema.parse({
    id: raw.id, provider: raw.provider, native_id: raw.native_id, kind: raw.kind, label: raw.label,
    scope, billing: pick(raw.billing, billingKeys), rates: raw.rates ?? [], metadata: pick(raw.metadata, metadataKeys),
    comparison_eligible: false, source_url: checkedUrl(raw.scope?.source_url ?? sourceUrl), reviewed_model_ids: [...new Set(models)].sort(),
    google_pricing_time_mode: latestGoogle && googleLatestTime(raw) ? 'latest' : undefined,
  });
}
export function classifyRecordChange(before: NativeRecord, after: NativeRecord): Array<Pick<NativeChange, 'category' | 'title' | 'details'>> {
  const changes: Array<Pick<NativeChange, 'category' | 'title' | 'details'>> = [];
  const latestGoogle = before.google_pricing_time_mode === 'latest' && after.google_pricing_time_mode === 'latest' && !!googleLatestTime(before) && !!googleLatestTime(after);
  if (latestGoogle) {
    before = googleAsOf(before) as NativeRecord;
    after = googleAsOf(after) as NativeRecord;
    if (same(before, after)) return [];
  }
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
    // Structured Google Money fields mirror those same explicit tier amounts.
    // Only strip them after stableBasis has verified currency/unit/tier scope.
    if (latestGoogle) for (const info of b.pricing_info as ObjectValue[]) for (const tier of info.pricingExpression?.tieredRates ?? []) {
      // Keep currency and unknown Money fields; only these integer components
      // are already represented by the verified native decimal amount.
      delete tier.unitPrice?.units;
      delete tier.unitPrice?.nanos;
    }
    return b;
  };
  if (!same(before.rates, after.rates) && !amounts.length || !same(amounts.length ? withoutAmounts(before) : before.billing, amounts.length ? withoutAmounts(after) : after.billing) || !same(before.scope, after.scope) || before.google_pricing_time_mode !== after.google_pricing_time_mode) {
    changes.push({ category: 'rule', title: 'Billing rules or price basis changed', details: [{ field: 'Billing basis', before: `${pricingState(before)} · ${billingBasis(before)}`, after: `${pricingState(after)} · ${billingBasis(after)}` }] });
  }
  if (!same(before.metadata, after.metadata) || before.label !== after.label) changes.push({ category: 'catalog', title: 'Listing metadata changed', details: [{ field: 'Listing', before: before.label, after: after.label }] });
  if (!changes.length) changes.push({ category: 'catalog', title: 'Source record changed', details: [] });
  return changes;
}

export function projectListing(r: NativeRecord): ModelListing {
  const m = r.metadata;
  const array = (value: unknown): string[] => Array.isArray(value) ? value.filter((v) => typeof v === 'string') : [];
  return { id: r.id, provider: r.provider, native_id: r.native_id, kind: r.kind, label: r.label,
    reviewed_model_ids: r.reviewed_model_ids, scope_label: scopeLabel(r), pricing_state: pricingState(r), billing_basis: billingBasis(r),
    modalities: [...new Set([...array(m.input_modalities), ...array((m.architecture as any)?.input_modalities),
      ...array(m.output_modalities), ...array((m.architecture as any)?.output_modalities), ...array(m.modalities)])] };
}

// The only persisted outputs are public assets. Warehouse files are never changed.
// Content-addressed chunks are shared by provider/category history manifests.
export function chunkRows<T>(rows: T[], field: string, assets: Map<string, string>): ChunkRef[] {
  const refs: ChunkRef[] = [];
  let current: T[] = [];
  let bytes = Buffer.byteLength(JSON.stringify({ schema_version: 1, [field]: [] }));
  const flush = () => {
    if (!current.length) return;
    const body = JSON.stringify({ schema_version: 1, [field]: current });
    const sha256 = createHash('sha256').update(body).digest('hex');
    const path = `catalog/chunks/${sha256}.json`;
    assets.set(path, body);
    refs.push({ path, sha256, count: current.length, bytes: Buffer.byteLength(body) });
    current = []; bytes = Buffer.byteLength(JSON.stringify({ schema_version: 1, [field]: [] }));
  };
  for (const row of rows) {
    const size = Buffer.byteLength(JSON.stringify(row));
    if (size + bytes + (current.length ? 1 : 0) > MAX_CATALOG_CHUNK_BYTES) flush();
    if (size + bytes > MAX_CATALOG_CHUNK_BYTES) throw new Error('A public record exceeds the bounded chunk size; explicit projection review is required.');
    bytes += size + (current.length ? 1 : 0); current.push(row);
  }
  flush();
  return refs;
}

export function buildDashboardAssets(dataDir: string): Map<string, string> {
  const read = (file: string) => JSON.parse(readFileSync(join(dataDir, file), 'utf8')) as any;
  const inventory = read('provider_inventory.json');
  const offerings = read('offerings.json');
  const assets = new Map<string, string>();
  const put = (path: string, value: unknown) => assets.set(path, JSON.stringify(value));
  const providers: CatalogProvider[] = [];
  const recordSources = new Map<string, string>();
  const listings: ModelListing[] = [];
  const kindTotals: Record<string, number> = {}, basisTotals: Record<string, number> = {}, stateTotals: Record<string, number> = {};
  const count = (counts: Record<string, number>, key: string) => { counts[key] = (counts[key] ?? 0) + 1; };
  for (const p of inventory.providers) {
    if (!/^[a-z0-9_-]+$/.test(p.id) || p.latest_path !== `provider_catalogs/${p.id}.json`) throw new Error('Unsafe provider catalog path');
    const c = read(p.latest_path);
    if (c.provider !== p.id || c.records.length !== p.record_count || c.catalog_sha256 !== p.catalog_sha256) throw new Error(`Inconsistent provider catalog: ${p.id}`);
    const observation = p.google_pricing_observation ? googlePricingObservationSchema.parse({ mode: 'latest', observed_at: p.last_seen_at, source_sha256: p.source_sha256,
      default_effective_time: p.google_pricing_observation.default_effective_time, record_count: p.google_pricing_observation.record_count,
      older_than_documented_window_count: p.google_pricing_observation.older_than_documented_window_count, exceptions: p.google_pricing_observation.exceptions }) : undefined;
    const records = currentGoogleRecords(c, observation).map((r: ObjectValue) => projectRecord(r, p.source_url, offerings,
      !!observation && !!googleLatestTime(r, observation.observed_at)));
    if (new Set(records.map((r: NativeRecord) => r.id)).size !== records.length) throw new Error('Duplicate native records');
    const kindCounts: Record<string, number> = {};
    for (const r of records) {
      count(kindCounts, r.kind); count(kindTotals, r.kind); count(basisTotals, billingBasis(r)); count(stateTotals, pricingState(r));
      recordSources.set(r.id, r.source_url);
      // Cloud SKUs and document labels never stand in for canonical model identities.
      if (['model', 'provider_route', 'model_flavor'].includes(r.kind)) listings.push(projectListing(r));
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
    const recordChunks = chunkRows(records.map((r: NativeRecord) => nativeRecordSchema.parse(r)), 'records', assets);
    const detailPaths = new Map<string, string>();
    for (const ref of recordChunks) for (const r of recordChunkSchema.parse(JSON.parse(assets.get(ref.path)!)).records) detailPaths.set(r.id, ref.path);
    const summaries = records.map((r: NativeRecord) => ({ ...projectListing(r), comparison_eligible: false,
      currencies: [...new Set(r.rates.map((rate) => rate.currency).filter(Boolean))], units: [...new Set(r.rates.map((rate) => rate.unit).filter(Boolean))],
      rate_count: r.rates.length, rate_preview: r.rates.slice(0, 2), detail_path: detailPaths.get(r.id)! }));
    // Validate index rows before publishing; previews retain original decimals/units.
    const validated = recordIndexChunkSchema.parse({ schema_version: 1, records: summaries }).records;
    put(`catalog/providers/${p.id}.json`, providerCatalogSchema.parse({ schema_version: 2, provider: p.id, catalog_sha256: c.catalog_sha256, revision: c.revision,
      billing_notes: c.billing_notes ?? [], source_evidence: (c.source_evidence ?? []).map((e: any) => ({ source_url: checkedUrl(e.source_url), response_sha256: e.response_sha256 })),
      record_count: records.length, index_chunks: chunkRows(validated, 'records', assets), record_chunks: recordChunks, pricing_observation: observation }));
  }
  const providerMap = new Map(providers.map((p) => [p.id, p]));
  const previous = new Map<string, NativeRecord>();
  const everSeen = new Set<string>();
  const notesSeen = new Set<string>();
  const events: NativeChange[] = [];
  const eventIds = new Set<string>();
  // Replay append-only history in its recorded order, never fabricate earlier states.
  for (const { event: e, observationOnly } of readNativeHistory(dataDir)) {
    const p = providerMap.get(e.provider);
    if (!p) throw new Error('History references an unknown provider');
    if (eventIds.has(e.id)) throw new Error('Duplicate inventory history event');
    eventIds.add(e.id);
    const before = previous.get(e.record_id);
    const after = e.after ? projectRecord(e.after, p.source_url, offerings, e.google_pricing_time_mode === 'latest') : null;
    if (observationOnly) {
      // Explicitly migrated, two-sided request evidence establishes an as-of
      // observation, not a tariff event. Keep exact state for later replay.
      if (!before || !after) throw new Error('Observation lacks a prior source record');
      previous.set(e.record_id, after); everSeen.add(e.record_id);
      continue;
    }
    const fields: Array<Pick<NativeChange, 'category' | 'title' | 'details'>> = [];
    if (e.kind === 'billing_notes_changed') {
      fields.push({ category: 'rule', title: notesSeen.has(e.provider) ? 'Billing guide changed' : 'Billing guide first observed', details: [] }); notesSeen.add(e.provider);
    } else if (e.kind === 'record_added') fields.push({ category: 'catalog', title: everSeen.has(e.record_id) ? 'Source listing reappeared' : 'First observed listing', details: [] });
    else if (e.kind === 'record_no_longer_listed') fields.push({ category: 'catalog', title: 'No longer in selected source', details: [] });
    else if (e.kind === 'record_changed' && before && after) fields.push(...classifyRecordChange(e.google_pricing_time_mode === 'latest' ? { ...before, google_pricing_time_mode: 'latest' } : before, after));
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
  const groups = new Map<string, NativeChange[]>();
  for (const event of nativeChangesSchema.parse({ schema_version: 1, events }).events) {
    const key = `${event.provider}:${event.observed_at}:${event.category}`;
    const group = groups.get(key) ?? []; group.push(event); groups.set(key, group);
  }
  const batches: EventBatch[] = [...groups].map(([id, selected]) => ({ id, provider: selected[0].provider,
    observed_at: selected[0].observed_at, category: selected[0].category, event_count: selected.length, chunks: chunkRows(selected, 'events', assets) }));
  const changeCounts: Record<string, number> = {};
  for (const category of ['price', 'rule', 'catalog'] as const) {
    const selected = batches.filter((b) => b.category === category); changeCounts[category] = selected.reduce((n, b) => n + b.event_count, 0);
    put(`catalog/changes/${category}.json`, historyManifestSchema.parse({ schema_version: 2, event_count: changeCounts[category], batches: selected }));
  }
  for (const p of providers) {
    const selected = batches.filter((b) => b.provider === p.id);
    put(p.history_path, historyManifestSchema.parse({ schema_version: 2, event_count: selected.reduce((n, b) => n + b.event_count, 0), batches: selected }));
  }
  const active = offerings.filter((o: ObjectValue) => o.active);
  const providerSets = new Map<string, Set<string>>();
  for (const o of active) { const set = providerSets.get(o.model_id) ?? new Set<string>(); set.add(o.provider); providerSets.set(o.model_id, set); }
  const coverage = { reviewed_model_count: new Set(offerings.map((o: ObjectValue) => o.model_id)).size,
    reviewed_offering_count: offerings.length, active_reviewed_offering_count: active.length,
    reviewed_provider_count: new Set(offerings.map((o: ObjectValue) => o.provider)).size, model_listing_count: listings.length,
    kind_counts: kindTotals, billing_basis_counts: basisTotals, pricing_state_counts: stateTotals,
    single_provider_model_count: [...providerSets.values()].filter((set) => set.size === 1).length,
    gateway_only_model_count: [...providerSets.values()].filter((set) => [...set].every((id) => accessKind(id) === 'Gateway')).length,
    unknown_context_offering_count: active.filter((o: ObjectValue) => o.context_window == null).length,
    reviewed_price_change_count: existsSync(join(dataDir, 'changes.json')) ? read('changes.json').filter((e: ObjectValue) => e.kind === 'price_changed').length : 0 };
  put('catalog/index.json', catalogIndexSchema.parse({ schema_version: 2, updated_at: inventory.updated_at,
    record_count: providers.reduce((sum, p) => sum + p.record_count, 0), providers, change_counts: changeCounts, coverage }));
  const sorted = modelListingsSchema.parse({ schema_version: 1, listings: listings.sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id)) }).listings;
  put('catalog/models.json', modelDirectorySchema.parse({ schema_version: 2, listing_count: sorted.length, chunks: chunkRows(sorted, 'listings', assets) }));
  return assets;
}
