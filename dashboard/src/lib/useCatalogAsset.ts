import { useEffect, useState } from 'react';
import type { z } from 'zod';
import { loadCatalogAsset } from './catalog';

export function useCatalogAsset<T>(path: string | null, schema: z.ZodType<T>, version: string) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<{ key: string; data?: T; error?: string }>({ key: '' });
  const key = `${path ?? ''}:${version}:${attempt}`;
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    let active = true;
    void loadCatalogAsset(path, schema, controller.signal).then((data) => {
      if (active) setResult({ key, data });
    }).catch((error: unknown) => {
      if (active) setResult({ key, error: error instanceof Error && error.name !== 'ZodError' ? error.message : 'Catalog data is incomplete or invalid. Please retry.' });
    });
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [path, schema, key]);
  return { data: result.key === key ? result.data : undefined, error: result.key === key ? result.error : undefined,
    loading: !!path && (result.key !== key || !result.data && !result.error), retry: () => setAttempt((n) => n + 1) };
}
