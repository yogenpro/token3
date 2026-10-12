import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildDashboardAssets, classifyRecordChange, projectRecord } from '../../scripts/dashboard_projection';
import { billingBasis, catalogIndexSchema, MAX_CATALOG_CHUNK_BYTES, nativeRateText, pricingState, type NativeRecord } from '../src/lib/catalog';
import { projectedEvents, projectedListings, projectedProvider } from './projected-assets';

const record = (): NativeRecord => projectRecord({ id: 'test-model', provider: 'openrouter', native_id: 'vendor/model', kind: 'model', label: 'Model', scope: {}, billing: { state: 'reported', rules: { prompt: '0.000001' } }, rates: [{ dimension: 'prompt', amount: '0.000001', currency: 'USD', unit: 'input token', conditions: {} }], metadata: {} }, 'https://example.com/pricing');

describe('native billing stays native', () => {
  it('preserves exact small amounts and denominators', () => {
    const r = record(); expect(nativeRateText(r.rates[0])).toBe('USD 0.000001 / input token');
    expect(pricingState(r)).toBe('Published native rate'); expect(billingBasis(r)).toBe('Tokens');
    expect(r.comparison_eligible).toBe(false);
  });
  it('unknown currency and missing prices never become zero', () => {
    const r = record(); r.rates[0].currency = null;
    expect(pricingState(r)).toBe('Currency unverified'); expect(nativeRateText(r.rates[0])).toContain('Currency unknown');
    r.rates = []; r.billing = { state: 'source_native_or_unpriced', rules: null };
    expect(pricingState(r)).toBe('Price not published'); expect(r.rates).toEqual([]);
  });
  it('PDF evidence and unaligned source cells are not usable quotes', () => {
    const r = record(); r.kind = 'document_page'; expect(pricingState(r)).toBe('Source evidence');
    r.kind = 'document_row'; r.billing.alignment_verified = false; expect(pricingState(r)).toBe('Rule-based');
  });
  it('credits, compute, and mixed rules remain separate billing bases', () => {
    const r = record(); r.rates = []; r.billing = { cells: ['DBU per 1M tokens', '12'] }; expect(billingBasis(r)).toBe('Mixed');
    r.billing = { unit: 'credits' }; expect(billingBasis(r)).toBe('Credits / native units');
    r.billing = { unit: 'GiBy.h' }; expect(billingBasis(r)).toBe('Storage / memory');
  });
  it('only exact same-provider reviewed identities are linked', () => {
    const raw = record(); const offers = [{ provider: 'openrouter', provider_model_id: 'vendor/model', model_id: 'reviewed/id' }, { provider: 'vercel', provider_model_id: 'vendor/model', model_id: 'wrong/id' }];
    expect(projectRecord(raw, raw.source_url, offers).reviewed_model_ids).toEqual(['reviewed/id']);
    expect(projectRecord({ ...raw, native_id: 'similar/model' }, raw.source_url, offers).reviewed_model_ids).toEqual([]);
  });
  it('publishes explicit projection fields, not arbitrary API response properties', () => {
    const raw = { ...record(), raw_body: 'private response', authorization: 'collector-only', metadata: { context_length: 42, collector_token: 'never publish', api_base_url: 'https://private.example' } };
    const r = projectRecord(raw, raw.source_url); expect(JSON.stringify(r)).not.toContain('collector-only'); expect(JSON.stringify(r)).not.toContain('never publish'); expect(r.metadata.context_length).toBe(42);
  });
  it.each(['http://example.com/pricing', 'https://user:pass@example.com/pricing', 'https://example.com/pricing?api_key=not-public', 'https://example.com/pricing?X-Goog-Api-Key=not-public', 'https://example.com/pricing?refresh_token=not-public'])('rejects unsafe source URL %s', (url) => {
    expect(() => projectRecord(record(), url)).toThrow();
  });
});

describe('source changes are not all price changes', () => {
  it('classifies exact same-basis amount changes without duplicate rules', () => {
    const before = record(); const after = structuredClone(before); after.rates[0].amount = '0.000002'; (after.billing.rules as any).prompt = '0.000002';
    const changes = classifyRecordChange(before, after); expect(changes.map((c) => c.category)).toEqual(['price']); expect(changes[0].details[0].before).toBe('USD 0.000001 / input token');
  });
  it.each(['unit', 'currency'])('changing %s is a rule change, not a cut', (key) => {
    const before = record(); const after = structuredClone(before); after.rates[0][key as 'unit' | 'currency'] = key === 'unit' ? '1M input tokens' : 'EUR'; after.rates[0].amount = '0.0000005';
    expect(classifyRecordChange(before, after).map((c) => c.category)).toEqual(['rule']);
  });
  it('changed regions and bands are not equal price bases', () => {
    const before = record(); const after = structuredClone(before); after.scope.region = 'EU'; after.rates[0].amount = '0.0000005';
    expect(classifyRecordChange(before, after).some((c) => c.category === 'price')).toBe(false);
  });
  it('source-cell extracts and unverified units cannot imply price changes', () => {
    for (const conditions of [{ active_rate_not_inferred: true }, { unit_verified: false }]) {
      const before = record(); before.rates[0].conditions = conditions; const after = structuredClone(before); after.rates[0].amount = '0';
      expect(classifyRecordChange(before, after).map((c) => c.category)).toEqual(['rule']);
    }
  });
  it('metadata and non-price formulas get their own categories', () => {
    const before = record(); const after = structuredClone(before); after.metadata.context_length = 123;
    expect(classifyRecordChange(before, after).map((c) => c.category)).toEqual(['catalog']);
    after.billing.discount = 'Account-specific'; expect(classifyRecordChange(before, after).map((c) => c.category)).toEqual(['rule', 'catalog']);
  });
});

