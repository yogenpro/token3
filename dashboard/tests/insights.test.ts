import { describe, expect, it } from 'vitest';
import { comparisonProviders, reviewedChangeGroups, workloadPriceMap } from '../src/lib/insights';
import { datasetSchema, publicationSchema, type Change, type Dataset } from '../src/lib/data';
import { defaultWorkload, rankOfferings } from '../src/lib/pricing';
import { publicationMetadata } from '../../scripts/publication';
import models from '../../data/models.json';
import offerings from '../../data/offerings.json';
import prices from '../../data/latest_prices.json';
import history from '../../data/price_history.json';
import changes from '../../data/changes.json';
import status from '../../data/status.json';
const data = datasetSchema.parse({ models, offerings, prices, history, changes, status });

const base = data.offerings[0], price = data.prices.find((p) => p.offering_id === base.id)!;
function fixture(): Dataset {
  return { ...data, models: [data.models.find((m) => m.id === base.model_id)!], offerings: [
    { ...base, id: 'normal', provider: 'deepinfra', active: true, region: 'a', context_window: 10000, min_input_tokens: 0, max_input_tokens: null, service_tier: 'standard' },
    { ...base, id: 'cheap', provider: 'novita', active: true, region: 'b', context_window: 10000, min_input_tokens: 0, max_input_tokens: null, service_tier: 'standard' },
    { ...base, id: 'paused', provider: 'together', active: true, region: 'a', context_window: 10000, min_input_tokens: 0, max_input_tokens: null, service_tier: 'standard' },
  ], prices: [
    { ...price, offering_id: 'normal', input_per_million: 2, output_per_million: 4 },
    { ...price, offering_id: 'cheap', input_per_million: 1, output_per_million: 2 },
    { ...price, offering_id: 'paused', input_per_million: 0, output_per_million: 0 },
  ] };
}

describe('reviewed insights and pauses', () => {
  it('groups component events into one observed offering update, never mixes sources or dates', () => {
    const c: Change = { id: 'a', offering_id: 'o', model_id: 'm', provider: 'vercel', observed_at: '2026-10-18T11:00:00Z', kind: 'price_changed', field: 'input_per_million', old: 1, new: 0.5, change_pct: -50 };
    const groups = reviewedChangeGroups([c, { ...c, id: 'b', field: 'output_per_million' }, { ...c, id: 'c', kind: 'offering_added' }, { ...c, id: 'd', offering_id: 'other' }, { ...c, id: 'e', observed_at: '2026-10-17T11:00:00Z' }]);
    expect(groups).toHaveLength(3);
    expect(groups.find((g) => g.changes.some((e) => e.id === 'a'))!.changes).toHaveLength(2);
    expect(groups.every((g) => g.changes.every((c) => c.kind === 'price_changed'))).toBe(true);
  });
  it('cannot let a zero-price paused provider win, but never mutates its retained history/availability', () => {
    const d = fixture(), before = JSON.stringify(d);
    expect(rankOfferings(d, base.model_id, defaultWorkload).map((r) => r.offering.id)).toEqual(['cheap', 'normal']);
    expect(comparisonProviders(d)).not.toContain('together');
    expect(workloadPriceMap(d, defaultWorkload, 'standard', 'all', '')[0].cells.has('together')).toBe(false);
    expect(JSON.stringify(d)).toBe(before);
  });
  it('respects region, tier, prompt bands and known output/context limits', () => {
    const d = fixture();
    expect(workloadPriceMap(d, defaultWorkload, 'standard', 'a', '')[0].cells.has('novita')).toBe(false);
    expect(workloadPriceMap(d, defaultWorkload, 'priority', 'all', '')[0].cells.size).toBe(0);
    d.offerings[1].max_input_tokens = 100;
    expect(workloadPriceMap(d, defaultWorkload, 'standard', 'all', '')[0].cells.has('novita')).toBe(false);
    d.offerings[0].context_window = 100;
    expect(workloadPriceMap(d, defaultWorkload, 'standard', 'all', '')[0].cells.size).toBe(0);
  });
  it('keeps unpublished cache as fallback, unknown capacity explicit and missing quotes absent', () => {
    const d = fixture(); d.prices[0].cache_read_per_million = null; d.offerings[0].context_window = null;
    const map = workloadPriceMap(d, { ...defaultWorkload, cacheHitPercent: 100 }, 'standard', 'all', '');
    expect(map[0].cells.get('deepinfra')![0].cost).toMatchObject({ cacheFallback: true, contextUnverified: true });
    d.prices = d.prices.filter((p) => p.offering_id !== 'normal');
    expect(workloadPriceMap(d, defaultWorkload, 'standard', 'all', '')[0].cells.has('deepinfra')).toBe(false);
  });
});

describe('publication provenance', () => {
  it('keeps collection and build timestamps distinct without asserting a deployment time', () => {
    const p = publicationMetadata(data.status.last_run_at, { PUBLICATION_COMMIT_SHA: 'a'.repeat(40), PUBLICATION_MODE: 'automatic' }, '2026-10-19T00:00:00Z');
    expect(publicationSchema.parse(p).data_collected_at).toBe(data.status.last_run_at);
    expect(p.built_at).not.toBe(p.data_collected_at);
    expect(p).not.toHaveProperty('published_at');
    expect(datasetSchema.parse({ ...data, publication: p }).publication).toEqual(p);
    expect(() => datasetSchema.parse({ ...data, publication: { ...p, data_collected_at: '2026-10-01T00:00:00Z' } })).toThrow(/Publication metadata/);
  });
  it('rejects invalid provenance values', () => {
    expect(() => publicationMetadata(data.status.last_run_at, { PUBLICATION_COMMIT_SHA: 'main' })).toThrow();
    expect(() => publicationMetadata('unknown')).toThrow();
    expect(() => publicationMetadata(data.status.last_run_at, { PUBLICATION_MODE: 'unverified' })).toThrow();
  });
});
