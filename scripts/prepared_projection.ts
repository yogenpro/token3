import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { closeSync, existsSync, lstatSync, mkdirSync, mkdtempSync, openSync, readFileSync, readSync, readdirSync, realpathSync, renameSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { z } from 'zod';

export const projectRoot = resolve(fileURLToPath(new URL('..', import.meta.url)));
const digest = z.string().regex(/^[a-f0-9]{64}$/);
const publicPath = z.string().regex(/^catalog\/(?:index|models|(?:providers|history|changes|historical)\/[a-z0-9_-]+|chunks\/[a-f0-9]{64})\.json$/);
const assetSchema = z.object({ path: publicPath, sha256: digest, bytes: z.number().int().positive().max(16 * 1024 * 1024) }).strict();
const receiptSchema = z.object({ schema_version: z.literal(1), kind: z.enum(['native', 'historical']), input_sha256: digest,
  assets: z.array(assetSchema).max(20000) }).strict();
const sha = (value: string | Uint8Array) => createHash('sha256').update(value).digest('hex');

export function fileHash(path: string): string {
  if (!lstatSync(path).isFile() || lstatSync(path).isSymbolicLink()) throw new Error('Input/output must be a regular file');
  const hash = createHash('sha256'), fd = openSync(path, 'r'), buffer = Buffer.alloc(1024 * 1024);
  try { let n: number; while ((n = readSync(fd, buffer, 0, buffer.length, null))) hash.update(buffer.subarray(0, n)); }
  finally { closeSync(fd); }
  return hash.digest('hex');
}

export function treeFiles(root: string): string[] {
  return readdirSync(root, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name)).flatMap((entry) => {
    if (['__pycache__', '.collect.lock', '.ledger.lock'].includes(entry.name) || entry.name.endsWith('.pyc')) return [];
    const path = join(root, entry.name);
    if (entry.isSymbolicLink()) throw new Error('Input/output tree cannot contain symlinks');
    return entry.isDirectory() ? treeFiles(path) : [path];
  });
}

/** Content hashes include dirty/untracked source files, not mtimes or only manifests.
 * No credentials, installed dependency trees, build outputs or raw response staging. */
export function projectionFingerprint(root: string): string {
  const paths = ['data', 'scripts', 'providers', 'dashboard/src', 'dashboard/tests', 'tests', 'catalog', 'config', 'docs', '.github/workflows',
    'package.json', 'package-lock.json', 'requirements.txt', 'vite.config.ts', 'playwright.config.ts', 'tsconfig.json', 'README.md', 'AGENTS.md'];
  const hash = createHash('sha256');
  hash.update(JSON.stringify({ commit: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    node: process.version, python: execFileSync('python3', ['-c', 'import sys, pypdf; print(sys.version); print(pypdf.__version__)'], { cwd: root, encoding: 'utf8' }) }));
  for (const path of paths) {
    const absolute = join(root, path);
    hash.update(JSON.stringify(path));
    if (!existsSync(absolute)) { hash.update('missing'); continue; }
    const files = lstatSync(absolute).isDirectory() ? treeFiles(absolute) : [absolute];
    for (const file of files) hash.update(JSON.stringify([file.slice(root.length + 1), fileHash(file)]));
  }
  return hash.digest('hex');
}

