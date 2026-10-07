import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';
import { datasetSchema } from '../../src/lib/data';
import { defaultWorkload, money, rankOfferings } from '../../src/lib/pricing';
const read = (file: string) => JSON.parse(readFileSync(new URL(`../../../data/${file}.json`, import.meta.url), 'utf8'));
const data = datasetSchema.parse({ models: read('models'), offerings: read('offerings'), prices: read('latest_prices'), history: read('price_history'), changes: read('changes'), status: read('status') });

test('loads official offerings, metadata, sources, and an honest first-day chart', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Same model. Different price.' })).toBeVisible();
  const rows = rankOfferings(data, 'openai/gpt-oss-120b', defaultWorkload);
  await expect(page.getByTestId('offering-row')).toHaveCount(rows.length);
  await expect(page.getByRole('link', { name: 'Official pricing source for Novita' })).toHaveAttribute('href', 'https://api.novita.ai/v3/openai/models');
  await page.getByRole('button', { name: 'Details for Novita standard standard' }).click();
  await expect(page.getByText('PROVIDER MODEL ID', { exact: true })).toBeVisible();
  await expect(page.getByText('OBSERVED AT', { exact: true })).toBeVisible();
  await page.getByLabel('History date range').selectOption('0');
  const days = new Set(data.history.map((p) => p.observed_at.slice(0, 10))).size;
  if (days === 1) await expect(page.getByText('Day one of tracking.', { exact: false })).toBeVisible();
  else await expect(page.locator('.chart-container')).toBeVisible();
  await page.screenshot({ path: 'test-results/dashboard-desktop.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('recalculates totals and keeps the workload in a shareable URL', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('spinbutton', { name: 'Input tokens per request' }).fill('2000');
  await page.getByRole('spinbutton', { name: 'Output tokens per request' }).fill('1000');
  await page.getByRole('spinbutton', { name: 'Number of requests' }).fill('10000');
  await page.getByRole('slider', { name: 'Cache hit rate' }).fill('50');
  const rows = rankOfferings(data, 'openai/gpt-oss-120b', { inputTokens: 2000, outputTokens: 1000, requests: 10000, cacheHitPercent: 50 });
  await expect(page.locator('.stat-card.accent .stat-value')).toContainText(money(rows[0].cost.total));
  await expect(page).toHaveURL(/input=2000.*output=1000.*cache=50.*requests=10000/);
  await page.reload();
  await expect(page.getByRole('spinbutton', { name: 'Input tokens per request' })).toHaveValue('2000');
  await expect(page.getByRole('slider', { name: 'Cache hit rate' })).toHaveValue('50');
});

test('model and tier controls change the table without merging variants', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('SELECT A MODEL').selectOption('meta/llama-3.1-8b-instruct');
  await expect(page.getByTestId('offering-row')).toHaveCount(rankOfferings(data, 'meta/llama-3.1-8b-instruct', defaultWorkload).length);
  await page.getByLabel('Service tier').selectOption('priority');
  await expect(page.getByRole('heading', { name: 'No tracked offerings in this tier' })).toBeVisible();
  await page.getByLabel('Service tier').selectOption('all');
  await expect(page.getByTestId('offering-row')).toHaveCount(rankOfferings(data, 'meta/llama-3.1-8b-instruct', defaultWorkload, 'all').length);
  await page.getByRole('spinbutton', { name: 'Input tokens per request' }).fill('999999');
  await expect(page.getByText('Exceeds context limit').first()).toBeVisible();
  await expect(page.getByText('Lowest estimate', { exact: true })).toHaveCount(0);
});

test('downloads comparison CSV with source and observation timestamp', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByTestId('offering-row').first()).toBeVisible();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export comparison as CSV' }).click();
  const download = await downloaded;
  expect(download.suggestedFilename()).toBe('gpt-oss-120b-comparison.csv');
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  const csv = Buffer.concat(chunks).toString('utf8');
  expect(csv).toContain('observed_at,source_url');
  expect(csv).toContain('https://api.deepinfra.com/models/list');
});

test('history metric and provider toggles work', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Cache read', exact: true }).click();
  await expect(page.locator('.history-controls button.active')).toHaveText('Cache read');
  await page.locator('.chart-legend').getByRole('button', { name: 'Fireworks' }).click();
  await expect(page.locator('.chart-legend').getByRole('button', { name: 'Fireworks' })).toHaveAttribute('aria-pressed', 'false');
  const otherIds = new Set(data.offerings.filter((o) => o.model_id === 'openai/gpt-oss-120b' && o.service_tier === 'standard' && o.provider !== 'fireworks').map((o) => o.id));
  if (!data.history.some((p) => otherIds.has(p.offering_id) && p.cache_read_per_million !== null)) await expect(page.getByText('No published observations for this selection')).toBeVisible();
  await page.locator('.chart-legend').getByRole('button', { name: 'Fireworks' }).click();
  await expect(page.locator('.chart-container')).toBeVisible();
  await page.getByLabel('History date range').selectOption('0');
  await page.getByText('View exact observations').click();
  await expect(page.locator('.history-data table')).toBeVisible();
});

