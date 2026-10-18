import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';
import { datasetSchema } from '../../src/lib/data';
import { comparisonProviders, reviewedChangeGroups, workloadPriceMap } from '../../src/lib/insights';
import { defaultWorkload, money } from '../../src/lib/pricing';
const read = (name: string) => JSON.parse(readFileSync(new URL(`../../../data/${name}.json`, import.meta.url), 'utf8'));
const data = datasetSchema.parse({ models: read('models'), offerings: read('offerings'), prices: read('latest_prices'), history: read('price_history'), changes: read('changes'), status: read('status') });
async function audit(page: import('@playwright/test').Page) {
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(result.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
}

test('freshness, grouped digest and explicit Together pause need no native assets', async ({ page }) => {
  const native: string[] = [];
  page.on('request', (r) => { if (r.url().includes('/catalog/')) native.push(r.url()); });
  await page.goto('/');
  const freshness = page.getByRole('region', { name: 'Published snapshot freshness' });
  await expect(freshness.getByText('Collected through', { exact: true })).toBeVisible();
  await expect(freshness.locator('time').first()).toHaveAttribute('datetime', data.status.last_run_at);
  await expect(freshness).toContainText('A new build does not make old quotes fresh');
  await expect(page.locator('.digest-card')).toHaveCount(Math.min(reviewedChangeGroups(data.changes).length, 3));
  await expect(page.locator('.notice').filter({ hasText: 'Together comparisons are paused' })).toBeVisible();
  await expect(page.locator('.comparison-table').getByText('Together AI', { exact: true })).toHaveCount(0);
  expect(native).toEqual([]);
  await audit(page);
});

test('workload map searches all reviewed models, recalculates and remains accessible on mobile/dark', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Explore price map', exact: true }).click();
  await page.getByRole('searchbox', { name: 'Filter reviewed price map' }).fill('DeepSeek V4.1 Flash');
  await expect(page.locator('.price-map-table tbody tr')).toHaveCount(1);
  await expect(page.locator('.price-map-table thead')).not.toContainText('Together AI');
  const column = comparisonProviders(data, new Set(['deepseek/deepseek-v4.1-flash'])).indexOf('vercel') + 1;
  const cell = page.locator('.price-map-table tbody tr').first().locator('th, td').nth(column);
  let row = workloadPriceMap(data, defaultWorkload, 'standard', 'all', 'DeepSeek V4.1 Flash')[0].cells.get('vercel')![0];
  await expect(cell).toContainText(money(row.cost.total));
  await page.getByRole('spinbutton', { name: 'Number of requests' }).fill('1');
  row = workloadPriceMap(data, { ...defaultWorkload, requests: 1 }, 'standard', 'all', 'DeepSeek V4.1 Flash')[0].cells.get('vercel')![0];
  await expect(cell).toContainText(money(row.cost.total));
  await expect(cell).toContainText('standard');
  await audit(page);
  await page.getByRole('button', { name: 'Switch to dark theme' }).click();
  await audit(page);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await audit(page);
  await page.screenshot({ path: 'test-results/workload-price-map-mobile-dark.png', fullPage: true });
});

test('mismatched publication metadata fails closed and can be retried', async ({ page }) => {
  await page.route('**/publication.json', (route) => route.fulfill({ json: { schema_version: 1, built_at: '2026-10-19T00:00:00Z', data_collected_at: '2026-10-01T00:00:00Z', commit_sha: null, mode: 'build' } }));
  await page.goto('/');
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByTestId('offering-row')).toHaveCount(0);
  await page.unroute('**/publication.json');
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(page.getByTestId('offering-row').first()).toBeVisible();
});

test('DeepSeek official evidence stays separate from gateway comparisons', async ({ page }) => {
  await page.goto('/?view=providers&provider=deepseek');
  await expect(page.getByText('Official DeepSeek API evidence, separate from gateway quotes.', { exact: false })).toBeVisible();
  await expect(page.locator('.native-table tbody tr').first()).toBeVisible();
  await expect(page.locator('.native-table')).toContainText('Not compared');
  await page.locator('.native-table tbody tr').filter({ has: page.getByText('MODEL VERSION', { exact: true }) }).getByRole('button').click();
  const evidence = page.getByRole('region', { name: 'Selected source record' });
  await evidence.getByText('Original billing expressions', { exact: true }).click();
  await expect(evidence).toContainText('DeepSeek-V4.1-Flash-1017');
});
