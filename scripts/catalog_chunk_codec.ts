import { createHash } from 'node:crypto';
import { gzipSync, gunzipSync } from 'node:zlib';
import { compressedChunkSchema, MAX_CATALOG_CHUNK_BYTES } from '../dashboard/src/lib/catalog';

export function encodeCatalogChunk(body: string): string {
  const raw = Buffer.from(body);
  if (!raw.length || raw.length > MAX_CATALOG_CHUNK_BYTES) throw new Error('Decoded catalog chunk exceeds size limit');
  const fields = { encoding: 'gzip-base64-v1', uncompressed_bytes: raw.length,
    content_sha256: createHash('sha256').update(raw).digest('hex'), data: gzipSync(raw).toString('base64') };
  const envelope = JSON.stringify(fields);
  return Buffer.byteLength(envelope) < raw.length ? JSON.stringify(compressedChunkSchema.parse(fields)) : body;
}

export function decodeCatalogChunk(body: string): unknown {
  if (Buffer.byteLength(body) > MAX_CATALOG_CHUNK_BYTES) throw new Error('Encoded catalog chunk exceeds size limit');
  const value: unknown = JSON.parse(body);
  if (!value || typeof value !== 'object' || !('encoding' in value)) return value;
  const envelope = compressedChunkSchema.parse(value);
  const compressed = Buffer.from(envelope.data, 'base64');
  if (compressed.toString('base64') !== envelope.data) throw new Error('Invalid catalog chunk encoding');
  const raw = gunzipSync(compressed, { maxOutputLength: MAX_CATALOG_CHUNK_BYTES });
  if (raw.length !== envelope.uncompressed_bytes || createHash('sha256').update(raw).digest('hex') !== envelope.content_sha256) {
    throw new Error('Decoded catalog chunk hash/bytes differ');
  }
  return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(raw));
}
