import { describe, expect, it } from 'vitest';
import { datasetSchema, type Offering, type Price } from '../src/lib/data';
import { comparisonCsv, defaultWorkload, eligibilityReason, estimateCost, inputBandLabel, rankOfferings } from '../src/lib/pricing';
import models from '../../data/models.json';
import offerings from '../../data/offerings.json';
import prices from '../../data/latest_prices.json';
import history from '../../data/price_history.json';
import changes from '../../data/changes.json';
import status from '../../data/status.json';

const data = datasetSchema.parse({ models, offerings, prices, history, changes, status });
const base: Offering = { id: 'short', model_id: 'model', provider: 'openai', provider_model_id: 'gpt-5.4-2026-03-05', context_window: 1050000, quantization: null, region: 'global', variant: 'short prompt', service_tier: 'standard', source_url: 'https://example.com', active: true, first_observed_at: '2026-10-03T12:00:00Z', last_seen_at: '2026-10-03T12:00:00Z', min_input_tokens: 0, max_input_tokens: 272000, max_output_tokens: 128000 };
const quote: Price = { offering_id: 'short', input_per_million: 2.5, output_per_million: 15, cache_read_per_million: 0.25, cache_write_per_million: null, observed_at: '2026-10-03T12:00:00Z', currency: 'USD', source_url: 'https://example.com', source_sha256: 'test' };
const long: Offering = { ...base, id: 'long', min_input_tokens: 272001, max_input_tokens: null, variant: 'long prompt' };
const longQuote: Price = { ...quote, offering_id: 'long', input_per_million: 5, output_per_million: 22.5, cache_read_per_million: 0.5 };
const fixture = { ...data, offerings: [base, long], prices: [quote, longQuote] };

describe('cloud and proprietary pricing rules', () => {
  it('uses the inclusive short-prompt boundary and excludes its rate above it', () => {
    expect(estimateCost(base, quote, { ...defaultWorkload, inputTokens: 272000 }).eligible).toBe(true);
    expect(estimateCost(base, quote, { ...defaultWorkload, inputTokens: 272001 }).eligible).toBe(false);
    expect(estimateCost(long, longQuote, { ...defaultWorkload, inputTokens: 272000 }).eligible).toBe(false);
    expect(estimateCost(long, longQuote, { ...defaultWorkload, inputTokens: 272001 }).eligible).toBe(true);
  });
  it('counts cached input toward the prompt band, not just uncached input', () => {
    const workload = { ...defaultWorkload, inputTokens: 300000, cacheHitPercent: 100, requests: 1 };
    const ranked = rankOfferings(fixture, 'model', workload);
    expect(ranked[0].offering.id).toBe('long');
    expect(ranked[0].cost.perRequest).toBeCloseTo(0.159);
    expect(ranked[1].cost.eligible).toBe(false);
    expect(eligibilityReason(ranked[1].cost)).toBe('Outside prompt band');
  });
  it('enforces output caps independently of the total context', () => {
    const cost = estimateCost(base, quote, { ...defaultWorkload, outputTokens: 128001 });
    expect(cost.fitsContext).toBe(true);
    expect(cost.fitsOutputLimit).toBe(false);
    expect(cost.eligible).toBe(false);
    expect(eligibilityReason(cost)).toBe('Exceeds output limit');
  });
  it('does not mistake Gemini input and output limits for a combined window', () => {
    const google = { ...base, context_window: null, min_input_tokens: 0, max_input_tokens: 1048576, max_output_tokens: 65536 };
    const cost = estimateCost(google, quote, { ...defaultWorkload, inputTokens: 1048576, outputTokens: 65536 });
    expect(cost.eligible).toBe(true);
    expect(cost.contextUnverified).toBe(true);
    expect(estimateCost(google, quote, { ...defaultWorkload, inputTokens: 1048577 }).eligible).toBe(false);
  });
  it('exports prompt bands and eligibility, not estimates for excluded bands', () => {
    const rows = rankOfferings(fixture, 'model', { ...defaultWorkload, inputTokens: 300000 });
    const csv = comparisonCsv(rows);
    expect(csv).toContain('min_input_tokens,max_input_tokens,max_output_tokens,fits_input_range,fits_output_limit,eligible,pricing_notes');
    expect(inputBandLabel(base)).toBe('Prompt ≤272K');
    expect(inputBandLabel(long)).toBe('Prompt >272K');
    const columns = csv.split('\n')[0].split(',');
    const shortRow = csv.split('\n')[2].split(',');
    expect(shortRow[columns.indexOf('estimated_workload_usd')]).toBe('');
    expect(shortRow[columns.indexOf('eligible')]).toBe('false');
  });
  it('rejects inverted and invalid token bands in the browser schema', () => {
    expect(() => datasetSchema.parse({ ...data, offerings: [{ ...data.offerings[0], min_input_tokens: 300, max_input_tokens: 200 }] })).toThrow();
    expect(() => datasetSchema.parse({ ...data, offerings: [{ ...data.offerings[0], max_output_tokens: -1 }] })).toThrow();
  });
  it('includes proprietary creators and native, GCP, AWS, and Azure comparisons', () => {
    for (const creator of ['OpenAI', 'Anthropic', 'Google']) expect(data.models.some((m) => m.creator === creator && !m.open_weight)).toBe(true);
    for (const provider of ['openai', 'anthropic', 'gemini', 'vertex', 'bedrock', 'azure']) expect(data.status.providers.find((p) => p.id === provider)?.state).toBe('ok');
    expect(new Set(rankOfferings(data, 'anthropic/claude-sonnet-4.6', defaultWorkload).map((r) => r.offering.provider))).toEqual(new Set(['anthropic', 'vertex', 'bedrock']));
    expect(new Set(rankOfferings(data, 'openai/gpt-5.4', defaultWorkload).map((r) => r.offering.provider))).toEqual(new Set(['openai', 'azure']));
  });
});
