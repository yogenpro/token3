import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { projectRoot, projectionFingerprint } from './prepared_projection.ts';

const directory = mkdtempSync(join(tmpdir(), 'token3-check-'));
const cleanup = () => rmSync(directory, { recursive: true, force: true });
process.once('exit', cleanup);
try {
  if (!process.env.npm_execpath) throw new Error('Run this entrypoint with npm run check.');
  const env = { ...process.env, TOKEN3_PROJECTION_CACHE: directory, TOKEN3_PROJECTION_INPUT_SHA: projectionFingerprint(projectRoot) };
  for (const command of ['test', 'test:collectors', 'build']) {
    const result = spawnSync(process.execPath, [process.env.npm_execpath, 'run', command], { cwd: projectRoot, env, stdio: 'inherit' });
    if (result.error) throw result.error;
    if (result.status !== 0) { process.exitCode = result.status ?? 1; break; }
    if (projectionFingerprint(projectRoot) !== env.TOKEN3_PROJECTION_INPUT_SHA) throw new Error('Check inputs changed; restart npm run check');
  }
} finally { cleanup(); }
