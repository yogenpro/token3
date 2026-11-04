import { describe, expect, it } from 'vitest';
import { historicalProviderDirectory } from '../../scripts/dashboard_projection';
import historicalPublication from '../../config/historical_publication.json';
import inventory from '../../data/provider_inventory.json';

const payload = (ids: string[]): Record<'captures' | 'assertions' | 'checks', Array<{ provider: string }>> =>
  ({ captures: ids.map((provider) => ({ provider })), assertions: [], checks: [] });

describe('independent current and historical source scopes', () => {
  it('keeps the complete authorized historical directory when current collection adds providers', () => {
    const scope = historicalPublication.providers;
    expect(scope).toHaveLength(26);
    expect(scope).toContain('bedrock'); // Dedicated historical adapter, outside document profiles.
    const result = historicalProviderDirectory(inventory.providers, scope, payload(scope));
    expect(result.map((p) => p.id)).toEqual(scope);
    for (const id of ['meta', 'mistral', 'moonshot']) {
      expect(inventory.providers.some((p) => p.id === id)).toBe(true);
      expect(result.some((p) => p.id === id)).toBe(false);
    }
  });
  it('still fails closed if any configured historical provider lacks a public capture or directory entry', () => {
    const directory = [{ id: 'known' }, { id: 'missing' }, { id: 'current-only' }];
    expect(() => historicalProviderDirectory(directory, ['known', 'missing'], payload(['known'])))
      .toThrow('no retained public capture');
    expect(() => historicalProviderDirectory(directory.slice(0, 1), ['known', 'missing'], payload(['known', 'missing'])))
      .toThrow('not in the published source directory');
    expect(() => historicalProviderDirectory(directory, ['known', 'known'], payload(['known']))).toThrow('Invalid historical provider scope');
  });
  it('rejects captures, assertions or lookup checks outside the authorized historical scope', () => {
    for (const kind of ['captures', 'assertions', 'checks'] as const) {
      const value = payload(['known']);
      value[kind] = [...value[kind], { provider: 'current-only' }];
      expect(() => historicalProviderDirectory([{ id: 'known' }, { id: 'current-only' }], ['known'], value))
        .toThrow('outside the configured source scope');
    }
  });
});
