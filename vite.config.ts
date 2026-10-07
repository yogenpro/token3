import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
import { readFileSync, statSync } from 'node:fs';
import { buildDashboardAssets } from './scripts/dashboard_projection';

const dataDir = fileURLToPath(new URL('./data', import.meta.url));
// Publish only normalized outputs; never expose collector response bodies.
const files = ['models.json', 'offerings.json', 'latest_prices.json', 'price_history.json', 'price_history.csv', 'changes.json', 'status.json'];
let projected: Map<string, string>;
let projectionVersion = '';
function catalogAssets() {
  const version = ['provider_inventory.json', 'inventory_history.jsonl', 'offerings.json'].map((file) => statSync(`${dataDir}/${file}`).mtimeMs).join(':');
  if (!projected || version !== projectionVersion) {
    projected = buildDashboardAssets(dataDir);
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
        server.middlewares.use((req, res, next) => {
          const base = server.config.base;
          const pathname = req.url?.split('?')[0] ?? '';
          const file = pathname.startsWith(base) ? pathname.slice(base.length) : '';
          if (!files.includes(file) && !file.startsWith('catalog/')) return next();
          try {
            const source = files.includes(file) ? readFileSync(`${dataDir}/${file}`) : catalogAssets().get(file);
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
