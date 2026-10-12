import { existsSync, lstatSync, readFileSync, realpathSync, statSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { isAbsolute, join, relative, sep } from 'node:path';
import { gunzipSync } from 'node:zlib';

const policy = 'google-unbounded-latest-v1';
const maxBytes = 16 * 1024 * 1024;
const hash = (value: Uint8Array) => createHash('sha256').update(value).digest('hex');
const digest = /^[a-f0-9]{64}$/;
type Value = Record<string, any>;
export type HistoryEntry = { event: Value; observationOnly: boolean };
const integer = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) >= 0;

export function historyVersionPath(dataDir: string): string {
  return existsSync(join(dataDir, 'inventory_history/manifest.json')) ? 'inventory_history/manifest.json' : 'inventory_history.jsonl';
}
function asset(dataDir: string, ref: Value, directory: string, suffix: string): Buffer {
  const expected = `inventory_history/${directory}/${ref.sha256}.${suffix}`;
  if (!digest.test(ref.sha256 ?? '') || ref.path !== expected || !integer(ref.bytes) || ref.bytes <= 0 || ref.bytes > maxBytes + 128 * 1024) throw new Error('Invalid history asset reference');
  const path = join(dataDir, expected);
  const local = relative(realpathSync(dataDir), realpathSync(path));
  if (lstatSync(path).isSymbolicLink() || isAbsolute(local) || local.split(sep).includes('..') || statSync(path).size !== ref.bytes) throw new Error('Unsafe or incomplete history asset');
  const bytes = readFileSync(path);
  if (hash(bytes) !== ref.sha256) throw new Error('History asset checksum differs');
  return bytes;
}
function segment(dataDir: string, ref: Value): string {
  if (!integer(ref.uncompressed_bytes) || ref.uncompressed_bytes <= 0 || ref.uncompressed_bytes > maxBytes || !integer(ref.event_count) || !digest.test(ref.content_sha256 ?? '')) throw new Error('Invalid history segment');
  const decoded = gunzipSync(asset(dataDir, ref, 'segments', 'jsonl.gz'), { maxOutputLength: maxBytes + 1 });
  if (decoded.length !== ref.uncompressed_bytes || hash(decoded) !== ref.content_sha256) throw new Error('History segment content differs');
  const text = decoded.toString('utf8');
  if (!text.endsWith('\n') || text.split('\n').filter((line) => line.trim()).length !== ref.event_count) throw new Error('Incomplete history segment');
  return text;
}
function latestScope(proof: Value): boolean {
  if (!['api', 'api+documentation'].includes(proof.source_kind) || !Array.isArray(proof.source_urls)) return false;
  let sku = false;
  for (const value of proof.source_urls) {
    const url = new URL(value);
    if (url.hostname !== 'cloudbilling.googleapis.com') continue;
    if (url.protocol !== 'https:' || url.username || url.password) return false;
    if (/^\/v1\/services\/[A-Za-z0-9_-]+\/skus$/.test(url.pathname)) sku = true;
    else if (url.pathname !== '/v1/services') return false;
    if ([...url.searchParams.keys()].some((key) => !['currencyCode', 'pageSize', 'pageToken'].includes(key))) return false;
  }
  return sku;
}
function latestTime(record: Value | undefined, observedAt: string): string | null {
  const service = record?.scope?.service, infos = record?.billing?.pricing_info;
  if (record?.provider !== 'vertex' || record.kind !== 'sku' || typeof service !== 'string' || !/^services\/[A-Za-z0-9_-]+$/.test(service) ||
    typeof record.native_id !== 'string' || !record.native_id.startsWith(`${service}/skus/`) || !Array.isArray(infos) || infos.length !== 1) return null;
  const time = infos[0]?.effectiveTime;
  if (typeof time !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$/.test(time) || !Number.isFinite(Date.parse(time)) ||
    !Number.isFinite(Date.parse(observedAt)) || Date.parse(observedAt) - Date.parse(time) < -20 * 60 * 1000 ||
    (record.rates ?? []).some((rate: Value) => rate.conditions?.effective_time !== time)) return null;
  return time;
}