test('explorer and feed filters navigate and distinguish discoveries from cuts', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Model explorer', exact: true }).click();
  await page.getByRole('textbox', { name: 'Search models' }).fill('qwen');
  await expect(page.locator('.explorer-table tbody tr')).toHaveCount(1);
  await page.getByRole('button', { name: 'Compare Qwen3 235B A22B', exact: true }).click();
  await expect(page.getByLabel('SELECT A MODEL')).toHaveValue('qwen/qwen3-235b-a22b-instruct-2507');
  await page.getByRole('button', { name: 'Recent changes', exact: true }).click();
  if (!data.changes.some((c) => c.kind === 'price_changed')) await expect(page.getByText('There are no verified price changes yet.', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Price cuts', exact: true }).click();
  const cuts = data.changes.filter((c) => c.kind === 'price_changed' && typeof c.old === 'number' && typeof c.new === 'number' && c.new < c.old);
  if (!cuts.length) await expect(page.getByRole('heading', { name: 'No matching changes yet' })).toBeVisible();
  else await expect(page.locator('.full-feed .change-item')).toHaveCount(Math.min(cuts.length, 20));
  await page.getByRole('button', { name: 'Offerings', exact: true }).click();
  await page.getByLabel('Filter changes by model').selectOption('openai/gpt-oss-20b');
  await expect(page.locator('.full-feed .change-item')).toHaveCount(Math.min(data.changes.filter((c) => c.model_id === 'openai/gpt-oss-20b' && c.kind !== 'price_changed').length, 20));
});

test('shows multiple failed collectors explicitly', async ({ page }) => {
  await page.route('**/status.json', async (route) => {
    const next = structuredClone(data.status);
    next.providers[0].state = 'error'; next.providers[0].error = 'Source unavailable';
    next.providers[1].state = 'error'; next.providers[1].error = 'Second source unavailable';
    await route.fulfill({ json: next });
  });
  await page.goto('/');
  await expect(page.getByText('Some collectors have failed', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Check sources' }).click();
  const first = page.locator('.collector-table tbody tr').filter({ has: page.getByText(data.status.providers[0].name, { exact: true }) });
  const second = page.locator('.collector-table tbody tr').filter({ has: page.getByText(data.status.providers[1].name, { exact: true }) });
  await expect(first.getByText('Failed · retained', { exact: true })).toBeVisible();
  await expect(first.getByText('Source unavailable', { exact: true })).toBeVisible();
  await expect(second.getByText('Failed · retained', { exact: true })).toBeVisible();
  await expect(second.getByText('Second source unavailable', { exact: true })).toBeVisible();
});

test('shows a recoverable error for a missing dataset', async ({ page }) => {
  await page.route('**/offerings.json', (route) => route.fulfill({ status: 503, body: 'Unavailable' }));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Unable to load offerings.json');
  await page.unroute('**/offerings.json');
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(page.getByTestId('offering-row').first()).toBeVisible();
});

test('theme toggle persists and refresh only checks the published dataset', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Switch to dark theme' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.getByTestId('offering-row').first()).toBeVisible();
  await page.getByRole('button', { name: 'Refresh published dataset' }).click();
  await expect(page.getByRole('status')).toContainText('Live collection runs separately');
  await page.screenshot({ path: 'test-results/dashboard-dark.png', fullPage: true });
});

test('mobile layout stays within the viewport and all views remain accessible', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByTestId('offering-row').first()).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: 'test-results/dashboard-mobile.png', fullPage: true });
  await page.getByRole('button', { name: 'Methodology', exact: true }).click();
  await expect(page.getByRole('heading', { name: `Collector health ${data.status.providers.length}` })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Download reviewed dataset' })).toBeVisible();
});

test('multi-day history and price cut/increase feeds work with test-only observations', async ({ page }) => {
  // Synthetic observations live ONLY in this intercepted browser fixture, never data/.
  const sample = rankOfferings(data, 'openai/gpt-oss-120b', defaultWorkload).slice(0, 2);
  const previousTime = new Date(Date.parse(sample[0].price.observed_at) - 86400000).toISOString();
  const oldHistory = sample.map(({ price }, i) => ({ ...price, observed_at: previousTime, input_per_million: price.input_per_million * (i === 0 ? 2 : 0.5) }));
  const history = [...oldHistory, ...data.history];
  const events = sample.map(({ offering, price }, i) => ({ id: `fixture-${i}`, kind: 'price_changed', offering_id: offering.id, model_id: offering.model_id, provider: offering.provider, observed_at: price.observed_at, field: 'input_per_million', old: oldHistory[i].input_per_million, new: price.input_per_million, change_pct: i === 0 ? -50 : 100 }));
  await page.route('**/price_history.json', (route) => route.fulfill({ json: history }));
  await page.route('**/changes.json', (route) => route.fulfill({ json: events }));
  await page.route('**/status.json', (route) => route.fulfill({ json: { ...data.status, observation_count: history.length } }));
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await page.getByLabel('History date range').selectOption('0');
  // Newly added providers may have only one real observation (a dot, not a
  // nonzero-length path). Assert the deliberately multi-day fixture series.
  await expect(page.locator(`.recharts-line-curve[name="${sample[0].offering.id}"]`)).toBeVisible();
  await expect(page.getByText('Day one of tracking.', { exact: false })).toHaveCount(0);
  await page.getByRole('button', { name: 'Recent changes', exact: true }).click();
  await expect(page.getByText('-50%', { exact: true })).toBeVisible();
  await expect(page.getByText('+100%', { exact: true })).toBeVisible();
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(result.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
  await page.getByRole('button', { name: 'Price cuts', exact: true }).click();
  await expect(page.locator('.full-feed .change-item')).toHaveCount(1);
  await page.getByRole('button', { name: 'Price increases', exact: true }).click();
  await expect(page.locator('.full-feed .change-item')).toHaveCount(1);
});

test('core views pass automated WCAG 2.1 AA checks in light and dark themes', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(page.getByTestId('offering-row').first()).toBeVisible();
  const audit = async () => {
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(result.violations.map((v) => ({ id: v.id, impact: v.impact, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
  };
  await audit();
  await page.getByRole('button', { name: 'Switch to dark theme' }).click();
  await audit();
  for (const name of ['Model explorer', 'Recent changes', 'Methodology']) {
    await page.getByRole('button', { name, exact: true }).click();
    await audit();
  }
});
