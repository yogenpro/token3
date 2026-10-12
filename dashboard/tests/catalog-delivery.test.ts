import { afterEach, describe, expect, it, vi } from 'vitest';
import { createHash } from 'node:crypto';
import { z } from 'zod';
import { chunkRows } from '../../scripts/dashboard_projection';
import { chunkRefSchema, historyManifestSchema, loadCatalogChunk, MAX_CATALOG_CHUNK_BYTES, providerCatalogSchema, billingBasis } from '../src/lib/catalog';
import { loadCatalogRows, pageChunks } from '../src/lib/catalogChunks';

const envelope = z.object({ schema_version: z.literal(1), records: z.array(z.object({ id: z.string(), text: z.string() })) });
const selector = (value: z.infer<typeof envelope>) => value.records;
afterEach(() => vi.unstubAllGlobals());

function fixture(rows: Array<{ id: string; text: string }>) {
  const assets = new Map<string, string>();
  return { assets, refs: chunkRows(rows, 'records', assets) };
}
function mockedFetch(assets: Map<string, string>) {
  return vi.fn(async (path: string) => new Response(assets.get(path.replace(/^\//, '')), { status: assets.has(path.replace(/^\//, '')) ? 200 : 404 }));
}

describe('bounded, immutable public delivery', () => {
  it('chunks UTF-8 by bytes without losing, altering or reordering records', () => {
    const records = Array.from({ length: 30 }, (_, i) => ({ id: String(i), text: '模型價格'.repeat(4000) }));
    const { assets, refs } = fixture(records);
    expect(refs.length).toBeGreaterThan(1);
    expect(refs.every((r) => r.bytes <= MAX_CATALOG_CHUNK_BYTES)).toBe(true);
    expect(refs.flatMap((r) => envelope.parse(JSON.parse(assets.get(r.path)!)).records)).toEqual(records);
    for (const ref of refs) {
      expect(ref.bytes).toBe(Buffer.byteLength(assets.get(ref.path)!));
      expect(ref.sha256).toBe(createHash('sha256').update(assets.get(ref.path)!).digest('hex'));
      expect(chunkRefSchema.parse(ref)).toEqual(ref);
    }
    expect(fixture(records).refs).toEqual(refs);
  });
  it('fails closed on an oversized atomic record rather than silently truncating evidence', () => {
    expect(() => fixture([{ id: 'large', text: 'x'.repeat(MAX_CATALOG_CHUNK_BYTES) }])).toThrow('explicit projection review');
  });
  it('checks content hashes, bytes, counts, schemas and duplicate IDs before returning a catalog', async () => {
    const { assets, refs } = fixture([{ id: 'first', text: 'original' }]);
    vi.stubGlobal('fetch', mockedFetch(assets));
    expect(await loadCatalogRows(refs, envelope, selector)).toEqual([{ id: 'first', text: 'original' }]);
    await expect(loadCatalogRows([{ ...refs[0], count: 2 }], envelope, selector)).rejects.toThrow('count differs');
    const duplicate = fixture([{ id: 'first', text: 'a' }, { id: 'first', text: 'b' }]);
    vi.stubGlobal('fetch', mockedFetch(duplicate.assets));
    await expect(loadCatalogRows(duplicate.refs, envelope, selector)).rejects.toThrow('Duplicate');
    assets.set(refs[0].path, assets.get(refs[0].path)!.replace('original', 'modified'));
    vi.stubGlobal('fetch', mockedFetch(assets));
    await expect(loadCatalogChunk(refs[0], envelope)).rejects.toThrow('manifest differ');
    await expect(loadCatalogChunk({ ...refs[0], path: 'https://private.example/credential' }, envelope)).rejects.toThrow();
  });
  it('requires a secure verification context instead of bypassing checks on insecure origins', async () => {
    const { refs } = fixture([{ id: 'one', text: 'test' }]);
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch); vi.stubGlobal('crypto', undefined);
    await expect(loadCatalogChunk(refs[0], envelope)).rejects.toThrow('HTTPS or localhost');
    expect(fetch).not.toHaveBeenCalled();
  });
  it('a missing chunk is an explicit failure, never a partial successful catalog', async () => {
    const { assets, refs } = fixture(Array.from({ length: 30 }, (_, i) => ({ id: String(i), text: 'x'.repeat(60000) })));
    assets.delete(refs.at(-1)!.path);
    vi.stubGlobal('fetch', mockedFetch(assets));
    await expect(loadCatalogRows(refs, envelope, selector)).rejects.toThrow('HTTP 404');
  });
  it('limits concurrent chunk requests and honors cancellation instead of completing stale searches', async () => {
    const { assets, refs } = fixture(Array.from({ length: 40 }, (_, i) => ({ id: String(i), text: 'x'.repeat(60000) })));
    let active = 0, highest = 0;
    vi.stubGlobal('fetch', vi.fn(async (path: string) => {
      active++; highest = Math.max(highest, active);
      await new Promise((resolve) => setTimeout(resolve, 10));
      active--; return new Response(assets.get(path.replace(/^\//, '')));
    }));
    expect(await loadCatalogRows(refs, envelope, selector)).toHaveLength(40);
    expect(highest).toBeLessThanOrEqual(4);
    expect(highest).toBeGreaterThan(1);
    const controller = new AbortController(); controller.abort();
    await expect(loadCatalogRows(refs, envelope, selector, controller.signal)).rejects.toThrow();
  });
  it('event paging fetches only intersecting chunks and handles a cross-chunk page', () => {
    const { refs } = fixture([{ id: 'one', text: 'test' }]);
    const first = { ...refs[0], count: 30 }, second = { ...refs[0], path: `catalog/chunks/${'b'.repeat(64)}.json`, count: 30 };
    expect(pageChunks([first, second], 1)).toEqual({ refs: [first], offset: 0 });
    expect(pageChunks([first, second], 2)).toEqual({ refs: [first, second], offset: 25 });
    expect(pageChunks([first, second], 3)).toEqual({ refs: [second], offset: 20 });
  });
  it('rejects incomplete manifests instead of pretending pagination or exports are complete', () => {
    expect(() => historyManifestSchema.parse({ schema_version: 2, event_count: 1, batches: [] })).toThrow();
    expect(() => providerCatalogSchema.parse({ schema_version: 2, provider: 'test', catalog_sha256: 'hash', revision: 1,
      billing_notes: [], source_evidence: [], record_count: 1, index_chunks: [], record_chunks: [] })).toThrow();
  });
  it.each([['per image', 'Images'], ['input second', 'Audio / video'], ['per request', 'Requests'], ['GiBy.h', 'Storage / memory'], ['1M TPM Hour', 'Capacity']])('facets %s without converting its amount or unit', (unit, expected) => {
    const r = { rates: [{ dimension: 'price', amount: '0.000001', currency: 'EUR', unit, conditions: {} }], billing: {}, scope: {} };
    expect(billingBasis(r)).toBe(expected);
    expect(r.rates[0]).toMatchObject({ amount: '0.000001', currency: 'EUR', unit });
  });
});
