import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('historical overview loads only summary metadata and all provider groups', async ({ page }) => {
  const paths: string[] = [];
  page.on('request', (r) => { const path = new URL(r.url()).pathname; if (path.includes('/catalog/')) paths.push(path); });
  await page.goto('/?view=historical');
  await expect(page.locator('.provider-card')).toHaveCount(26);
  expect([...new Set(paths.filter((p) => p.includes('historical/')))]).toEqual(['/catalog/historical/index.json']);
  expect(paths.some((p) => p.includes('/chunks/'))).toBe(false);
  await expect(page.getByRole('note').first()).toContainText('excluded from comparisons');
  await page.getByLabel('Search historical providers').fill('together');
  await expect(page.locator('.provider-card')).toHaveCount(1);
  await page.getByRole('button', { name: 'Historical evidence for Together AI' }).click();
  await expect(page.getByText('Free documents only.', { exact: false })).toBeVisible();
});

test('historical IDs, dates, expressions and provenance survive deep links', async ({ page }) => {
  await page.goto('/?view=historical&provider=deepinfra');
  await expect(page.locator('.historical-records tbody tr')).toHaveCount(25);
  await page.getByLabel('Search historical assertions').fill('llama');
  await page.locator('.historical-records tbody tr').first().getByRole('button').click();
  const detail = page.getByRole('region', { name: 'Selected historical evidence' });
  await expect(detail).toBeVisible();
  await expect(detail).toContainText('Unreviewed historical · not compared');
  await expect(detail).toContainText('Archive capture');
  await expect(detail).toContainText('Reported effective');
  await expect(page.getByLabel('Historical source expressions')).toBeVisible();
  await detail.getByText('Scope and provenance', { exact: true }).click();
  await expect(page.getByLabel('Historical scope and provenance')).toContainText('source_sha256');
  await expect(page).toHaveURL(/view=historical&provider=deepinfra&record=assertion-/);
  await page.reload(); await expect(detail).toBeVisible();
  await page.getByRole('button', { name: 'Close evidence' }).click();
  await expect(page).not.toHaveURL(/record=/);
  await page.getByLabel('Date basis', { exact: true }).selectOption('effective');
  await page.getByLabel('From', { exact: true }).fill('2020-01-01');
  await expect(page.getByRole('heading', { name: 'No matching historical assertions' })).toBeVisible();
});

test('historical exports cover the entire filtered index and retain capture provenance', async ({ page }) => {
  await page.goto('/?view=historical&provider=openrouter');
  await expect(page.locator('.historical-records tbody tr')).toHaveCount(25);
  await page.getByLabel('Search historical assertions').fill('llama');
  await expect(page.locator('.historical-records tbody tr').first()).toContainText(/llama/i);
  const totalText = await page.locator('.historical-records .catalog-pagination').textContent();
  const total = Number(totalText!.match(/of ([\d,]+)/)![1].replaceAll(',', ''));
  expect(total).toBeGreaterThan(25);
  const pending = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export filtered historical evidence', exact: true }).click();
  const download = await pending;
  const stream = await download.createReadStream(); const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  expect(data.assertions).toHaveLength(total);
  expect(data.assertions.every((r: any) => r.comparison_eligible === false && r.review_status === 'unreviewed_historical')).toBe(true);
  expect(data.captures.every((c: any) => c.source_sha256 && c.retrieved_at)).toBe(true);
  expect(data).not.toHaveProperty('prices');
});

test('corrupt historical chunks fail visibly, retry completely and do not become empty results', async ({ page }) => {
  let blocked = true;
  await page.route('**/catalog/chunks/*.json', (route) => blocked ? route.fulfill({ json: { schema_version: 1, records: [] } }) : route.continue());
  await page.goto('/?view=historical&provider=openrouter');
  await expect(page.getByRole('alert')).toContainText('Catalog chunk and manifest differ');
  await expect(page.getByRole('heading', { name: 'No matching historical assertions' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Export filtered historical evidence', exact: true })).toHaveCount(0);
  blocked = false; await page.getByRole('button', { name: 'Retry catalog' }).click();
  await expect(page.locator('.historical-records tbody tr')).toHaveCount(25);
  await page.getByRole('button', { name: 'Load lookup checks' }).click();
  await expect(page.locator('.historical-checks tbody tr').first()).toBeVisible();
  await expect(page.locator('.historical-checks')).toContainText('No HTTP response recorded');
});

test('historical views are accessible in both themes and fit mobile', async ({ page }) => {
  const audit = async () => {
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(result.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
  };
  await page.goto('/?view=historical');
  await expect(page.locator('.provider-card')).toHaveCount(26); await audit();
  await page.getByRole('button', { name: 'Switch to dark theme' }).click(); await audit();
  await page.getByRole('button', { name: 'Historical evidence for Amazon Bedrock' }).click();
  await expect(page.locator('.historical-records tbody tr')).toHaveCount(25); await audit();
  await page.locator('.historical-records tbody tr').first().getByRole('button').click();
  await expect(page.getByRole('region', { name: 'Selected historical evidence' })).toBeVisible(); await audit();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  await page.screenshot({ path: 'test-results/historical-mobile.png', fullPage: true });
});
