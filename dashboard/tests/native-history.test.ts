import { afterEach, describe, expect, it } from 'vitest';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { isDeepStrictEqual } from 'node:util';
import { fileURLToPath } from 'node:url';
import { gunzipSync } from 'node:zlib';
import { buildDashboardAssets } from '../../scripts/dashboard_projection';
import { historyVersionPath, readNativeHistory } from '../../scripts/native_history';
import { projectedEvents } from './projected-assets';

const root = fileURLToPath(new URL('../..', import.meta.url));
const first = '2026-10-10T07:00:00Z', second = '2026-10-11T07:00:00Z', third = '2026-10-12T07:00:00Z';
const a = 'a'.repeat(64), b = 'b'.repeat(64), c = 'c'.repeat(64);
const source = 'https://cloudbilling.googleapis.com/v1/services/FIXTURE/skus?currencyCode=USD&pageSize=500';
const paths: string[] = [];
afterEach(() => { for (const path of paths.splice(0)) rmSync(path, { recursive: true, force: true }); });
const raw = (time = first, amount = '0.1') => ({
  id: 'vertex-record', provider: 'vertex', native_id: 'services/FIXTURE/skus/1', kind: 'sku', label: 'Fixture SKU — é',
  scope: { service: 'services/FIXTURE', regions: ['us-east1'] }, metadata: {}, comparison_eligible: false,
  billing: { pricing_info: [{ effectiveTime: time, pricingExpression: { usageUnit: 'token', tieredRates: [] } }] },
  rates: [{ dimension: 'tier', amount, currency: 'USD', unit: 'token', conditions: { effective_time: time } }],
});
function fixture() {
  const path = mkdtempSync(join(tmpdir(), 'token3-history-compaction-')); paths.push(path);
  mkdirSync(join(path, 'provider_catalogs'));
  const write = (file: string, value: unknown) => writeFileSync(join(path, file), JSON.stringify(value));
  const records = [raw(third, '0.2')];
  const provider = { id: 'vertex', name: 'Vertex', source_url: source, source_urls: [source], source_kind: 'api', record_count: 1,
    revision: 3, catalog_sha256: c, source_sha256: c, first_seen_at: first, last_seen_at: third, changed_at: third,
    latest_path: 'provider_catalogs/vertex.json' };
  write('provider_inventory.json', { updated_at: third, providers: [provider] });
  write('provider_catalogs/vertex.json', { ...provider, provider: 'vertex', records, billing_notes: [] });
  write('offerings.json', []); write('changes.json', []);
  const events = [
    { id: 'first', provider: 'vertex', revision: 1, observed_at: first, catalog_sha256: a, kind: 'record_added', record_id: 'vertex-record', after: raw() },
    { id: 'observation', provider: 'vertex', revision: 2, observed_at: second, catalog_sha256: b, kind: 'record_changed', record_id: 'vertex-record', after: raw(second) },
    { id: 'rate-change', provider: 'vertex', revision: 3, observed_at: third, catalog_sha256: c, kind: 'record_changed', record_id: 'vertex-record', after: raw(third, '0.2') },
  ];
  writeFileSync(join(path, 'inventory_history.jsonl'), events.map((e) => JSON.stringify(e)).join('\n') + '\n');
  return { path, events, write };
}
function migrate(path: string) {
  // Exercise the actual Python writer against the TypeScript reader, including
  // exact UTF-8 gzip/hash/row references. No provider or inference call occurs.
  execFileSync('python3', ['-c', `
import sys
from scripts.native_history import compact_history
p={k:dict(catalog_sha256=k,source_kind='api',source_urls=[${JSON.stringify(source)}]) for k in ['a'*64,'b'*64,'c'*64]}
compact_history(sys.argv[1],p,apply=True,limit=2048)
`, path], { cwd: root, stdio: 'pipe' });
}

