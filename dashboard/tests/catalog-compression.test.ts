import { afterEach, describe, expect, it, vi } from 'vitest';
import { createHash, randomBytes } from 'node:crypto';
import { gzipSync } from 'node:zlib';
import { z } from 'zod';
import { encodeCatalogChunk, decodeCatalogChunk } from '../../scripts/catalog_chunk_codec';
import { chunkRows } from '../../scripts/dashboard_projection';
import { loadCatalogChunk, MAX_CATALOG_CHUNK_BYTES, type ChunkRef } from '../src/lib/catalog';
import { loadCatalogRows } from '../src/lib/catalogChunks';

const schema = z.object({ schema_version: z.literal(1), records: z.array(z.object({ id: z.string(), text: z.string() }).strict()) }).strict();
afterEach(() => vi.unstubAllGlobals());
const ref = (body: string, count = 1): ChunkRef => {
  const sha256 = createHash('sha256').update(body).digest('hex');
  return { path: `catalog/chunks/${sha256}.json`, sha256, bytes: Buffer.byteLength(body), count };
};
const serve = (body: string) => vi.stubGlobal('fetch', vi.fn(async () => new Response(body)));

describe('lossless bounded catalog compression', () => {
  it('preserves UTF-8 records, ordering and complete browser exports across compressed chunks', async () => {
    const records = Array.from({ length: 25 }, (_, i) => ({ id: String(i), text: '模型價格'.repeat(3500) }));
    const assets = new Map<string, string>(), refs = chunkRows(records, 'records', assets, true);
    expect(refs.length).toBeGreaterThan(1);
    expect([...assets.values()].every((body) => JSON.parse(body).encoding === 'gzip-base64-v1')).toBe(true);
    vi.stubGlobal('fetch', vi.fn(async (path: string) => new Response(assets.get(path.replace(/^\//, '')))));
    expect(await loadCatalogRows(refs, schema, (v) => v.records)).toEqual(records);
    expect(refs.flatMap((r) => schema.parse(decodeCatalogChunk(assets.get(r.path)!)).records)).toEqual(records);
    expect([...assets.values()].reduce((n, s) => n + Buffer.byteLength(s), 0)).toBeLessThan(Buffer.byteLength(JSON.stringify(records)) / 2);
    await expect(loadCatalogRows([{ ...refs[0], count: refs[0].count + 1 }], schema, (v) => v.records)).rejects.toThrow('count differs');
  });
  it('retains plain JSON when compression would increase wire size', async () => {
    const plain = JSON.stringify({ schema_version: 1, records: [{ id: 'x', text: randomBytes(10000).toString('base64') }] });
    expect(encodeCatalogChunk(plain)).toBe(plain);
    serve(plain); expect(await loadCatalogChunk(ref(plain), schema)).toEqual(JSON.parse(plain));
  });
  it('rejects correct wire hashes with altered decoded hashes, sizes, gzip or encoding fields', async () => {
    const plain = JSON.stringify({ schema_version: 1, records: [{ id: 'x', text: 'price'.repeat(5000) }] });
    const encoded = encodeCatalogChunk(plain), envelope = JSON.parse(encoded);
    for (const changes of [{ content_sha256: '0'.repeat(64) }, { uncompressed_bytes: Buffer.byteLength(plain) - 1 },
      { data: envelope.data.slice(0, -4) }, { encoding: 'unknown' }, { data: '!invalid!' }, { extra: true }]) {
      const body = JSON.stringify({ ...envelope, ...changes }); serve(body);
      await expect(loadCatalogChunk(ref(body), schema)).rejects.toThrow();
      expect(() => decodeCatalogChunk(body)).toThrow();
    }
  });
  it('rejects decompression beyond the declared bound and never treats invalid data as empty', async () => {
    const raw = Buffer.from('x'.repeat(MAX_CATALOG_CHUNK_BYTES * 3));
    const body = JSON.stringify({ encoding: 'gzip-base64-v1', uncompressed_bytes: MAX_CATALOG_CHUNK_BYTES,
      content_sha256: createHash('sha256').update(raw).digest('hex'), data: gzipSync(raw).toString('base64') });
    serve(body); await expect(loadCatalogChunk(ref(body), schema)).rejects.toThrow('size limit');
    expect(() => decodeCatalogChunk(body)).toThrow();
    const controller = new AbortController(); controller.abort();
    await expect(loadCatalogChunk(ref(body), schema, controller.signal)).rejects.toThrow();
  });
});
