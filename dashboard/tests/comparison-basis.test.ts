import { describe, expect, it } from 'vitest';
import { datasetSchema, type Dataset, type Offering, type Price } from '../src/lib/data';
import { comparisonCsv, defaultWorkload, money, quoteUnit, rankOfferings } from '../src/lib/pricing';
import { comparisonProviders, workloadPriceMap } from '../src/lib/insights';

const base: Offering = { id: 'usd', model_id: 'model', provider: 'openrouter', provider_model_id: 'source', context_window: null, quantization: null, service_tier: 'standard', region: 'route', variant: 'standard', source_url: 'https://example.com', active: true, first_observed_at: '2026-10-26T00:00:00Z', last_seen_at: '2026-10-26T00:00:00Z' };
const price: Price = { offering_id: 'usd', observed_at: base.first_observed_at, input_per_million: 2, output_per_million: 4, cache_read_per_million: null, cache_write_per_million: null, currency: 'USD', source_url: base.source_url, source_sha256: 'a'.repeat(64) };
const data: Dataset = { models: [{ id: 'model', creator: 'Creator', name: 'Model', version: '1', family: 'Family', open_weight: true, description: 'Test model' }], offerings: [base, { ...base, id: 'eur', quote_unit: 'EUR', provider: 'scaleway' }, { ...base, id: 'dbu', quote_unit: 'DBU', provider: 'databricks' }, { ...base, id: 'credit', quote_unit: 'AI_CREDIT', provider: 'snowflake' }], prices: [price, { ...price, offering_id: 'eur', currency: 'EUR', input_per_million: 0.1 }, { ...price, offering_id: 'dbu', currency: null, input_per_million: 0.01 }, { ...price, offering_id: 'credit', currency: null, input_per_million: 0.001 }], history: [], changes: [], status: { schema_version: 1, last_run_at: base.first_observed_at, first_observed_at: null, observation_count: 0, providers: [] } };

describe('reviewed billing bases', () => {
  it('validates explicit currencies and native units without calling credits currency', () => {
    expect(datasetSchema.parse(data)).toBeTruthy();
    expect(() => datasetSchema.parse({ ...data, prices: data.prices.map((p) => p.offering_id === 'dbu' ? { ...p, currency: 'USD' } : p) })).toThrow();
    expect(() => datasetSchema.parse({ ...data, prices: data.prices.map((p) => p.offering_id === 'eur' ? { ...p, currency: 'USD' } : p) })).toThrow();
    expect(quoteUnit(base)).toBe('USD');
  });
  it('never ranks EUR, DBU or AI Credits against USD', () => {
    expect(rankOfferings(data, 'model', defaultWorkload).map((r) => r.offering.id)).toEqual(['usd']);
    for (const [unit, id] of [['EUR', 'eur'], ['DBU', 'dbu'], ['AI_CREDIT', 'credit']] as const) {
      expect(rankOfferings(data, 'model', defaultWorkload, 'standard', unit).map((r) => r.offering.id)).toEqual([id]);
      const map = workloadPriceMap(data, defaultWorkload, 'standard', 'all', '', unit);
      expect([...map[0].cells.values()].flat().map((r) => r.offering.id)).toEqual([id]);
      expect(comparisonProviders(data, undefined, unit)).toEqual([data.offerings.find((o) => o.id === id)!.provider]);
    }
  });
  it('formats and exports the real billing basis and refuses mixed-unit exports', () => {
    expect(money(1, false, 'EUR')).toBe('€1.00');
    expect(money(1, false, 'DBU')).toBe('1.00 DBU');
    expect(money(1, false, 'AI_CREDIT')).toBe('1.00 AI Credits');
    const eur = rankOfferings(data, 'model', defaultWorkload, 'standard', 'EUR');
    expect(comparisonCsv(eur)).toContain('input_eur_per_million');
    expect(comparisonCsv(eur)).toContain(',EUR\n');
    expect(comparisonCsv(eur)).not.toContain('estimated_workload_usd');
    expect(() => comparisonCsv([...rankOfferings(data, 'model', defaultWorkload), ...eur])).toThrow();
  });
  it('uses only an explicitly selected DeepSeek time-of-use scenario', () => {
    const scenarios: Dataset = { ...data, offerings: ['peak', 'off-peak'].map((variant) => ({ ...base, id: variant, provider: 'deepseek', variant, region: variant })), prices: [{ ...price, offering_id: 'peak' }, { ...price, offering_id: 'off-peak', input_per_million: 0.1 }] };
    expect(rankOfferings(scenarios, 'model', defaultWorkload).map((r) => r.offering.variant)).toEqual(['peak']);
    expect(rankOfferings(scenarios, 'model', defaultWorkload, 'standard', 'USD', 'off-peak').map((r) => r.offering.variant)).toEqual(['off-peak']);
  });
});
