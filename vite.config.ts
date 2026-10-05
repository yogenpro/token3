import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
import { readFileSync } from 'node:fs';

const dataDir = fileURLToPath(new URL('./data', import.meta.url));
// Publish only normalized outputs; never expose collector response bodies.
const files = ['models.json', 'offerings.json', 'latest_prices.json', 'price_history.json', 'price_history.csv', 'changes.json', 'status.json'];

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
          const file = req.url?.split('?')[0].split('/').pop();
          if (!file || !files.includes(file)) return next();
          try {
            res.setHeader('Content-Type', file.endsWith('.csv') ? 'text/csv; charset=utf-8' : 'application/json');
            res.setHeader('Cache-Control', 'no-cache');
            res.end(readFileSync(`${dataDir}/${file}`));
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
      },
    },
  ],
  build: {
    outDir: '../dist', emptyOutDir: true,
    rollupOptions: { output: { manualChunks: { charts: ['recharts'], validation: ['zod'], react: ['react', 'react-dom'] } } },
  },
  test: { include: ['tests/**/*.test.ts'], environment: 'node' },
});
