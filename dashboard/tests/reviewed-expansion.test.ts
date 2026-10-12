import { describe, expect, it } from 'vitest';
import { datasetSchema } from '../src/lib/data';
import { defaultWorkload, estimateCost, rankOfferings } from '../src/lib/pricing';
import models from '../../data/models.json';
import offerings from '../../data/offerings.json';
import prices from '../../data/latest_prices.json';
import history from '../../data/price_history.json';
import changes from '../../data/changes.json';
import status from '../../data/status.json';

const data = datasetSchema.parse({ models, offerings, prices, history, changes, status });
const requested = ['anthropic/claude-opus-5.5', 'anthropic/claude-fable-5', 'anthropic/claude-fable-5.1', 'openai/gpt-6.1-sol', 'openai/gpt-6-luna', 'openai/gpt-6-astra'];

function boundary(model: string, short: number, long: number) {
  for (const inputTokens of [short, long]) {
    const workload = { ...defaultWorkload, inputTokens, outputTokens: 0, requests: 1, cacheHitPercent: 100 };
    const ranked = rankOfferings(data, model, workload);
    const eligible = ranked.filter((r) => r.cost.eligible);
    expect(eligible.length).toBeGreaterThan(0);
    expect(eligible.every((r) => inputTokens >= (r.offering.min_input_tokens ?? 0) &&
      (r.offering.max_input_tokens == null || inputTokens <= r.offering.max_input_tokens))).toBe(true);
    expect(ranked.some((r) => !r.cost.fitsInputRange)).toBe(true);
    expect(ranked[0].cost.eligible).toBe(true);
  }
}

describe('explicit recent-model comparison expansion', () => {
  it('has real reviewed quotes for requested models and every retained canonical identity', () => {
    expect(data.models).toHaveLength(45);
    for (const id of requested) {
      expect(data.models.some((m) => m.id === id)).toBe(true);
      const rows = rankOfferings(data, id, defaultWorkload);
      expect(rows.some((r) => r.cost.eligible)).toBe(true);
      expect(rows.some((r) => r.offering.provider === (id.startsWith('openai/') ? 'openai' : 'anthropic'))).toBe(true);
    }
    for (const model of data.models) expect(data.offerings.some((o) => o.model_id === model.id)).toBe(true);
    expect(data.models.some((m) => m.id === 'openai/gpt-6.1-luna')).toBe(false);
  });
  it('keeps 100K, 200K and 272K whole-prompt boundaries, including fully cached input', () => {
    boundary('anthropic/claude-haiku-5.5', 100000, 100001);
    boundary('google/gemini-3.1-pro-preview', 200000, 200001);
    boundary('openai/gpt-6.1-sol', 272000, 272001);
    const rows = rankOfferings(data, 'anthropic/claude-haiku-5.5', { ...defaultWorkload, inputTokens: 100001, outputTokens: 0, requests: 1, cacheHitPercent: 100 });
    expect(rows[0].cost.perRequest).toBeCloseTo(100001 * 0.05 / 1000000, 10);
  });
  it('keeps gateway identity, quote scope and unknown cache-write TTL explicit', () => {
    const rows = rankOfferings(data, 'openai/gpt-6.1-sol', defaultWorkload, 'all');
    expect(new Set(rows.map((r) => r.offering.provider))).toEqual(new Set(['openai', 'vercel']));
    const gateway = rows.filter((r) => r.offering.provider === 'vercel');
    expect(new Set(gateway.map((r) => r.offering.service_tier))).toEqual(new Set(['standard', 'priority', 'flex']));
    expect(gateway.every((r) => r.offering.region === 'default gateway route' &&
      r.offering.pricing_notes?.includes('not a direct upstream-provider quote') &&
      r.offering.pricing_notes.includes('Cache-write TTL is not established'))).toBe(true);
    const standard = gateway.find((r) => r.offering.service_tier === 'standard' && !r.offering.min_input_tokens)!;
    expect(standard.price.input_per_million).toBe(2);
    expect(standard.price.output_per_million).toBe(10);
    expect(estimateCost(standard.offering, { ...standard.price, cache_write_per_million: 100000 }, defaultWorkload))
      .toEqual(estimateCost(standard.offering, standard.price, defaultWorkload));
  });
  it('does not invent cloud, direct-creator, dynamic-route or unsupported tiered quotes', () => {
    for (const provider of ['azure', 'bedrock', 'vertex'])
      expect(data.offerings.some((o) => o.model_id === 'openai/gpt-6-astra' && o.provider === provider)).toBe(false);
    expect(data.offerings.some((o) => o.provider === 'openrouter')).toBe(false);
    expect(data.offerings.some((o) => o.provider === 'novita' && o.model_id === 'minimax/minimax-m3')).toBe(false);
    expect(new Set(data.offerings.filter((o) => o.model_id === 'xai/grok-4.7').map((o) => o.provider))).toEqual(new Set(['vercel']));
    expect(data.models.find((m) => m.id === 'anthropic/claude-mythos-5.1')?.description).toContain('Limited availability');
  });
});
