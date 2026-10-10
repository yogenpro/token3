import { afterEach, describe, expect, it } from 'vitest';
import { mkdtempSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildDashboardAssets, classifyRecordChange, projectRecord } from '../../scripts/dashboard_projection';
import { nativeChangesSchema, providerCatalogSchema } from '../src/lib/catalog';

const first = '2026-10-10T07:00:00Z';
const second = '2026-10-11T07:00:00Z';
const third = '2026-10-12T07:00:00Z';
const source = 'https://cloudbilling.googleapis.com/v1/services/FIXTURE/skus?currencyCode=USD&pageSize=500';
const raw = (time = first, nanos = 750000, suffix = '1') => ({
  id: `vertex-${suffix.repeat(24)}`, provider: 'vertex', native_id: `services/FIXTURE/skus/${suffix}`, kind: 'sku', label: 'Fixture SKU',
  scope: { service: 'services/FIXTURE', regions: ['us-east1'] }, metadata: { category: { resourceFamily: 'AI' } }, comparison_eligible: false,
  billing: { pricing_info: [{ effectiveTime: time, pricingExpression: { usageUnit: '1k', baseUnit: 'token', baseUnitConversionFactor: 1000,
    tieredRates: [{ startUsageAmount: 0, unitPrice: { currencyCode: 'USD', units: '0', nanos } }] } }] },
  rates: [{ dimension: 'tieredRate', amount: String(nanos / 1e9), currency: 'USD', unit: '1k',
    conditions: { effective_time: time, start_usage_amount: 0, base_unit: 'token', base_unit_conversion: 1000 } }],
});
const record = (time = first, nanos = 750000, latest = true) => projectRecord(raw(time, nanos), source, [], latest);
const temporary: string[] = [];
afterEach(() => { for (const path of temporary.splice(0)) rmSync(path, { recursive: true, force: true }); });

function fixture() {
  const path = mkdtempSync(join(tmpdir(), 'token3-native-retention-')); temporary.push(path);
  mkdirSync(join(path, 'provider_catalogs'));
  const write = (name: string, value: unknown) => writeFileSync(join(path, name), JSON.stringify(value));
  const records = [raw(second, 500000), raw(first, 750000, '2')];
  const provider = { id: 'vertex', name: 'Vertex', source_url: source, source_urls: [source], source_kind: 'api+documentation',
    latest_path: 'provider_catalogs/vertex.json', record_count: records.length, revision: 2, catalog_sha256: '2'.repeat(64), source_sha256: '3'.repeat(64),
    first_seen_at: first, last_seen_at: third,
    google_pricing_observation: { record_count: 2, older_than_documented_window_count: 0, default_effective_time: third, exceptions: { [records[1].id]: '2026-10-12T07:10:00Z' }, collector_token: 'must-not-publish' } };
  const catalog = { schema_version: 1, parser_version: 1, provider: 'vertex', source_kind: provider.source_kind, records, billing_notes: [], source_evidence: [],
    revision: provider.revision, catalog_sha256: provider.catalog_sha256, changed_at: second, google_pricing_time_mode: 'latest', google_pricing_observed_at: second };
  // The second SKU's old timestamp belongs to its discovery, but the persisted
  // semantic snapshot is from second. Use a current snapshot time for it too.
  catalog.records[1] = raw(second, 750000, '2');
  write('provider_inventory.json', { schema_version: 2, updated_at: third, provider_count: 1, providers: [provider] });
  write('provider_catalogs/vertex.json', catalog);
  write('offerings.json', []);
  const event = (id: string, kind: string, after: ReturnType<typeof raw>, revision: number, at: string, latest = false) => ({
    id, kind, provider: 'vertex', record_id: after.id, after, revision, observed_at: at, ...(latest ? { google_pricing_time_mode: 'latest' } : {}),
  });
  const events = [event('discovery-1', 'record_added', raw(), 1, first), event('discovery-2', 'record_added', raw(first, 750000, '2'), 1, first),
    event('changed-1', 'record_changed', raw(second, 500000), 2, second, true)];
  writeFileSync(join(path, 'inventory_history.jsonl'), events.map((e) => JSON.stringify(e)).join('\n') + '\n');
  return { path, provider, catalog, write };
}

describe('latest Google observations are not billing-effective dates', () => {
  it('does not manufacture a rule or catalog change from a verified as-of rollover', () => {
    expect(classifyRecordChange(record(), record(second))).toEqual([]);
  });
  it('detects a genuine native amount change across as-of timestamps without duplicate Money rules', () => {
    const changes = classifyRecordChange(record(), record(second, 500000));
    expect(changes.map((c) => c.category)).toEqual(['price']);
    expect(changes[0].details).toEqual([{ field: 'tieredRate', before: 'USD 0.00075 / 1k', after: 'USD 0.0005 / 1k' }]);
  });
  it('retains unknown Money fields as rules even when its amount changes', () => {
    const before = record(); const after = record(second, 500000);
    (after.billing.pricing_info as any[])[0].pricingExpression.tieredRates[0].unitPrice.new_condition = 'New billing qualifier';
    expect(classifyRecordChange(before, after).map((c) => c.category)).toEqual(['price', 'rule']);
  });
  it('keeps unknown or explicit-range effective dates in the billing basis', () => {
    expect(classifyRecordChange(record(first, 750000, false), record(second, 500000, false)).map((c) => c.category)).toEqual(['rule']);
    expect(classifyRecordChange(record(), record(first, 750000, false)).map((c) => c.category)).toEqual(['rule']);
  });
  it.each(['unit', 'currency', 'tier', 'aggregation', 'promotion', 'region'])('preserves changed %s rules', (field) => {
    const before = record(); const after = record(second, 500000);
    if (field === 'unit') after.rates[0].unit = '1M tokens';
    if (field === 'currency') after.rates[0].currency = 'EUR';
    if (field === 'tier') after.rates[0].conditions.start_usage_amount = 1000;
    if (field === 'aggregation') (after.billing.pricing_info as any[])[0].aggregationInfo = { aggregationInterval: 'MONTHLY' };
    if (field === 'promotion') after.rates[0].conditions.promotion_effective_date = third;
    if (field === 'region') after.scope.regions = ['europe-west1'];
    const categories = classifyRecordChange(before, after).map((c) => c.category);
    expect(categories).toContain('rule');
    if (field !== 'aggregation') expect(categories).not.toContain('price');
  });
  it('does not reinterpret multi-version schedules or dates on another provider', () => {
    const before = record(); const after = record(second, 500000);
    (before.billing.pricing_info as any[]).push(structuredClone((before.billing.pricing_info as any[])[0]));
    (after.billing.pricing_info as any[]).push(structuredClone((after.billing.pricing_info as any[])[0]));
    expect(classifyRecordChange(before, after).some((e) => e.category === 'price')).toBe(false);
    before.provider = after.provider = 'azure';
    expect(classifyRecordChange(before, after).some((e) => e.category === 'price')).toBe(false);
  });
});

