import { defineConfig, devices } from '@playwright/test';

const base = process.env.TOKEN3_TEST_BASE_PATH ?? '/';
export default defineConfig({
  testDir: './dashboard/tests/e2e',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: {
    baseURL: `http://127.0.0.1:4173${base}`, trace: 'retain-on-failure',
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : {},
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1050 } } }],
  webServer: {
    command: 'npm run preview -- --port 4173 --strictPort --host 127.0.0.1',
    url: `http://127.0.0.1:4173${base}`,
    reuseExistingServer: false,
    timeout: 60000,
  },
});
