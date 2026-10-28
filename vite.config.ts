import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
import { readFileSync, statSync } from 'node:fs';
import { buildDashboardAssets, buildHistoricalAssets } from './scripts/dashboard_projection';
import { historyVersionPath } from './scripts/native_history';
import { publicationMetadata } from './scripts/publication';
import { projectRoot, recordBuild } from './scripts/prepared_projection';

const dataDir = fileURLToPath(new URL('./data', import.meta.url));
// Publish only normalized outputs; never expose collector response bodies.
const files = ['models.json', 'offerings.json', 'latest_prices.json', 'price_history.json', 'price_history.csv', 'changes.json', 'status.json'];
let projected: Map<string, string>;
let projectionVersion = '';
let buildBase = '/';
const sessionStartedAt = new Date().toISOString();
const publication = (development = false) => JSON.stringify(publicationMetadata(JSON.parse(readFileSync(`${dataDir}/status.json`, 'utf8')).last_run_at, process.env, development ? sessionStartedAt : new Date().toISOString(), development));
function catalogAssets() {
  const version = ['provider_inventory.json', historyVersionPath(dataDir), 'offerings.json', 'historical_evidence/manifest.json'].map((file) => statSync(`${dataDir}/${file}`).mtimeMs).join(':');
  if (!projected || version !== projectionVersion) {
    projected = buildDashboardAssets(dataDir);
    for (const [path, body] of buildHistoricalAssets(dataDir)) projected.set(path, body);
    projectionVersion = version;
  }
  return projected;
}

export default defineConfig({
  root: 'dashboard',
  base: process.env.PAGES_BASE_PATH || '/',
  publicDir: false,
  plugins: [
    react(),
    {
      name: 'normalized-dataset',
      configResolved(config) { buildBase = config.base; },
      configureServer(server) {
        // Verify/project once before serving, so first browser requests never
        // wait on a full ledger reconstruction and hit their request timeout.
        // Vitest has its own complete real-corpus projection test. Preparing
        // browser assets for its internal Vite server duplicates that expensive
        // verification before the suite even starts as the archive grows.
        if (server.config.mode !== 'test') catalogAssets();
        server.middlewares.use((req, res, next) => {
          const base = server.config.base;
          const pathname = req.url?.split('?')[0] ?? '';
          const file = pathname.startsWith(base) ? pathname.slice(base.length) : '';
          if (!files.includes(file) && file !== 'publication.json' && !file.startsWith('catalog/')) return next();
          try {
            const source = file === 'publication.json' ? publication(true) : files.includes(file) ? readFileSync(`${dataDir}/${file}`) : catalogAssets().get(file);
            if (source === undefined) return next();
            res.setHeader('Content-Type', file.endsWith('.csv') ? 'text/csv; charset=utf-8' : 'application/json');
            res.setHeader('Cache-Control', 'no-cache');
            res.end(source);
          } catch {
            res.statusCode = 404;
            res.end('Run python3 -m scripts.collect to generate the dataset.');
          }
        });
      },
      generateBundle(_options, bundle) {
        const datasets: Array<[string, string | Uint8Array]> = [['publication.json', publication()],
          ...files.map((file): [string, Uint8Array] => [file, readFileSync(`${dataDir}/${file}`)]), ...catalogAssets()];
        const bytes = datasets.reduce((n, [, source]) => n + Buffer.byteLength(source), 0) +
          Object.values(bundle).reduce((n, entry) => n + Buffer.byteLength(entry.type === 'asset' ? entry.source : entry.code), 0);
        if (bytes > 1_000_000_000) throw new Error('Static site exceeds the GitHub Pages 1 GB limit. Preserve the data and review its delivery format before publishing.');
        for (const [fileName, source] of datasets) this.emitFile({ type: 'asset', fileName, source });
      },
      writeBundle() { recordBuild(projectRoot, buildBase, process.env.TOKEN3_PROJECTION_INPUT_SHA); },
    },
  ],
  build: {
    outDir: '../dist', emptyOutDir: true,
    rollupOptions: { output: { manualChunks: { charts: ['recharts'], validation: ['zod'], react: ['react', 'react-dom'] } } },
  },
  test: { include: ['tests/**/*.test.ts'], environment: 'node' },
});
