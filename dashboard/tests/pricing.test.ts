import { describe, expect, it } from 'vitest';
import { comparisonCsv, defaultWorkload, estimateCost, historyRows, money, normalizeWorkload, rankOfferings } from '../src/lib/pricing';
import { datasetSchema, isStale, type Offering, type Price } from '../src/lib/data';
import models from '../../data/models.json';
import offerings from '../../data/offerings.json';
import prices from '../../data/latest_prices.json';
import history from '../../data/price_history.json';
import changes from '../../data/changes.json';
import status from '../../data/status.json';

const data = datasetSchema.parse({ models, offerings, prices, history, changes, status });
const offering: Offering = { id: 'a', model_id: 'model', provider: 'provider', provider_model_id: 'model', context_window: 4096, quantization: null, region: 'unspecified', variant: 'standard', service_tier: 'standard', source_url: 'https://example.com', active: true, first_observed_at: '2026-10-03T12:00:00Z', last_seen_at: '2026-10-03T12:00:00Z' };
const price: Price = { offering_id: 'a', input_per_million: 2, output_per_million: 4, cache_read_per_million: 0.5, cache_write_per_million: 5, observed_at: '2026-10-03T12:00:00Z', currency: 'USD', source_url: 'https://example.com', source_sha256: 'test' };

describe('workload estimates', () => {
  it('does not double-count cached input or apply cache-write fees', () => {
    const estimate = estimateCost(offering, price, { inputTokens: 1000, outputTokens: 500, cacheHitPercent: 50, requests: 1_000_000 });
    expect(estimate.perRequest).toBeCloseTo(0.00325);
    expect(estimate.total).toBe(3250);
    expect(estimate.perMillionRequests).toBe(3250);
  });
  it('applies full regular input price when the cache rate is unpublished', () => {
    const estimate = estimateCost(offering, { ...price, cache_read_per_million: null }, { inputTokens: 1000, outputTokens: 500, cacheHitPercent: 100, requests: 1 });
    expect(estimate.perRequest).toBe(0.004);
    expect(estimate.cacheFallback).toBe(true);
  });
  it('respects a published free cache rate instead of falling back', () => {
    const estimate = estimateCost(offering, { ...price, cache_read_per_million: 0 }, { inputTokens: 1000, outputTokens: 0, cacheHitPercent: 100, requests: 1 });
    expect(estimate.perRequest).toBe(0);
    expect(estimate.cacheFallback).toBe(false);
  });
  it('excludes input plus output that exceeds a known context limit', () => {
    expect(estimateCost(offering, price, { ...defaultWorkload, inputTokens: 4000, outputTokens: 500 }).fitsContext).toBe(false);
    expect(estimateCost(offering, price, { ...defaultWorkload, inputTokens: 4000, outputTokens: 96 }).fitsContext).toBe(true);
  });
  it('marks unknown context as unverified', () => {
    expect(estimateCost({ ...offering, context_window: null }, price, defaultWorkload).contextUnverified).toBe(true);
  });
  it('clamps unsafe, negative, nonfinite and over-100% inputs', () => {
    expect(normalizeWorkload({ inputTokens: -1, outputTokens: Infinity, requests: 2e12, cacheHitPercent: 170 })).toEqual({ inputTokens: 0, outputTokens: 0, requests: 1e9, cacheHitPercent: 100 });
  });
  it('zero requests has zero total but keeps per-request ranking', () => {
    const rows = rankOfferings(data, 'openai/gpt-oss-120b', { ...defaultWorkload, requests: 0 });
    expect(rows.every((r) => r.cost.total === 0)).toBe(true);
    expect(rows[0].cost.perRequest).toBeLessThanOrEqual(rows[1].cost.perRequest);
  });
});

describe('the real normalized dataset', () => {
  it('keeps the original open models and only explicitly reviewed offerings', () => {
    expect(data.models.filter((m) => m.open_weight)).toHaveLength(5);
    for (const o of data.offerings) expect(data.models.some((m) => m.id === o.model_id)).toBe(true);
  });
  it('compares standard tiers by default and keeps variants separate', () => {
    const fixture = { ...data, offerings: [offering, { ...offering, id: 'turbo', variant: 'turbo' }, { ...offering, id: 'priority', service_tier: 'priority' as const }], prices: [price, { ...price, offering_id: 'turbo' }, { ...price, offering_id: 'priority' }] };
    const standard = rankOfferings(fixture, 'model', defaultWorkload);
    expect(standard).toHaveLength(2);
    expect(standard.every((r) => r.offering.service_tier === 'standard')).toBe(true);
    expect(rankOfferings(fixture, 'model', defaultWorkload, 'all')).toHaveLength(3);
  });
  it('rejects invalid currency, negative prices and broken references', () => {
    expect(() => datasetSchema.parse({ ...data, prices: [{ ...data.prices[0], currency: 'EUR' }] })).toThrow();
    expect(() => datasetSchema.parse({ ...data, prices: [{ ...data.prices[0], input_per_million: -1 }] })).toThrow();
    expect(() => datasetSchema.parse({ ...data, prices: [{ ...data.prices[0], offering_id: 'missing' }] })).toThrow();
  });
  it('rejects an executable source URL', () => {
    expect(() => datasetSchema.parse({ ...data, prices: [{ ...data.prices[0], source_url: 'javascript:alert(1)' }] })).toThrow();
  });
});

describe('history and exports', () => {
  it('does not round a tiny positive estimate to a misleading zero', () => {
    expect(money(0.0000079)).toBe('$0.0000079');
    expect(money(0)).toBe('$0.00');
  });
  it('keeps missing cache prices null, not zero', () => {
    const rows = historyRows([{ ...price, cache_read_per_million: null }], [offering], 'cache_read_per_million', 0);
    expect(rows[0].a).toBeNull();
  });
  it('sorts history and applies the chosen date range', () => {
    const rows = historyRows([price, { ...price, observed_at: '2026-09-01T12:00:00Z' }], [offering], 'input_per_million', 7, Date.parse('2026-10-04T12:00:00Z'));
    expect(rows).toHaveLength(1);
    expect(rows[0].a).toBe(2);
  });
  it('exports provenance and neutralizes spreadsheet formulas', () => {
    const rows = [{ offering: { ...offering, provider_model_id: '=HYPERLINK("evil")' }, price, cost: estimateCost(offering, price, defaultWorkload) }];
    const csv = comparisonCsv(rows);
    expect(csv).toContain('observed_at,source_url');
    expect(csv).toContain("'=HYPERLINK");
    expect(csv).toContain('https://example.com');
  });
  it('treats observations older than 48 hours as stale', () => {
    expect(isStale('2026-10-01T00:00:00Z', Date.parse('2026-10-03T01:00:00Z'))).toBe(true);
    expect(isStale('2026-10-03T00:00:00Z', Date.parse('2026-10-03T01:00:00Z'))).toBe(false);
    expect(isStale(null)).toBe(true);
  });
});
