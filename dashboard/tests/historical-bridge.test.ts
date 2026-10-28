import { afterEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { readHistoricalProjection } from '../../scripts/dashboard_projection';

const folders: string[] = [];
afterEach(() => { for (const path of folders.splice(0)) rmSync(path, { recursive: true, force: true }); });
const metadata = (assertions = 0) => ({ kind: 'metadata', value: { schema_version: 1, snapshot_sha256: 'a'.repeat(64), counts: { captures: 0, assertions, checks: 0, corrections: 0 } } });
function file(lines: unknown[], terminated = true) {
  const directory = mkdtempSync(join(tmpdir(), 'historical-bridge-test-')); folders.push(directory);
  const path = join(directory, 'projection.jsonl');
  writeFileSync(path, lines.map((r) => JSON.stringify(r)).join('\n') + (terminated ? '\n' : ''));
  return path;
}

describe('private historical projection record bridge', () => {
  it('preserves unicode across read boundaries and verifies complete record counts', () => {
    const value = { id: 'row', provider: 'example', native_id: 'exact/model', label: '历史价格', capture_id: 'capture', assertion_type: 'historical_document_text',
      identity_scope: {}, source_pointer: {}, source_reported_effective_at: null, extractor: 'fixture', review_status: 'unreviewed_historical', comparison_eligible: false, evidence: { text: '价'.repeat(170000) } };
    const path = file([metadata(3), ...Array.from({ length: 3 }, () => ({ kind: 'assertion', value }))]);
    expect(readHistoricalProjection(path).assertions.map((r: any) => r.evidence.text)).toEqual([value.evidence.text, value.evidence.text, value.evidence.text]);
  });
  it('fails closed on truncation, wrong counts, extra envelopes and unsafe evidence', () => {
    for (const path of [file([metadata()], false), file([metadata(1)]), file([metadata(), { kind: 'metadata', value: {} }]),
      file([metadata(), { kind: 'assertion', value: { comparison_eligible: true } }]), file([{ kind: 'check', value: {} }])]) {
      expect(() => readHistoricalProjection(path)).toThrow();
    }
  });
  it('bounds every private bridge record', () => {
    expect(() => readHistoricalProjection(file([metadata(), { kind: 'assertion', value: 'x'.repeat(1024 * 1024) }]))).toThrow(/cap/);
  });
});