describe('warehouse history compaction', () => {
  it('Python and TypeScript reconstruct the exact original event values and identities', () => {
    const { path, events } = fixture(); migrate(path);
    const entries = [...readNativeHistory(path)];
    expect(entries.map((e) => e.event)).toEqual(events);
    expect(entries.map((e) => e.observationOnly)).toEqual([false, true, false]);
    expect(historyVersionPath(path)).toBe('inventory_history/manifest.json');
  });
  it('projection removes only verified observation events, keeps later source provenance and actual changes unchanged', () => {
    const { path } = fixture();
    const before = buildDashboardAssets(path), old = projectedEvents(before, 'catalog/changes/rule.json').events;
    expect(old.some((e) => e.id.includes('observation'))).toBe(true);
    migrate(path);
    const after = buildDashboardAssets(path);
    expect(projectedEvents(after, 'catalog/changes/rule.json').events).toEqual(old.filter((e) => !e.id.includes('observation')));
    expect(after.get('catalog/providers/vertex.json')).toBe(before.get('catalog/providers/vertex.json'));
    expect([...after.keys()].every((p) => !p.includes('archive') && !p.includes('proofs') && !p.includes('inventory_history'))).toBe(true);
  });
  it('unmarked legacy events are still conservatively classified without a migration', () => {
    const { path } = fixture();
    expect([...readNativeHistory(path)].every((e) => !e.observationOnly)).toBe(true);
    expect(projectedEvents(buildDashboardAssets(path), 'catalog/changes/rule.json').events.some((e) => e.id.includes('observation'))).toBe(true);
    expect(historyVersionPath(path)).toBe('inventory_history.jsonl');
  });
  it('missing or corrupt assets and incomplete manifests are explicit errors', () => {
    const { path, write } = fixture(); migrate(path);
    const manifest = JSON.parse(readFileSync(join(path, 'inventory_history/manifest.json'), 'utf8'));
    const ref = manifest.segments[0];
    const file = join(path, ref.path), original = readFileSync(file);
    writeFileSync(file, original.subarray(0, original.length - 1));
    expect(() => [...readNativeHistory(path)]).toThrow();
    writeFileSync(file, original);
    manifest.event_count++;
    write('inventory_history/manifest.json', manifest);
    expect(() => buildDashboardAssets(path)).toThrow(/Incomplete history manifest/);
  });
  it('rejects proof corruption and unsafe paths rather than trusting observation flags', () => {
    const { path, write } = fixture(); migrate(path);
    const manifest = JSON.parse(readFileSync(join(path, 'inventory_history/manifest.json'), 'utf8'));
    const proof = join(path, manifest.proofs.path); writeFileSync(proof, readFileSync(proof).toString() + ' ');
    expect(() => [...readNativeHistory(path)]).toThrow();
    manifest.segments[0].path = '../outside.gz'; write('inventory_history/manifest.json', manifest);
    expect(() => [...readNativeHistory(path)]).toThrow();
  });
  it('the real migrated dataset reconstructs every archived observation and remains bounded', () => {
    const data = join(root, 'data');
    const manifest = JSON.parse(readFileSync(join(data, 'inventory_history/manifest.json'), 'utf8'));
    const entries = readNativeHistory(data); let originalCount = 0, observed = 0;
    for (const ref of manifest.archive.segments) {
      expect(ref.uncompressed_bytes).toBeLessThanOrEqual(16 * 1024 * 1024);
      const original = gunzipSync(readFileSync(join(data, ref.path)), { maxOutputLength: 16 * 1024 * 1024 + 1 }).toString('utf8');
      for (const line of original.split('\n')) {
        if (!line.trim()) continue;
        const expanded = entries.next();
        if (expanded.done || !isDeepStrictEqual(expanded.value.event, JSON.parse(line))) throw new Error('Real migration changed an original event');
        originalCount++; observed += Number(expanded.value.observationOnly);
      }
    }
    for (const _ of entries) { /* validate legitimately appended events too */ }
    expect(originalCount).toBe(manifest.archive.event_count);
    expect(observed).toBe(manifest.migration.observation_count);
    expect(manifest.segments.every((r: { uncompressed_bytes: number }) => r.uncompressed_bytes <= 16 * 1024 * 1024)).toBe(true);
  }, 60000);
});
