// Public build provenance only. This is not an asserted deployment timestamp.
export function publicationMetadata(collectedAt: string, env: Record<string, string | undefined> = process.env, builtAt = new Date().toISOString(), development = false) {
  const commit = env.PUBLICATION_COMMIT_SHA ?? null;
  const mode = development ? 'development' : env.PUBLICATION_MODE ?? 'build';
  if (commit !== null && !/^[a-f0-9]{40}$/.test(commit)) throw new Error('Invalid publication commit SHA');
  if (!['development', 'manual', 'automatic', 'build'].includes(mode)) throw new Error('Invalid publication mode');
  for (const time of [collectedAt, builtAt]) if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(time) || !Number.isFinite(Date.parse(time))) throw new Error('Invalid publication timestamp');
  return { schema_version: 1, built_at: builtAt, data_collected_at: collectedAt, commit_sha: commit, mode };
}
