import { createHash } from 'node:crypto';
import { historyManifestSchema, modelDirectorySchema, modelListingsSchema, nativeChangesSchema,
  providerCatalogSchema, recordChunkSchema, type ChunkRef } from '../src/lib/catalog';

export function assetJson(assets: Map<string, string>, path: string): unknown {
  const value = assets.get(path);
  if (value == null) throw new Error(`Missing projected asset ${path}`);
  return JSON.parse(value);
}
export function chunkJson(assets: Map<string, string>, ref: ChunkRef): unknown {
  const value = assets.get(ref.path);
  if (value == null || Buffer.byteLength(value) !== ref.bytes || createHash('sha256').update(value).digest('hex') !== ref.sha256) throw new Error('Invalid projected chunk');
  return JSON.parse(value);
}
export function projectedProvider(assets: Map<string, string>, id: string) {
  const header = providerCatalogSchema.parse(assetJson(assets, `catalog/providers/${id}.json`));
  const records = header.record_chunks.flatMap((ref) => recordChunkSchema.parse(chunkJson(assets, ref)).records);
  if (records.length !== header.record_count) throw new Error('Incomplete projected provider');
  return { ...header, records };
}
export function projectedEvents(assets: Map<string, string>, path: string) {
  const manifest = historyManifestSchema.parse(assetJson(assets, path));
  const events = manifest.batches.flatMap((b) => b.chunks.flatMap((ref) => nativeChangesSchema.parse(chunkJson(assets, ref)).events));
  if (events.length !== manifest.event_count) throw new Error('Incomplete projected events');
  return { ...manifest, events };
}
export function projectedListings(assets: Map<string, string>) {
  const manifest = modelDirectorySchema.parse(assetJson(assets, 'catalog/models.json'));
  return manifest.chunks.flatMap((ref) => modelListingsSchema.parse(chunkJson(assets, ref)).listings);
}
