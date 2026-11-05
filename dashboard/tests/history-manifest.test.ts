import { describe, expect, it } from 'vitest';
import { historyManifestSchema, serializeHistoryManifest } from '../src/lib/catalog';

function fixture(count = 500) {
  return { schema_version: 2 as const, event_count: count, batches: Array.from({ length: count }, (_, i) => {
    const provider = `provider-${i}`, observed_at = '2026-11-05T17:47:57Z', category = 'catalog' as const;
    const sha256 = i.toString(16).padStart(64, '0');
    return { id: `${provider}:${observed_at}:${category}`, provider, observed_at, category, event_count: 1,
      chunks: [{ path: `catalog/chunks/${sha256}.json`, sha256, count: 1, bytes: 321 }] };
  }) };
}

describe('lossless native history manifest delivery', () => {
  it('fits growing batch metadata within the existing budget without dropping or changing any reference', () => {
    const original = fixture();
    expect(Buffer.byteLength(JSON.stringify(original))).toBeGreaterThan(128 * 1024);
    const wire = serializeHistoryManifest(original);
    expect(Buffer.byteLength(wire)).toBeLessThanOrEqual(128 * 1024);
    expect(JSON.parse(wire).schema_version).toBe(3);
    expect(historyManifestSchema.parse(JSON.parse(wire))).toEqual(original);
    expect(serializeHistoryManifest(JSON.parse(wire))).toBe(wire);
  });
  it('keeps legacy inline histories and empty results readable', () => {
    const original = fixture(2);
    expect(historyManifestSchema.parse(original)).toEqual(original);
    const empty = fixture(0);
    expect(historyManifestSchema.parse(JSON.parse(serializeHistoryManifest(empty)))).toEqual(empty);
    expect(JSON.parse(serializeHistoryManifest(empty)).schema_version).toBe(2);
  });
  it('preserves arbitrary batch IDs and exact Unicode strings instead of inventing identities', () => {
    const original = fixture(2);
    original.batches[0].id = 'original:模型:explicit-id';
    original.batches[0].provider = '原始供應商';
    expect(historyManifestSchema.parse(JSON.parse(serializeHistoryManifest(original)))).toEqual(original);
  });
  it('fails closed on malformed tuples, incomplete counts and invalid chunk references', () => {
    const wire = JSON.parse(serializeHistoryManifest(fixture(2)));
    const corruptions = [
      (m: any) => { m.schema_version = 4; },
      (m: any) => { m.batch_encoding = 'unknown'; },
      (m: any) => { m.event_count++; },
      (m: any) => { m.batches.pop(); },
      (m: any) => { m.batches[0].push('extra'); },
      (m: any) => { m.batches[0][0] = 123; },
      (m: any) => { m.batches[0][2] = 'not-a-timestamp'; },
      (m: any) => { m.batches[0][4]++; },
      (m: any) => { m.batches[0][5][0][0] = '../untrusted'; },
      (m: any) => { m.batches[0][5][0][1] = 0; },
      (m: any) => { m.batches[0][5][0][2] = 512 * 1024 + 1; },
      (m: any) => { m.batches[0][5][0].push('extra'); },
    ];
    for (const change of corruptions) {
      const altered = structuredClone(wire); change(altered);
      expect(() => historyManifestSchema.parse(altered)).toThrow();
    }
  });
});
