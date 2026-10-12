import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';
import type { Model, Offering } from '../../src/lib/data';
import { pageChunks } from '../../src/lib/catalogChunks';
import { readNativeHistory } from '../../../scripts/native_history';
import { fileURLToPath } from 'node:url';
const models: Model[] = JSON.parse(readFileSync(new URL('../../../data/models.json', import.meta.url), 'utf8'));
const offerings: Offering[] = JSON.parse(readFileSync(new URL('../../../data/offerings.json', import.meta.url), 'utf8'));
const inventory = JSON.parse(readFileSync(new URL('../../../data/provider_inventory.json', import.meta.url), 'utf8'));

const audit = async (page: import('@playwright/test').Page) => {
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(result.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
};

test('coverage uses separate denominators and downloads only the small native index', async ({ page }) => {
  const requested: string[] = [];
  page.on('request', (r) => { if (r.url().includes('/catalog/')) requested.push(new URL(r.url()).pathname); });
  await page.goto('/?view=coverage');
  await expect(page.getByRole('heading', { name: 'Coverage, without the guesswork.' })).toBeVisible();
  await expect(page.locator('.coverage-card')).toHaveCount(3);
  await expect(page.locator('.coverage-card').first()).toContainText(`${models.length} canonical models`);
  await expect(page.locator('.coverage-card').first()).toContainText(`${offerings.filter((o) => o.active).length} active offers`);
  await expect(page.locator('.coverage-sources tbody tr')).toHaveCount(inventory.provider_count);
  expect(requested).toEqual(['/catalog/index.json']);
  await audit(page);
  await page.getByRole('button', { name: 'Switch to dark theme' }).click(); await audit(page);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await audit(page);
  await page.screenshot({ path: 'test-results/coverage-mobile.png', fullPage: true });
});

test('large provider browsing loads indexes, then one bounded evidence chunk, never history automatically', async ({ page }) => {
  const response = await page.request.get('/catalog/providers/vertex.json');
  const header = await response.json();
  const requested: string[] = [];
  page.on('request', (r) => { if (r.url().includes('/catalog/')) requested.push(new URL(r.url()).pathname.slice(1)); });
  await page.goto('/?view=providers&provider=vertex');
  await expect(page.locator('.native-table tbody tr')).toHaveCount(25);
  expect(header.record_chunks.every((r: { path: string }) => !requested.includes(r.path))).toBe(true);
  expect(requested).not.toContain('catalog/history/vertex.json');
  await page.locator('.native-table tbody tr').first().getByRole('button').click();
  await expect(page.getByRole('region', { name: 'Selected source record' })).toBeVisible();
  expect(header.record_chunks.filter((r: { path: string }) => requested.includes(r.path))).toHaveLength(1);
  expect(header.record_chunks.every((r: { bytes: number }) => r.bytes <= 512 * 1024)).toBe(true);
  expect(requested).not.toContain('catalog/history/vertex.json');
});

test('large history opens as batches and an event page loads only intersecting chunks', async ({ page }) => {
  // Verified timestamp-only rule copies are no longer a large event feed. Use
  // the largest real catalog batch; do not fabricate events or relax paging.
  const response = await page.request.get('/catalog/changes/catalog.json');
  const manifest = await response.json();
  const batch = manifest.batches.filter((b: { provider: string }) => b.provider === 'vertex')
    .sort((a: { event_count: number }, b: { event_count: number }) => b.event_count - a.event_count)[0];
  expect(batch.event_count).toBeGreaterThan(50);
  expect(batch.chunks.length).toBeGreaterThan(2);
  const expectedChunks = pageChunks(batch.chunks, 1).refs.map((r) => r.path);
  const requested: string[] = [];
  page.on('request', (r) => { if (r.url().includes('/catalog/chunks/')) requested.push(new URL(r.url()).pathname.slice(1)); });
  await page.goto('/?view=changes&feed=catalog');
  await expect(page.locator('.history-batch').first()).toBeVisible();
  expect(requested).toEqual([]);
  await page.getByLabel('Filter native changes by provider').selectOption('vertex');
  await page.getByRole('button', { name: `Open vertex catalog observation batch ${batch.observed_at}`, exact: true }).click();
  await expect(page.locator('.native-change')).toHaveCount(25);
  expect(requested.sort()).toEqual(expectedChunks.sort());
  expect(requested.length).toBeLessThanOrEqual(2);
  await expect(page.getByText('Batches show change-bearing observations', { exact: false })).toBeVisible();
  await audit(page);
});

test('the native rule feed excludes verified as-of copies without exposing warehouse archives', async ({ page }) => {
  const observationEvents = new Set<string>();
  for (const entry of readNativeHistory(fileURLToPath(new URL('../../../data', import.meta.url)))) {
    if (entry.observationOnly) observationEvents.add(`native-${entry.event.id}-rule`);
  }
  expect(observationEvents.size).toBeGreaterThan(0);
  const response = await page.request.get('/catalog/changes/rule.json');
  const manifest = await response.json();
  let count = 0;
  for (const batch of manifest.batches) for (const ref of batch.chunks) {
    const chunk = await (await page.request.get(`/${ref.path}`)).json();
    for (const event of chunk.events) expect(observationEvents.has(event.id)).toBe(false);
    count += chunk.events.length;
  }
  expect(count).toBe(manifest.event_count);
  const requested: string[] = [];
  page.on('request', (r) => requested.push(new URL(r.url()).pathname));
  await page.goto('/?view=changes&feed=rule');
  await expect(page.getByText('Original observations are retained in the warehouse', { exact: false })).toBeVisible();
  await expect(page.getByText('Batches show change-bearing observations', { exact: false })).toBeVisible();
  expect(requested.some((p) => /inventory_history|\/archive\/|\/proofs\//.test(p))).toBe(false);
  await audit(page);
});

test('directories filter current coverage and the sidebar keeps a small honest recent list', async ({ page }) => {
  await page.goto('/?view=models');
  await page.getByLabel('Filter reviewed models by creator').selectOption('Qwen');
  await expect(page.locator('.explorer-table tbody tr')).toHaveCount(models.filter((m) => m.creator === 'Qwen').length);
  await page.getByLabel('Filter reviewed models by family').selectOption('Qwen3');
  await page.getByRole('textbox', { name: 'Search models', exact: true }).fill('3.8');
  await expect(page.locator('.explorer-table tbody tr')).toHaveCount(models.filter((m) => m.creator === 'Qwen' && m.family === 'Qwen3' && m.name.includes('3.8')).length);
  await page.getByRole('button', { name: 'Compare prices', exact: true }).click();
  for (const id of models.slice(0, 9).map((m) => m.id)) await page.getByLabel('SELECT A MODEL').selectOption(id);
  await expect(page.locator('.sidebar-label')).toContainText('RECENT MODELS');
  await expect(page.locator('.watch-item')).toHaveCount(6);
  await page.reload();
  await expect(page.locator('.watch-item')).toHaveCount(6);
  await page.getByLabel('Find a reviewed model').fill('Fable');
  await page.getByLabel('SELECT A MODEL').selectOption('anthropic/claude-fable-5.1');
  await expect(page.getByLabel('SELECT A MODEL').locator('option')).toHaveCount(models.length);
});

test('one-day histories use a compact snapshot and comparison certainty stays visible', async ({ page }) => {
  await page.goto('/?model=anthropic%2Fclaude-fable-5.1');
  await expect(page.getByRole('region', { name: 'First observed price snapshot for Claude Fable 5.1' })).toBeVisible();
  await expect(page.locator('.history-panel .chart-container')).toHaveCount(0);
  await expect(page.locator('.comparison-certainty')).toContainText('Reviewed USD/token quotes');
  await expect(page.locator('.comparison-certainty')).toContainText('context-unverified');
  await expect(page.locator('.model-selection-note')).toContainText('2 billing sources');
  await page.setViewportSize({ width: 390, height: 844 });
  await audit(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/data-fit-comparison-mobile.png', fullPage: true });
});

test('a corrupt index chunk is recoverable and cannot become a shorter catalog or partial export', async ({ page }) => {
  const response = await page.request.get('/catalog/providers/openrouter.json');
  const header = await response.json();
  let corrupt = true;
  await page.route(`**/${header.index_chunks[0].path}`, async (route) => {
    const response = await route.fetch();
    await route.fulfill({ response, body: corrupt ? (await response.text()).replace('label', 'tampered-label') : await response.text() });
  });
  await page.goto('/?view=providers&provider=openrouter');
  await expect(page.getByRole('alert')).toContainText('Catalog chunk and manifest differ');
  await expect(page.locator('.native-table')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Export filtered records' })).toHaveCount(0);
  corrupt = false;
  await page.getByRole('button', { name: 'Retry catalog' }).click();
  await expect(page.locator('.native-table tbody tr')).toHaveCount(25);
  await page.getByRole('button', { name: 'Compare prices', exact: true }).click();
  await expect(page.getByTestId('offering-row').first()).toBeVisible();
});