describe('compact latest observation projection', () => {
  it('reconstructs exact current timestamps from the default and exceptions without rewriting stored history', () => {
    const { path } = fixture();
    const before = [...readdirSync(path).filter((p) => p.endsWith('.json') || p.endsWith('.jsonl')), 'provider_catalogs/vertex.json']
      .map((file) => [file, readFileSync(join(path, file), 'utf8')] as const);
    const assets = buildDashboardAssets(path);
    const detail = providerCatalogSchema.parse(JSON.parse(assets.get('catalog/providers/vertex.json')!));
    expect(detail.pricing_observation?.observed_at).toBe(third);
    expect(detail.pricing_observation?.source_sha256).toBe('3'.repeat(64));
    expect(detail.records.map((r) => r.rates[0].conditions.effective_time)).toEqual([third, '2026-10-12T07:10:00Z']);
    expect((detail.records[1].billing.pricing_info as any[])[0].effectiveTime).toBe('2026-10-12T07:10:00Z');
    expect(detail.records.every((r) => r.google_pricing_time_mode === 'latest' && !r.comparison_eligible)).toBe(true);
    expect(JSON.stringify(detail)).not.toContain('must-not-publish');
    expect(JSON.parse(assets.get('catalog/index.json')!).providers[0].changed_at).toBe(second);
    const prices = nativeChangesSchema.parse(JSON.parse(assets.get('catalog/changes/price.json')!));
    expect(prices.events).toHaveLength(1);
    expect(prices.events[0].observed_at).toBe(second);
    expect(nativeChangesSchema.parse(JSON.parse(assets.get('catalog/changes/rule.json')!)).events).toHaveLength(0);
    for (const [file, content] of before) expect(readFileSync(join(path, file), 'utf8')).toBe(content);
  });
  it('retains older past as-of timestamps with a validated source-time warning', () => {
    const { path, provider, write } = fixture();
    provider.last_seen_at = '2026-10-12T21:00:00Z';
    provider.google_pricing_observation.older_than_documented_window_count = 2;
    write('provider_inventory.json', { updated_at: provider.last_seen_at, provider_count: 1, providers: [provider] });
    const detail = providerCatalogSchema.parse(JSON.parse(buildDashboardAssets(path).get('catalog/providers/vertex.json')!));
    expect(detail.pricing_observation?.older_than_documented_window_count).toBe(2);
    expect(detail.records.map((r) => r.rates[0].conditions.effective_time)).toEqual([third, '2026-10-12T07:10:00Z']);
    expect(detail.records.every((r) => r.google_pricing_time_mode === 'latest' && !r.comparison_eligible)).toBe(true);
  });
  it.each(['count', 'unknown record', 'invalid time', 'future effective date', 'warning count', 'unconfirmed mode'])('fails closed on %s observation mismatch', (field) => {
    const { path, provider, catalog, write } = fixture();
    if (field === 'count') provider.google_pricing_observation.record_count = 3;
    if (field === 'unknown record') provider.google_pricing_observation.exceptions = { [`vertex-${'f'.repeat(24)}`]: third };
    if (field === 'invalid time') provider.google_pricing_observation.default_effective_time = 'not-a-time';
    if (field === 'future effective date') provider.google_pricing_observation.default_effective_time = '2026-10-13T07:00:00Z';
    if (field === 'warning count') provider.google_pricing_observation.older_than_documented_window_count = 1;
    if (field === 'unconfirmed mode') catalog.google_pricing_time_mode = 'unknown';
    write('provider_inventory.json', { updated_at: third, provider_count: 1, providers: [provider] });
    write('provider_catalogs/vertex.json', catalog);
    expect(() => buildDashboardAssets(path)).toThrow();
  });
  it('retains historical classification for legacy entries without a verified latest-mode marker', () => {
    const { path } = fixture();
    const file = join(path, 'inventory_history.jsonl');
    const entries = readFileSync(file, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
    delete entries[2].google_pricing_time_mode;
    writeFileSync(file, entries.map((e) => JSON.stringify(e)).join('\n') + '\n');
    const assets = buildDashboardAssets(path);
    expect(nativeChangesSchema.parse(JSON.parse(assets.get('catalog/changes/price.json')!)).events).toHaveLength(0);
    expect(nativeChangesSchema.parse(JSON.parse(assets.get('catalog/changes/rule.json')!)).events).toHaveLength(1);
  });
});
