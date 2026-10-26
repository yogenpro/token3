import { z } from 'zod';
import { chunkRefSchema } from './catalog';

const count = z.number().int().nonnegative();
const digest = z.string().regex(/^[a-f0-9]{64}$/);
const time = z.string().refine((s) => /T/.test(s) && Number.isFinite(Date.parse(s)), 'Invalid evidence timestamp');
const url = z.url().refine((s) => {
  const u = new URL(s);
  return ['http:', 'https:'].includes(u.protocol) && !u.username && !u.password && ![...u.searchParams.keys()].some((k) => /key|token|secret|signature|credential|authorization/i.test(k));
});
const object = z.record(z.string(), z.unknown());
export const historicalCaptureSchema = z.object({
  id: z.string(), provider: z.string(), source_kind: z.string(), source_url: url, replay_url: url.nullable(),
  retrieved_at: time, archive_capture_at: time.nullable(), source_published_at: time.nullable(), source_sha256: digest,
  scope: object, state: z.string(), assertion_count: count, returned_entries: count.nullable(), cap_reached: z.boolean(),
}).strict();
export const historicalEvidenceSchema = z.object({
  id: z.string(), provider: z.string(), native_id: z.string(), label: z.string(), capture_id: z.string(),
  assertion_type: z.string(), identity_scope: object, source_pointer: z.unknown(), source_reported_effective_at: time.nullable(),
  extractor: z.string(), review_status: z.literal('unreviewed_historical'), comparison_eligible: z.literal(false), evidence: object,
}).strict();
export const historicalSummarySchema = historicalEvidenceSchema.omit({ evidence: true, extractor: true, source_pointer: true }).extend({
  detail_path: chunkRefSchema.shape.path,
});
export const historicalCheckSchema = z.object({
  id: z.string(), provider: z.string(), state: z.string(), checked_at: time.nullable(), checked_date: z.string().nullable(), recorded_at: time.nullable(),
  source_url: url, target_url: url.nullable(), archive_capture_at: time.nullable(), http_status: z.number().int().nullable(),
  transport_exit_code: z.number().int().nullable(), comparison_eligible: z.literal(false),
}).strict();
const correction = z.object({ id: z.string(), assertion_id: z.string(), supersedes: z.string(), reason: z.string(), recorded_at: time }).strict();
const counts = z.record(z.string(), count);
export const historicalProviderSchema = z.object({
  id: z.string().regex(/^[a-z0-9_-]+$/), name: z.string(), capture_count: count, assertion_count: count, check_count: count,
  archive_from: time.nullable(), archive_to: time.nullable(), retrieved_through: time,
  states: counts, check_states: counts, detail_path: z.string().regex(/^catalog\/historical\/[a-z0-9_-]+\.json$/),
}).strict();
export const historicalIndexSchema = z.object({ schema_version: z.literal(2), snapshot_sha256: digest,
  capture_count: count, assertion_count: count, check_count: count, providers: z.array(historicalProviderSchema),
}).strict().refine((d) => new Set(d.providers.map((p) => p.id)).size === d.providers.length &&
  d.providers.every((p) => p.detail_path === `catalog/historical/${p.id}.json`) &&
  d.providers.reduce((n, p) => n + p.capture_count, 0) === d.capture_count &&
  d.providers.reduce((n, p) => n + p.assertion_count, 0) === d.assertion_count &&
  d.providers.reduce((n, p) => n + p.check_count, 0) === d.check_count, 'Incomplete historical summary');
export const historicalManifestSchema = z.object({
  schema_version: z.literal(2), snapshot_sha256: digest, provider: z.string(), captures: z.array(historicalCaptureSchema),
  assertion_count: count, check_count: count, index_chunks: z.array(chunkRefSchema), evidence_chunks: z.array(chunkRefSchema),
  check_chunks: z.array(chunkRefSchema), corrections: z.array(correction),
}).strict().refine((d) => new Set(d.captures.map((c) => c.id)).size === d.captures.length &&
  d.captures.every((c) => c.provider === d.provider) && d.captures.reduce((n, c) => n + c.assertion_count, 0) === d.assertion_count &&
  [d.index_chunks, d.evidence_chunks].every((refs) => refs.reduce((n, r) => n + r.count, 0) === d.assertion_count && new Set(refs.map((r) => r.path)).size === refs.length) &&
  d.check_chunks.reduce((n, r) => n + r.count, 0) === d.check_count && new Set(d.check_chunks.map((r) => r.path)).size === d.check_chunks.length,
'Incomplete historical provider manifest');
export const historicalEvidenceChunkSchema = z.object({ schema_version: z.literal(1), records: z.array(historicalEvidenceSchema) }).strict();
export const historicalIndexChunkSchema = z.object({ schema_version: z.literal(1), records: z.array(historicalSummarySchema) }).strict();
export const historicalCheckChunkSchema = z.object({ schema_version: z.literal(1), records: z.array(historicalCheckSchema) }).strict();
export type HistoricalIndex = z.infer<typeof historicalIndexSchema>;
export type HistoricalManifest = z.infer<typeof historicalManifestSchema>;
export type HistoricalSummary = z.infer<typeof historicalSummarySchema>;
export type HistoricalEvidence = z.infer<typeof historicalEvidenceSchema>;
export const evidenceKind = (kind: string) => ({ aws_sku_dimension: 'AWS billing dimension', aws_unpriced_product: 'Unpriced AWS product', deepinfra_model: 'Native model', historical_native_model: 'Native model', historical_provider_route: 'Provider route', deepinfra_table_row: 'Document row', historical_document_row: 'Document row', historical_document_text: 'Document text', historical_pdf_page: 'PDF page' })[kind] ?? kind;
export const historicalSearch = (r: HistoricalSummary) => `${r.native_id} ${r.label} ${JSON.stringify(r.identity_scope)}`.toLowerCase();
export const evidenceRows = (v: z.infer<typeof historicalEvidenceChunkSchema>) => v.records;
export const summaryRows = (v: z.infer<typeof historicalIndexChunkSchema>) => v.records;
export const checkRows = (v: z.infer<typeof historicalCheckChunkSchema>) => v.records;

export function validateHistoricalIndex(records: HistoricalSummary[], manifest: HistoricalManifest): boolean {
  const counts = new Map<string, number>();
  const captures = new Set(manifest.captures.map((c) => c.id));
  for (const r of records) {
    if (r.provider !== manifest.provider || !captures.has(r.capture_id) || !manifest.evidence_chunks.some((c) => c.path === r.detail_path)) return false;
    counts.set(r.capture_id, (counts.get(r.capture_id) ?? 0) + 1);
  }
  return records.length === manifest.assertion_count && manifest.captures.every((c) => (counts.get(c.id) ?? 0) === c.assertion_count);
}
export function matchingEvidence(record: HistoricalEvidence, summary: HistoricalSummary): boolean {
  const { detail_path: _, ...expected } = summary;
  const { evidence: __, source_pointer: ___, extractor: ____, ...actual } = record;
  return JSON.stringify(actual) === JSON.stringify(expected);
}
