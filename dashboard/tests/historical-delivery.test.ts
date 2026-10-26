import { beforeAll, describe, expect, it } from 'vitest';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildHistoricalAssets } from '../../scripts/dashboard_projection';
import { historicalEvidenceChunkSchema, historicalIndexChunkSchema, historicalIndexSchema, historicalManifestSchema,
  matchingEvidence, validateHistoricalIndex } from '../src/lib/historical';
import { MAX_CATALOG_CHUNK_BYTES } from '../src/lib/catalog';

const dataDir = fileURLToPath(new URL('../../data', import.meta.url));
const warehouse = join(dataDir, 'historical_evidence');
const fingerprint = () => Object.fromEntries(['manifest.json', ...['sources', 'segments'].flatMap((dir) => readdirSync(join(warehouse, dir)).map((p) => `${dir}/${p}`))]
  .map((p) => [p, createHash('sha256').update(readFileSync(join(warehouse, p))).digest('hex')]));
let assets: Map<string, string>, before: ReturnType<typeof fingerprint>;
beforeAll(() => { before = fingerprint(); assets = buildHistoricalAssets(dataDir); }, 120000);

describe('read-only public historical evidence', () => {
  it('preserves every warehouse byte while publishing only selected JSON assets', () => {
    expect(fingerprint()).toEqual(before);
    expect([...assets.keys()].every((p) => /^catalog\/(historical\/[a-z0-9_-]+|chunks\/[a-f0-9]{64})\.json$/.test(p))).toBe(true);
    expect([...assets.values()].some((s) => /"(?:raw|body_path|previous_attempts|collector_only|reviewed_model_ids)"\s*:/.test(s))).toBe(false);
  });
  it('keeps the overview small and counts assertions separately from captures and lookup checks', () => {
    const text = assets.get('catalog/historical/index.json')!;
    const index = historicalIndexSchema.parse(JSON.parse(text));
    const original = JSON.parse(readFileSync(join(warehouse, 'manifest.json'), 'utf8'));
    expect(index.providers.length).toBe(26);
    expect(index.capture_count).toBe(original.counts.capture);
    expect(index.assertion_count).toBe(original.counts.assertion);
    expect(text.length).toBeLessThan(30000);
    expect(text).not.toContain('source_pointer'); expect(text).not.toContain('evidence_chunks');
  });
  it('binds every complete provider index to exact evidence and bounded immutable chunks', () => {
    const index = historicalIndexSchema.parse(JSON.parse(assets.get('catalog/historical/index.json')!));
    let total = 0;
    for (const p of index.providers) {
      const manifest = historicalManifestSchema.parse(JSON.parse(assets.get(p.detail_path)!));
      const rows = manifest.index_chunks.flatMap((c) => historicalIndexChunkSchema.parse(JSON.parse(assets.get(c.path)!)).records);
      expect(validateHistoricalIndex(rows, manifest)).toBe(true);
      expect(manifest.snapshot_sha256).toBe(index.snapshot_sha256);
      const values = new Map(manifest.evidence_chunks.flatMap((c) => historicalEvidenceChunkSchema.parse(JSON.parse(assets.get(c.path)!)).records).map((r) => [r.id, r]));
      expect(rows.every((r) => matchingEvidence(values.get(r.id)!, r) && !r.comparison_eligible)).toBe(true);
      total += rows.length;
      expect(historicalManifestSchema.safeParse({ ...manifest, assertion_count: manifest.assertion_count + 1 }).success).toBe(false);
      expect(validateHistoricalIndex(rows.slice(1), manifest)).toBe(false);
    }
    expect(total).toBe(index.assertion_count);
    for (const [path, body] of assets) if (path.startsWith('catalog/chunks/')) {
      expect(Buffer.byteLength(body)).toBeLessThanOrEqual(MAX_CATALOG_CHUNK_BYTES);
      expect(path).toBe(`catalog/chunks/${createHash('sha256').update(body).digest('hex')}.json`);
    }
  });
  it('does not merge archive, retrieval and reported effective dates or infer unknown rates', () => {
    const manifest = historicalManifestSchema.parse(JSON.parse(assets.get('catalog/historical/deepinfra.json')!));
    const records = manifest.evidence_chunks.flatMap((r) => historicalEvidenceChunkSchema.parse(JSON.parse(assets.get(r.path)!)).records);
    expect(records.every((r) => r.source_reported_effective_at === null)).toBe(true);
    expect(manifest.captures.some((c) => c.archive_capture_at && c.archive_capture_at !== c.retrieved_at)).toBe(true);
    expect(records.some((r) => r.evidence.pricing)).toBe(true);
    expect(records.every((r) => !('rates' in r) && r.review_status === 'unreviewed_historical')).toBe(true);
  });
});
