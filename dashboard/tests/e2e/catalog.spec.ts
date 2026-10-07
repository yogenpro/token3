import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';

const inventory = JSON.parse(readFileSync(new URL('../../../data/provider_inventory.json', import.meta.url), 'utf8'));
const catalog = (id: string) => JSON.parse(readFileSync(new URL(`../../../data/provider_catalogs/${id}.json`, import.meta.url), 'utf8'));

test('the comparison landing page does not download the warehouse', async ({ page }) => {
  const assets: string[] = [];
  page.on('request', (request) => { if (new URL(request.url()).pathname.includes('/catalog/')) assets.push(request.url()); });
  await page.goto('/');
  await expect(page.getByTestId('offering-row').first()).toBeVisible();
  expect(assets).toEqual([]);
  await page.getByRole('button', { name: 'Providers', exact: true }).click();
  await expect(page.locator('.provider-card')).toHaveCount(inventory.provider_count);
  expect(assets.some((url) => url.endsWith('catalog/index.json'))).toBe(true);
  expect(assets.some((url) => url.includes('catalog/providers/'))).toBe(false);
});

test('reviewed offers expose commercial access and link to their native provider catalog', async ({ page }) => {
  await page.goto('/?model=openai/gpt-5.4');
  await expect(page.getByTestId('offering-row').first()).toBeVisible();
  await expect(page.locator('.comparison-access').filter({ hasText: 'Cloud access' }).first()).toBeVisible();
  await expect(page.locator('.comparison-access').filter({ hasText: 'Direct API access' }).first()).toBeVisible();
  const row = page.getByTestId('offering-row').filter({ hasText: 'OpenAI API' }).first();
  await row.getByRole('button', { name: /Details for OpenAI API/ }).click();
  await page.getByRole('button', { name: 'Explore native provider catalog' }).click();
  await expect(page).toHaveURL(/view=providers&provider=openai/);
  await expect(page.getByRole('heading', { name: 'OpenAI API', exact: true })).toBeVisible();
});

test('provider search and access filters separate gateway offers', async ({ page }) => {
  await page.goto('/?view=providers');
  await expect(page.locator('.provider-card')).toHaveCount(inventory.provider_count);
  await page.getByLabel('Filter providers by access type').selectOption('Gateway');
  await expect(page.locator('.provider-card')).toHaveCount(3);
  await page.getByLabel('Search providers').fill('openrouter');
  await expect(page.locator('.provider-card')).toHaveCount(1);
  await page.getByRole('button', { name: 'Explore OpenRouter', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'OpenRouter', exact: true })).toBeVisible();
  await expect(page.locator('.native-table tbody tr')).toHaveCount(25);
  await expect(page.getByLabel('Search native catalog')).toBeVisible();
  await expect(page).toHaveURL(/provider=openrouter/);
});

test('native record deep links preserve unknown currency and source rules', async ({ page }) => {
  const record = catalog('ovhcloud').records[0];
  await page.goto(`/?view=providers&provider=ovhcloud&record=${record.id}`);
  const detail = page.getByRole('region', { name: 'Selected source record' });
  await expect(detail).toBeVisible();
  await expect(detail).toContainText('Currency unverified');
  await expect(detail).toContainText('Unreviewed billing · not compared');
  await expect(detail.locator('.source-json').first()).toContainText('native_rates');
  await expect(page.getByText('Currency is not stated in the selected catalog.', { exact: false })).toBeVisible();
  await page.reload();
  await expect(detail).toBeVisible();
  await page.getByRole('button', { name: 'Close record' }).click();
  await expect(page).not.toHaveURL(/record=/);
});

test('catalog filters, pagination, and native export use all matching records', async ({ page }) => {
  await page.goto('/?view=providers&provider=openrouter');
  await expect(page.locator('.native-table tbody tr')).toHaveCount(25);
  await page.locator('.native-catalog').getByRole('button', { name: 'Next page' }).click();
  await expect(page.locator('.native-catalog .catalog-pagination')).toContainText('Page 2');
  await page.getByLabel('Search native catalog').fill('gpt-oss-120b');
  await expect(page.locator('.native-catalog .catalog-pagination')).toContainText('Page 1');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export filtered records' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('openrouter-native-catalog.json');
  const stream = await download.createReadStream(); const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  const exported = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  expect(exported.provider).toBe('openrouter');
  expect(exported.records.length).toBeGreaterThan(0);
  expect(exported.records.every((r: any) => r.comparison_eligible === false)).toBe(true);
});

