import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
import { readFileSync, statSync } from 'node:fs';
import { buildDashboardAssets, buildHistoricalAssets } from './scripts/dashboard_projection';
import { historyVersionPath } from './scripts/native_history';
import { publicationMetadata } from './scripts/publication';

const dataDir = fileURLToPath(new URL('./data', import.meta.url));
// Publish only normalized outputs; never expose collector response bodies.
const files = ['models.json', 'offerings.json', 'latest_prices.json', 'price_history.json', 'price_history.csv', 'changes.json', 'status.json'];
let projected: Map<string, string>;
let projectionVersion = '';
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
      configureServer(server) {
        // Verify/project once before serving, so first browser requests never
        // wait on a full ledger reconstruction and hit their request timeout.
        catalogAssets();
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
      generateBundle() {
        this.emitFile({ type: 'asset', fileName: 'publication.json', source: publication() });
        for (const file of files) {
          this.emitFile({ type: 'asset', fileName: file, source: readFileSync(`${dataDir}/${file}`) });
        }
        for (const [fileName, source] of catalogAssets()) this.emitFile({ type: 'asset', fileName, source });
      },
    },
  ],
  build: {
    outDir: '../dist', emptyOutDir: true,
    rollupOptions: { output: { manualChunks: { charts: ['recharts'], validation: ['zod'], react: ['react', 'react-dom'] } } },
  },
  test: { include: ['tests/**/*.test.ts'], environment: 'node' },
});
