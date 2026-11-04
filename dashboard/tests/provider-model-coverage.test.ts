import { describe, expect, it } from 'vitest';
import { datasetSchema, weightLabel, providerInfo } from '../src/lib/data';
import { accessKind } from '../src/lib/catalog';
import { comparisonCsv, defaultWorkload, eligibilityReason, estimateCost, historyRows, isBestCost, rankOfferings } from '../src/lib/pricing';
import models from '../../data/models.json';
import offerings from '../../data/offerings.json';
import prices from '../../data/latest_prices.json';
import history from '../../data/price_history.json';
import changes from '../../data/changes.json';
import status from '../../data/status.json';
import inventory from '../../data/provider_inventory.json';
import review from '../../tests/fixtures/provider-model-expansion/review.json';

const data = datasetSchema.parse({ models, offerings, prices, history, changes, status });

describe('current provider and model coverage', () => {
  it('preserves the retained baseline and binds every new selection to its reviewed billing source', () => {
    expect(data.models).toHaveLength(169);
    expect(data.offerings).toHaveLength(447);
    expect(new Set(data.offerings.map((o) => o.provider)).size).toBe(34);
    expect(inventory.providers).toHaveLength(47);
    for (const id of review.new_model_ids) {
      expect(data.models.some((m) => m.id === id)).toBe(true);
      expect(rankOfferings(data, id, defaultWorkload).some((r) => r.cost.eligible)).toBe(true);
    }
    for (const [provider, bindings] of Object.entries(review.reviewed_bindings)) {
      for (const [sourceId, canonical] of Object.entries(bindings)) {
        expect(data.offerings.some((o) => o.provider === provider && o.provider_model_id === sourceId && o.model_id === canonical)).toBe(true);
      }
    }
  });
  it('keeps unknown weight access distinct from proprietary and open models', () => {
    for (const id of review.new_model_ids) {
      const model = data.models.find((m) => m.id === id)!;
      expect(model.open_weight).toBeNull();
      expect(weightLabel(model)).toBe('Weights unverified');
    }
    expect(weightLabel(data.models.find((m) => m.id === 'openai/gpt-oss-120b')!)).toBe('Open weights');
    expect(weightLabel(data.models.find((m) => m.id === 'openai/gpt-6-astra')!)).toBe('Proprietary');
  });
  it('keeps document-only models, training and media outside comparable token quotes', () => {
    const nativeOnly = ['cohere', 'ai21', 'stepfun', 'telnyx', 'typesafe', 'blackforestlabs', 'runway', 'stability', 'ideogram', 'elevenlabs', 'byteplus', 'adobe', 'baidu'];
    for (const provider of nativeOnly) {
      expect(inventory.providers.some((p) => p.id === provider)).toBe(true);
      expect(data.offerings.some((o) => o.provider === provider)).toBe(false);
    }
    expect(data.offerings.some((o) => o.provider === 'castform' && ['hy3-rl', 'text-embedding-3-large'].includes(o.provider_model_id))).toBe(false);
    expect(data.offerings.filter((o) => o.provider === 'perplexity').every((o) => o.source_url.includes('/agent-api/'))).toBe(true);
    const cerebras = data.offerings.filter((o) => o.provider === 'cerebras');
    expect(cerebras).toHaveLength(2);
    expect(cerebras.every((o) => o.context_window === null && o.max_output_tokens === null)).toBe(true);
  });
  it('exposes explicit billing-source names and platform access labels', () => {
    for (const provider of ['cerebras', 'castform', 'perplexity', 'arcee', 'upstage']) {
      expect(providerInfo(provider).name).not.toBe(provider);
    }
    expect(accessKind('castform')).toBe('Platform');
    expect(accessKind('perplexity')).toBe('Platform');
    expect(accessKind('cerebras')).toBe('Direct API');
    expect(accessKind('openrouter')).toBe('Gateway');
  });
  it('excludes unreviewed billing conditions from winners and exported estimates', () => {
    const offering = { ...data.offerings[0], pricing_scope_unverified: true, pricing_notes: 'Test scope quarantine' };
    const price = data.prices.find((p) => p.offering_id === offering.id)!;
    const cost = estimateCost(offering, price, defaultWorkload);
    expect(cost.eligible).toBe(false);
    expect(cost.pricingScopeVerified).toBe(false);
    expect(eligibilityReason(cost)).toBe('Pricing scope unverified');
    const row = { offering, price, cost };
    expect(isBestCost(row, row)).toBe(false);
    const csv = comparisonCsv([row]);
    const [header, values] = csv.trim().split('\n').map((line) => line.split(','));
    expect(values[header.indexOf('estimated_workload_usd')]).toBe('');
    expect(values[header.indexOf('pricing_scope_verified')]).toBe('false');
  });
  it('quarantines the retained scheduled gateway base quote in both scenarios', () => {
    for (const period of ['peak', 'off_peak']) {
      const rows = rankOfferings(data, 'deepseek/deepseek-v4-pro-0813', defaultWorkload, 'standard', 'USD', period);
      const scheduled = rows.find((r) => r.offering.provider === 'vercel')!;
      expect(scheduled.offering.pricing_scope_unverified).toBe(true);
      expect(scheduled.price.input_per_million).toBe(.66);
      expect(scheduled.cost.eligible).toBe(false);
      expect(eligibilityReason(scheduled.cost)).toBe('Pricing scope unverified');
      expect(isBestCost(scheduled, rows[0])).toBe(false);
      expect(historyRows(data.history, [scheduled.offering], 'input_per_million', 0)).toEqual([]);
    }
  });
});
