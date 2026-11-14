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
