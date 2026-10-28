import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, symlinkSync, utimesSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { preparedProjection, projectRoot, projectionFingerprint, recordBuild, verifiedBuild } from '../../scripts/prepared_projection';

let root: string;
beforeEach(() => { root = mkdtempSync(join(tmpdir(), 'token3-prepared-test-')); });
afterEach(() => rmSync(root, { recursive: true, force: true }));
const key = 'a'.repeat(64);
const fixture = () => new Map([['catalog/historical/index.json', '{"fixture":"Original units"}']]);
function inputs() {
  execFileSync('git', ['init', '-q'], { cwd: root });
  writeFileSync(join(root, 'package.json'), '{}');
  execFileSync('git', ['add', 'package.json'], { cwd: root });
  execFileSync('git', ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Fixture'], { cwd: root });
  mkdirSync(join(root, 'data'));
  writeFileSync(join(root, 'data/source.bin'), 'source');
}

describe('same-check prepared public projections', () => {
  it('builds once and revalidates the complete serialized result on every reuse', () => {
    const build = vi.fn(fixture), validate = vi.fn((assets) => expect(assets).toEqual(fixture()));
    expect(preparedProjection('historical', root, key, build, validate)).toEqual(fixture());
    expect(preparedProjection('historical', root, key, build, validate)).toEqual(fixture());
    expect(build).toHaveBeenCalledTimes(1);
    expect(validate).toHaveBeenCalledTimes(2);
    expect(() => preparedProjection('historical', root, 'b'.repeat(64), build, validate)).toThrow('inputs differ');
  });
  it('fails closed on incomplete, altered or symlinked prepared assets', () => {
    preparedProjection('historical', root, key, fixture, () => {});
    const hash = createHash('sha256').update(fixture().values().next().value!).digest('hex');
    const file = join(root, 'historical', `${hash}.json`), original = readFileSync(file);
    writeFileSync(file, original.toString().replace('Original', 'Modified'));
    expect(() => preparedProjection('historical', root, key, fixture, () => {})).toThrow('hash/bytes');
    rmSync(file); writeFileSync(join(root, 'elsewhere'), original); symlinkSync(join(root, 'elsewhere'), file);
    expect(() => preparedProjection('historical', root, key, fixture, () => {})).toThrow('regular file');
    rmSync(join(root, 'historical/receipt.json'));
    expect(() => preparedProjection('historical', root, key, fixture, () => {})).toThrow('Incomplete');
  });
  it('does not save incomplete generation, failed validation or private/unsafe paths', () => {
    expect(() => preparedProjection('historical', root, key, () => { throw new Error('source failure'); }, () => {})).toThrow('source failure');
    expect(() => preparedProjection('historical', root, key, fixture, () => { throw new Error('schema'); })).toThrow('schema');
    for (const path of ['data/historical_evidence/manifest.json', 'catalog/../private.json', 'https://example.invalid/file.json']) {
      expect(() => preparedProjection('historical', root, key, () => new Map([[path, '{}']]), () => {})).toThrow();
    }
    expect(existsSync(join(root, 'historical'))).toBe(false);
  });
  it('hashes actual source bytes, new files and commits rather than trusting mtimes', () => {
    inputs();
    const before = projectionFingerprint(root), path = join(root, 'data/source.bin'), stats = statSync(path);
    writeFileSync(path, 'change'); utimesSync(path, stats.atime, stats.mtime);
    expect(projectionFingerprint(root)).not.toBe(before);
    writeFileSync(path, 'source');
    expect(projectionFingerprint(root)).toBe(before);
    mkdirSync(join(root, 'scripts')); writeFileSync(join(root, 'scripts/new.ts'), 'changed extractor');
    expect(projectionFingerprint(root)).not.toBe(before);
    rmSync(join(root, 'scripts'), { recursive: true });
    execFileSync('git', ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '--allow-empty', '-qm', 'Different commit'], { cwd: root });
    expect(projectionFingerprint(root)).not.toBe(before);
  });
  it('stops the check pipeline when inputs change between commands', () => {
    inputs();
    writeFileSync(join(root, 'package.json'), '{"type":"module"}');
    mkdirSync(join(root, 'scripts'));
    for (const file of ['check.ts', 'prepared_projection.ts']) copyFileSync(join(projectRoot, 'scripts', file), join(root, 'scripts', file));
    symlinkSync(join(projectRoot, 'node_modules'), join(root, 'node_modules'), 'junction');
    const cli = join(root, 'fixture-npm.cjs');
    writeFileSync(cli, "const fs = require('node:fs'); fs.appendFileSync('commands.log', process.argv.at(-1) + '\\n'); fs.writeFileSync('data/source.bin', 'changed');");
    let error: any;
    try { execFileSync(process.execPath, ['--experimental-strip-types', join(root, 'scripts/check.ts')], { cwd: root, env: { ...process.env, npm_execpath: cli }, stdio: 'pipe' }); }
    catch (caught) { error = caught; }
    expect(error?.status).toBe(1);
    expect(error.stderr.toString()).toContain('Check inputs changed');
    expect(readFileSync(join(root, 'commands.log'), 'utf8')).toBe('test\n');
  });
});

describe('browser build provenance', () => {
  it('requires a complete, current production tree and retains its actual subdirectory', () => {
    inputs();
    expect(() => verifiedBuild(root)).toThrow('No verified production build');
    mkdirSync(join(root, 'dist')); writeFileSync(join(root, 'dist/index.html'), '<html>Built</html>');
    expect(() => recordBuild(root, '/token3/', key)).toThrow('Check inputs changed');
    recordBuild(root, '/token3/');
    expect(verifiedBuild(root)).toEqual({ base: '/token3/' });
    writeFileSync(join(root, 'dist/index.html'), '<html>Other</html>');
    expect(() => verifiedBuild(root)).toThrow('hash/bytes');
    recordBuild(root, '/'); writeFileSync(join(root, 'dist/extra.json'), '{}');
    expect(() => verifiedBuild(root)).toThrow('file set');
    rmSync(join(root, 'dist/extra.json')); writeFileSync(join(root, 'data/source.bin'), 'modified source');
    expect(() => verifiedBuild(root)).toThrow('inputs changed');
  });
});
