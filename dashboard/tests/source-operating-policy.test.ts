import { describe, expect, it } from 'vitest';
import { collectionDisabled, comparisonsPaused, datasetSchema, providerPolicies } from '../src/lib/data';
import { comparisonCsv, defaultWorkload, rankOfferings } from '../src/lib/pricing';
import { comparisonProviders, workloadPriceMap } from '../src/lib/insights';
import models from '../../data/models.json';
import offerings from '../../data/offerings.json';
import prices from '../../data/latest_prices.json';
import history from '../../data/price_history.json';
import changes from '../../data/changes.json';
import status from '../../data/status.json';

const data = datasetSchema.parse({ models, offerings, prices, history, changes, status });

describe('bounded source operating policies', () => {
  it('pauses the exact Vercel Nano and Mercury IDs, preserving other sources and models', () => {
    const excluded = ['nvidia/nemotron-3-nano-30b-a3b', 'inception/mercury-2', 'inception/mercury-2.5'];
    expect(providerPolicies.vercel).toMatchObject({ excluded_model_ids: excluded });
    for (const id of excluded) {
      expect(comparisonsPaused('vercel', id)).toBe(true);
      expect(comparisonsPaused('vercel')).toBe(false);
      expect(collectionDisabled('vercel')).toBe(false);
      expect(comparisonsPaused('vercel', `${id}-other`)).toBe(false);
      expect(comparisonsPaused('openrouter', id)).toBe(false);
      const rows = rankOfferings(data, id, defaultWorkload, 'all');
      expect(rows.some((r) => r.offering.provider === 'vercel')).toBe(false);
      const otherSource = id.startsWith('inception/') ? 'openrouter' : 'deepinfra';
      // OpenRouter's retained Mercury offers can be inactive independently.
      // Use synthetic availability to verify this Vercel policy does not suppress another source.
      const available = { ...data, offerings: data.offerings.map((o) =>
        o.model_id === id && o.provider === otherSource ? { ...o, active: true } : o) };
      expect(rankOfferings(available, id, defaultWorkload, 'all').some((r) => r.offering.provider === otherSource)).toBe(true);
      expect(comparisonCsv(rows)).not.toContain('Vercel AI Gateway');
      expect(comparisonProviders(data, new Set([id]))).not.toContain('vercel');
      expect(workloadPriceMap(data, defaultWorkload, 'all', 'all', '').find((r) => r.model.id === id)?.cells.has('vercel')).toBe(false);
    }
    expect(rankOfferings(data, 'inception/mercury-3', defaultWorkload).some((r) => r.offering.provider === 'vercel')).toBe(true);
    expect(rankOfferings(data, 'nvidia/nemotron-3.5-lightning', defaultWorkload).some((r) => r.offering.provider === 'vercel')).toBe(true);
  });

  it('pauses Castform and only the exact Arcee served IDs, independently of health or availability', () => {
    expect(collectionDisabled('castform')).toBe(true);
    expect(collectionDisabled('together')).toBe(false);
    expect(comparisonsPaused('castform')).toBe(true);
    expect(comparisonsPaused('arcee')).toBe(false);
    for (const id of ['deepseek/deepseek-v4-pro-0813', 'zai-org/glm-5.2']) {
      expect(comparisonsPaused('arcee', id)).toBe(true);
      expect(comparisonsPaused('arcee', `${id}-other`)).toBe(false);
      expect(comparisonsPaused('another-source', id)).toBe(false);
    }
    expect(comparisonsPaused('arcee', 'zai-org/glm-5.3-flash')).toBe(false);
    expect(rankOfferings(data, 'zai/glm-5.3-flash', defaultWorkload).some((r) => r.offering.provider === 'arcee')).toBe(true);
  });

  it('excludes stopped quotes from current rankings, workload winners, provider columns and comparison CSV', () => {
    const before = JSON.stringify(data);
    for (const model of data.models) {
      const rows = rankOfferings(data, model.id, defaultWorkload, 'all');
      expect(rows.every((r) => !comparisonsPaused(r.offering.provider, r.offering.provider_model_id))).toBe(true);
      expect(comparisonCsv(rows)).not.toContain('castform');
      for (const row of rows) {
        if (row.offering.provider === 'arcee') expect(['zai-org/glm-5.2', 'deepseek/deepseek-v4-pro-0813']).not.toContain(row.offering.provider_model_id);
      }
    }
    expect(comparisonProviders(data)).not.toContain('castform');
    expect(comparisonProviders(data, new Set(['zai/glm-5.2']))).not.toContain('arcee');
    for (const row of workloadPriceMap(data, defaultWorkload, 'all', 'all', '')) {
      expect(row.cells.has('castform')).toBe(false);
      if (['zai/glm-5.2', 'deepseek/deepseek-v4-pro-0813'].includes(row.model.id)) expect(row.cells.has('arcee')).toBe(false);
    }
    expect(JSON.stringify(data)).toBe(before);
  });

  it('retains original prices, availability, history and explicit export policy', () => {
    const excluded = data.offerings.filter((o) => comparisonsPaused(o.provider, o.provider_model_id));
    expect(excluded.filter((o) => o.provider === 'castform')).toHaveLength(11);
    expect(excluded.filter((o) => o.provider === 'arcee')).toHaveLength(2);
    expect(excluded.filter((o) => o.provider === 'vercel')).toHaveLength(3);
    for (const offering of excluded) {
      expect(data.prices.some((p) => p.offering_id === offering.id)).toBe(true);
      expect(data.history.some((p) => p.offering_id === offering.id)).toBe(true);
    }
    const exported = JSON.parse(JSON.stringify({ ...data, provider_policies: providerPolicies }));
    expect(exported.provider_policies.castform.collection).toBe('disabled');
    expect(exported.provider_policies.arcee.excluded_model_ids).toEqual(['deepseek/deepseek-v4-pro-0813', 'zai-org/glm-5.2']);
    expect(exported.offerings).toEqual(offerings);
    expect(exported.prices).toEqual(prices);
    expect(exported.history).toEqual(history);
  });
});