/** Same-run scratch only: never restored from Actions caches or other runs. */
export function preparedProjection(kind: 'native' | 'historical', directory: string, key: string,
  build: () => Map<string, string>, validate: (assets: Map<string, string>) => void): Map<string, string> {
  digest.parse(key);
  if (realpathSync(directory) !== resolve(directory)) throw new Error('Prepared projection directory cannot traverse symlinks');
  const target = join(directory, kind), receipt = join(target, 'receipt.json');
  if (existsSync(target)) {
    if (!lstatSync(target).isDirectory() || lstatSync(target).isSymbolicLink() || !existsSync(receipt) || !lstatSync(receipt).isFile() || lstatSync(receipt).isSymbolicLink() || statSync(receipt).size > 4 * 1024 * 1024) throw new Error('Incomplete prepared projection');
    const saved = receiptSchema.parse(JSON.parse(readFileSync(receipt, 'utf8')));
    if (saved.kind !== kind || saved.input_sha256 !== key || new Set(saved.assets.map((a) => a.path)).size !== saved.assets.length) throw new Error('Prepared projection inputs differ');
    const assets = new Map<string, string>();
    for (const ref of saved.assets) {
      const path = join(target, `${ref.sha256}.json`);
      if (statSync(path).size !== ref.bytes || fileHash(path) !== ref.sha256) throw new Error('Prepared projection asset hash/bytes differ');
      assets.set(ref.path, new TextDecoder('utf-8', { fatal: true }).decode(readFileSync(path)));
    }
    validate(assets);
    console.info(`[projection] reused ${kind} assets from this check`);
    return assets;
  }
  const assets = build();
  validate(assets);
  const staging = mkdtempSync(join(directory, `${kind}-`));
  try {
    const refs = [...assets].map(([path, body]) => {
      const ref = assetSchema.parse({ path, bytes: Buffer.byteLength(body), sha256: sha(body) });
      const file = join(staging, `${ref.sha256}.json`);
      if (!existsSync(file)) writeFileSync(file, body, { flag: 'wx' });
      return ref;
    });
    writeFileSync(join(staging, 'receipt.json'), JSON.stringify(receiptSchema.parse({ schema_version: 1, kind, input_sha256: key, assets: refs })), { flag: 'wx' });
    renameSync(staging, target);
  } finally { rmSync(staging, { recursive: true, force: true }); }
  console.info(`[projection] generated ${kind} assets for this check`);
  return assets;
}

export function checkedProjection(kind: 'native' | 'historical', dataDir: string, build: () => Map<string, string>, validate: (assets: Map<string, string>) => void) {
  const directory = process.env.TOKEN3_PROJECTION_CACHE, key = process.env.TOKEN3_PROJECTION_INPUT_SHA;
  if ((!directory && !key) || resolve(dataDir) !== join(projectRoot, 'data')) return build();
  if (!directory || !key) throw new Error('Incomplete check projection context');
  const unchanged = () => { if (projectionFingerprint(projectRoot) !== key) throw new Error('Check inputs changed; restart npm run check'); };
  unchanged();
  const assets = preparedProjection(kind, directory, key, build, validate);
  unchanged();
  return assets;
}

const buildReceiptPath = (root: string) => join(root, 'node_modules/.cache/token3/build.json');
const outputPath = (root: string, path: string) => relative(root, path).split(sep).join('/');
export function recordBuild(root: string, base: string, expectedInput?: string) {
  if (!/^\/(?:[A-Za-z0-9._-]+\/)*$/.test(base)) throw new Error('Unsupported static site base path');
  const input = projectionFingerprint(root);
  if (expectedInput && expectedInput !== input) throw new Error('Check inputs changed; restart npm run check');
  const output = join(root, 'dist');
  const receipt = { schema_version: 1, input_sha256: input, base,
    assets: treeFiles(output).map((path) => ({ path: outputPath(output, path), bytes: statSync(path).size, sha256: fileHash(path) })) };
  const path = buildReceiptPath(root);
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(receipt));
}

export function verifiedBuild(root: string): { base: string } {
  const path = buildReceiptPath(root);
  if (!existsSync(path)) throw new Error('No verified production build. Run npm run check or npm run build first.');
  const receipt = z.object({ schema_version: z.literal(1), input_sha256: digest, base: z.string().regex(/^\/(?:[A-Za-z0-9._-]+\/)*$/),
    assets: z.array(z.object({ path: z.string().regex(/^(?!\/)(?!.*(?:^|\/)\.{1,2}(?:\/|$))[A-Za-z0-9_./-]+$/), bytes: z.number().int().nonnegative(), sha256: digest }).strict()) }).strict().parse(JSON.parse(readFileSync(path, 'utf8')));
  if (receipt.input_sha256 !== projectionFingerprint(root)) throw new Error('Production build inputs changed. Run npm run check or npm run build again.');
  const output = join(root, 'dist');
  const actual = treeFiles(output).map((p) => outputPath(output, p)).sort();
  if (JSON.stringify(actual) !== JSON.stringify(receipt.assets.map((a) => a.path).sort())) throw new Error('Production build file set differs');
  for (const ref of receipt.assets) if (statSync(join(output, ref.path)).size !== ref.bytes || fileHash(join(output, ref.path)) !== ref.sha256) throw new Error('Production build hash/bytes differ');
  return { base: receipt.base };
}
