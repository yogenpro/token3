import { spawnSync } from 'node:child_process';
import { join } from 'node:path';
import { projectRoot, verifiedBuild } from './prepared_projection.ts';

const { base } = verifiedBuild(projectRoot);
const result = spawnSync(process.execPath, [join(projectRoot, 'node_modules/@playwright/test/cli.js'), 'test', ...process.argv.slice(2)], { cwd: projectRoot, stdio: 'inherit',
  env: { ...process.env, TOKEN3_TEST_BASE_PATH: base, PAGES_BASE_PATH: base } });
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