/** Reconstruct original events in recorded order. Interpretation is a separate flag;
 * legacy rows without a checksummed migration remain conservatively classified. */
export function* readNativeHistory(dataDir: string): Generator<HistoryEntry> {
  const manifestPath = join(dataDir, 'inventory_history/manifest.json');
  if (!existsSync(manifestPath)) {
    const legacy = join(dataDir, 'inventory_history.jsonl');
    if (!existsSync(legacy)) return;
    for (const line of readFileSync(legacy, 'utf8').split('\n')) {
      if (!line.trim()) continue;
      const event = JSON.parse(line);
      if ('_observation' in event) throw new Error('Observation requires a verified manifest');
      yield { event, observationOnly: false };
    }
    return;
  }
  if (statSync(manifestPath).size > 4 * 1024 * 1024) throw new Error('Oversized history manifest');
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  if (manifest.schema_version !== 1 || manifest.policy !== policy || !integer(manifest.event_count) || !integer(manifest.observation_count) || manifest.observation_count > manifest.event_count ||
    !Array.isArray(manifest.segments) || new Set(manifest.segments.map((r: Value) => r.path)).size !== manifest.segments.length ||
    manifest.segments.reduce((n: number, r: Value) => n + r.event_count, 0) !== manifest.event_count) throw new Error('Incomplete history manifest');
  const legacy = join(dataDir, 'inventory_history.jsonl');
  if (existsSync(legacy) && (statSync(legacy).size !== manifest.archive?.bytes || hash(readFileSync(legacy)) !== manifest.archive?.sha256)) throw new Error('Legacy history changed after compaction');
  if (manifest.proofs?.bytes > 1024 * 1024) throw new Error('Oversized history proof');
  const proofDocument = JSON.parse(asset(dataDir, manifest.proofs, 'proofs', 'json').toString('utf8'));
  if (proofDocument.schema_version !== 1 || proofDocument.policy !== policy || !proofDocument.catalogs || typeof proofDocument.catalogs !== 'object') throw new Error('Invalid history proofs');
  const proofs: Value = proofDocument.catalogs;
  for (const [key, value] of Object.entries<Value>(proofs)) if (!digest.test(key) || value.catalog_sha256 !== key || !latestScope(value)) throw new Error('Unverified retrospective request scope');
  const previous = new Map<string, Value>(), ids = new Set<string>();
  let count = 0, observations = 0;
  for (const ref of manifest.segments) {
    for (const line of segment(dataDir, ref).split('\n')) {
      if (!line.trim()) continue;
      const event = JSON.parse(line), observation = event._observation;
      delete event._observation;
      if (typeof event.id !== 'string' || ids.has(event.id)) throw new Error('Duplicate or invalid history event ID');
      ids.add(event.id); count++;
      if (observation != null) {
        const old = previous.get(event.record_id);
        if (event.provider !== 'vertex' || event.kind !== 'record_changed' || 'after' in event || observation.policy !== policy || !old ||
          old.id !== observation.before_event_id || !proofs[old.catalog_sha256] || !proofs[event.catalog_sha256] || !digest.test(observation.original_event_sha256 ?? '') ||
          !latestTime(old.after, old.observed_at)) throw new Error('Invalid retrospective observation reference');
        const after = structuredClone(old.after), value = observation.effective_time;
        after.billing.pricing_info[0].effectiveTime = value;
        for (const rate of after.rates ?? []) rate.conditions.effective_time = value;
        if (typeof value !== 'string' || latestTime(after, event.observed_at) !== value) throw new Error('Invalid retrospective observation timestamp');
        event.after = after; observations++;
      }
      if (event.after) previous.set(event.record_id, event);
      else if (event.kind === 'record_no_longer_listed') previous.delete(event.record_id);
      yield { event, observationOnly: observation != null };
    }
  }
  if (count !== manifest.event_count || observations !== manifest.observation_count) throw new Error('History totals differ');
}