test('collected models stay provider-scoped and navigate to source evidence', async ({ page }) => {
  await page.goto('/?view=models&directory=collected');
  await expect(page.getByLabel('Search collected models')).toBeVisible();
  await page.getByLabel('Filter collected models by provider').selectOption('huggingface');
  await page.getByLabel('Search collected models').fill('gpt-oss-120b');
  await expect(page.locator('.collected-models tbody tr').first()).toBeVisible();
  await expect(page.locator('.collected-models tbody tr').first()).toContainText('Not compared');
  await page.locator('.collected-models tbody tr').first().getByRole('button').click();
  await expect(page).toHaveURL(/provider=huggingface.*record=/);
  await expect(page.getByRole('region', { name: 'Selected source record' })).toBeVisible();
  await expect(page.getByTestId('offering-row')).toHaveCount(0);
});

test('native changes separate prices, rules, and source absence', async ({ page }) => {
  await page.goto('/?view=changes&feed=price');
  await expect(page.getByLabel('Search native changes')).toBeVisible();
  await page.getByLabel('Filter native changes by provider').selectOption('openrouter');
  await expect(page.locator('.native-change').first()).toContainText('Published native amount changed');
  await expect(page.locator('.native-change').first()).toContainText('not a reviewed comparison');
  await page.getByRole('button', { name: 'Billing rules', exact: true }).click();
  await expect(page).toHaveURL(/feed=rule/);
  await expect(page.getByLabel('Search native changes')).toBeVisible();
  await page.getByRole('button', { name: 'Catalog changes', exact: true }).click();
  await page.getByLabel('Filter native changes by provider').selectOption('huggingface');
  await page.getByLabel('Search native changes').fill('No longer');
  await expect(page.locator('.native-change').first()).toContainText('Source absence is not proof');
});

test('lazy asset failures are recoverable and never erase reviewed quotes', async ({ page }) => {
  let blocked = true;
  await page.route('**/catalog/providers/openrouter.json', (route) => blocked ? route.fulfill({ status: 503, body: '{}' }) : route.continue());
  await page.goto('/?view=providers&provider=openrouter');
  await expect(page.getByRole('alert')).toContainText('Unable to load catalog');
  blocked = false;
  await page.getByRole('button', { name: 'Retry catalog' }).click();
  await expect(page.locator('.native-table tbody tr')).toHaveCount(25);
  await page.getByRole('button', { name: 'Compare prices', exact: true }).click();
  await expect(page.getByTestId('offering-row').first()).toBeVisible();
});

test('new catalog surfaces pass AA accessibility in both themes and fit mobile', async ({ page }) => {
  const audit = async () => {
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(result.violations.map((v) => ({ id: v.id, impact: v.impact, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
  };
  await page.goto('/?view=providers');
  await expect(page.locator('.provider-card')).toHaveCount(inventory.provider_count);
  await audit();
  await page.getByRole('button', { name: 'Switch to dark theme' }).click(); await audit();
  await page.getByRole('button', { name: 'Explore OVHcloud AI Endpoints', exact: true }).click();
  await expect(page.locator('.native-table tbody tr').first()).toBeVisible(); await audit();
  await page.locator('.native-table tbody tr').first().getByRole('button').click();
  await expect(page.getByRole('region', { name: 'Selected source record' })).toBeVisible(); await audit();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  await page.screenshot({ path: 'test-results/catalog-provider-mobile.png', fullPage: true });
  await page.getByRole('button', { name: 'Model explorer', exact: true }).click();
  await page.getByRole('button', { name: 'Collected listings', exact: true }).click();
  await expect(page.locator('.collected-models tbody tr').first()).toBeVisible(); await audit();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  await page.getByRole('button', { name: 'Recent changes', exact: true }).click();
  await page.getByRole('button', { name: 'Native price amounts', exact: true }).click();
  await expect(page.locator('.native-change').first()).toBeVisible(); await audit();
});
