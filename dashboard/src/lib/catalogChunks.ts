import { useEffect, useState } from 'react';
import type { z } from 'zod';
import { loadCatalogChunk, type ChunkRef } from './catalog';

// Bounded concurrency, cancellation and all-or-error results. A failed chunk
// must never look like a valid shorter catalog or empty search result.
export async function loadCatalogRows<T extends { id: string }, E>(refs: ChunkRef[], schema: z.ZodType<E>,
  rows: (envelope: E) => T[], signal?: AbortSignal, progress?: (completed: number, total: number) => void): Promise<T[]> {
  const controller = new AbortController();
  const combined = signal ? AbortSignal.any([signal, controller.signal]) : controller.signal;
  const result: T[][] = new Array(refs.length);
  let next = 0, completed = 0;
  try {
    await Promise.all(Array.from({ length: Math.min(4, refs.length) }, async () => {
      while (next < refs.length) {
        combined.throwIfAborted();
        const i = next++;
        const values = rows(await loadCatalogChunk(refs[i], schema, combined));
        if (values.length !== refs[i].count) throw new Error('Catalog chunk count differs from its manifest.');
        result[i] = values; progress?.(++completed, refs.length);
      }
    }));
    const values = result.flat();
    if (new Set(values.map((r) => r.id)).size !== values.length) throw new Error('Duplicate records in catalog chunks.');
    return values;
  } catch (error) { controller.abort(); throw error; }
}

export function useCatalogChunks<T extends { id: string }, E>(refs: ChunkRef[] | undefined, schema: z.ZodType<E>,
  rows: (envelope: E) => T[], version: string) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<{ key: string; data?: T[]; error?: string }>({ key: '' });
  const [progress, setProgress] = useState<{ key: string; done: number; total: number }>({ key: '', done: 0, total: 0 });
  const key = refs ? `${version}:${attempt}:${refs.map((r) => `${r.sha256}:${r.count}:${r.bytes}`).join(',')}` : '';
  useEffect(() => {
    if (!refs) return;
    const controller = new AbortController();
    let active = true;
    void loadCatalogRows(refs, schema, rows, controller.signal, (done, total) => {
      if (active) setProgress({ key, done, total });
    }).then((data) => { if (active) setResult({ key, data }); }).catch((error: unknown) => {
      if (active) setResult({ key, error: error instanceof Error && error.name !== 'ZodError' ? error.message : 'Catalog chunks are incomplete or invalid. Please retry.' });
    });
    return () => { active = false; controller.abort(); };
    // Stable schema and row selectors are module-level. The key describes the
    // entire immutable manifest, not the newly allocated references array.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, schema, rows]);
  return { data: result.key === key && refs ? result.data : undefined,
    error: result.key === key && refs ? result.error : undefined,
    loading: !!refs && (result.key !== key || !result.data && !result.error),
    progress: progress.key === key ? progress : { done: 0, total: refs?.length ?? 0 },
    retry: () => setAttempt((n) => n + 1) };
}

export function pageChunks(refs: ChunkRef[], page: number, size = 25): { refs: ChunkRef[]; offset: number } {
  const start = (page - 1) * size, end = start + size;
  let skipped = 0;
  const selected: ChunkRef[] = [];
  let offset = 0;
  for (const ref of refs) {
    if (skipped + ref.count > start && skipped < end) {
      if (!selected.length) offset = start - skipped;
      selected.push(ref);
    }
    skipped += ref.count;
  }
  return { refs: selected, offset };
}