describe('read-only static projections', () => {
  const dataDir = fileURLToPath(new URL('../../data', import.meta.url));
  const inventory = JSON.parse(readFileSync(`${dataDir}/provider_inventory.json`, 'utf8'));
  const fingerprint = (): Record<string, string> => {
    const paths = (dir: string): string[] => readdirSync(dir, { withFileTypes: true }).flatMap((entry) => entry.isDirectory() ? paths(join(dir, entry.name)) : [join(dir, entry.name)]);
    return Object.fromEntries(paths(dataDir).map((path) => [path, createHash('sha256').update(readFileSync(path)).digest('hex')]));
  };
  const before = fingerprint();
  const assets = buildDashboardAssets(dataDir);
  it('building the real public assets leaves every production input byte-identical', () => {
    expect(fingerprint()).toEqual(before);
  });
  it('the index is small and contains no catalogs or response bodies', () => {
    const raw = assets.get('catalog/index.json')!; const index = catalogIndexSchema.parse(JSON.parse(raw));
    expect(index.providers.length).toBe(inventory.provider_count); expect(index.record_count).toBe(inventory.providers.reduce((sum: number, p: any) => sum + p.record_count, 0));
    expect(raw.length).toBeLessThan(60000); expect(raw).not.toContain('raw_body'); expect(raw).not.toContain('billing_notes');
  });
  it('all provider projections have source provenance and remain comparison-ineligible', () => {
    for (const p of inventory.providers) {
      const detail = projectedProvider(assets, p.id);
      const source = JSON.parse(readFileSync(`${dataDir}/${p.latest_path}`, 'utf8'));
      expect(detail.records.length).toBe(p.record_count); expect(detail.records.every((r) => !r.comparison_eligible)).toBe(true);
      for (let i = 0; i < detail.records.length; i++) {
        expect(detail.records[i].id).toBe(source.records[i].id);
        expect(detail.records[i].native_id).toBe(source.records[i].native_id);
        // Source-time overlays are tested independently; original amounts,
        // dimensions, currencies and units must survive exactly in every row.
        expect(detail.records[i].rates.map(({ dimension, amount, currency, unit }) => ({ dimension, amount, currency, unit })))
          .toEqual(source.records[i].rates.map(({ dimension, amount, currency, unit }: any) => ({ dimension, amount, currency, unit })));
      }
    }
  });
  it('the model directory excludes meters, SKU dimensions, and ambiguous document labels', () => {
    const directory = { listings: projectedListings(assets) };
    expect(directory.listings.length).toBeGreaterThan(1000); expect(directory.listings.every((r) => ['model', 'provider_route', 'model_flavor'].includes(r.kind))).toBe(true);
    expect(directory.listings.some((r) => r.provider === 'openrouter')).toBe(true);
  });
  it('splits source events by category and keeps absences out of prices', () => {
    for (const category of ['price', 'rule', 'catalog']) {
      const feed = projectedEvents(assets, `catalog/changes/${category}.json`);
      expect(feed.events.every((e) => e.category === category)).toBe(true);
      if (category === 'price') expect(feed.events.some((e) => e.title.includes('First observed') || e.title.includes('No longer'))).toBe(false);
    }
  });
  it('bounds every immutable chunk and publishes small history manifests instead of full feeds', () => {
    for (const [path, body] of assets) if (path.startsWith('catalog/chunks/')) expect(Buffer.byteLength(body)).toBeLessThanOrEqual(MAX_CATALOG_CHUNK_BYTES);
    expect(Buffer.byteLength(assets.get('catalog/providers/vertex.json')!)).toBeLessThan(60000);
    expect(Buffer.byteLength(assets.get('catalog/history/vertex.json')!)).toBeLessThan(60000);
    expect(Buffer.byteLength(assets.get('catalog/changes/rule.json')!)).toBeLessThan(60000);
  });
  it('coverage counts use separate denominators and retain inactive offers', () => {
    const { coverage } = catalogIndexSchema.parse(JSON.parse(assets.get('catalog/index.json')!));
    const offers = JSON.parse(readFileSync(`${dataDir}/offerings.json`, 'utf8'));
    expect(coverage.reviewed_offering_count).toBe(offers.length);
    expect(coverage.active_reviewed_offering_count).toBe(offers.filter((o: any) => o.active).length);
    expect(coverage.model_listing_count).toBe(projectedListings(assets).length);
    expect(Object.values(coverage.kind_counts).reduce((a, b) => a + b, 0)).toBe(inventory.providers.reduce((n: number, p: any) => n + p.record_count, 0));
  });
  it('never exposes source archive or authenticated response assets', () => {
    expect([...assets.keys()].every((path) => /^catalog\//.test(path))).toBe(true);
    expect([...assets.keys()].some((path) => /provider_sources|responses|\.jsonl/.test(path))).toBe(false);
  });
});
