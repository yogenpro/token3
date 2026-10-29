import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('Compare keeps EUR, DBU and AI Credit views separate with shareable URLs', async ({ page }) => {
  const nativeRequests: string[] = [];
  page.on('request', (r) => { if (r.url().includes('/catalog/')) nativeRequests.push(r.url()); });
  await page.goto('./?model=openai/gpt-oss-120b');
  await expect(page.getByLabel('Billing basis')).toHaveValue('USD');
  await expect(page.locator('.comparison-table')).toContainText('OpenRouter');
  await expect(page.locator('.comparison-table')).not.toContainText('Databricks');
  await page.getByLabel('Billing basis').selectOption('EUR');
  await expect(page).toHaveURL(/unit=EUR/);
  await expect(page.locator('.comparison-table')).toContainText('Scaleway');
  await expect(page.locator('.comparison-table')).toContainText('OVHcloud');
  await expect(page.locator('.comparison-table')).toContainText('€');
  await expect(page.locator('.comparison-table')).not.toContainText('$');
  await expect(page.locator('.history-panel')).toContainText('EUR / 1M tokens');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export comparison as CSV' }).click();
  const saved = await download;
  const stream = await saved.createReadStream();
  let csv = ''; for await (const part of stream!) csv += part.toString();
  expect(csv).toContain('input_eur_per_million');
  expect(csv).not.toContain('estimated_workload_usd');
  await page.getByLabel('Billing basis').selectOption('DBU');
  await expect(page.locator('.comparison-table')).toContainText('Databricks');
  await expect(page.locator('.comparison-table')).toContainText('DBU');
  await expect(page.locator('.comparison-table')).not.toContainText('$');
  expect(nativeRequests).toEqual([]);
  await page.goto('./?model=zai%2Fglm-5.3&unit=AI_CREDIT');
  await expect(page.getByLabel('Billing basis')).toHaveValue('AI_CREDIT');
  await expect(page.locator('.comparison-table')).toContainText('Snowflake');
  await expect(page.locator('.comparison-table')).toContainText('AI Credits');
  await expect(page.locator('.comparison-table')).not.toContainText('$');
  await expect(page.locator('.history-panel')).toContainText('AI Credits / 1M tokens');
});

test('DeepSeek uses the selected scenario and keeps the UTC/holiday conditions', async ({ page }) => {
  await page.goto('./?model=deepseek%2Fdeepseek-v4.1-flash');
  const row = page.getByTestId('offering-row').filter({ hasText: 'DeepSeek' });
  await expect(row).toHaveCount(1);
  await expect(row).toContainText('peak UTC schedule');
  await expect(row).toContainText('$0.30');
  await page.getByLabel('DeepSeek billing period').selectOption('off-peak');
  await expect(page).toHaveURL(/period=off-peak/);
  await expect(row).toContainText('off-peak UTC schedule');
  await expect(row).toContainText('$0.15');
  await row.getByRole('button', { name: /Details for DeepSeek/ }).click();
  await expect(page.locator('.offering-details')).toContainText('Chinese public holidays');
  await expect(page.locator('.offering-details')).toContainText('01:00 - 04:00');
});

test('billing-basis controls remain accessible on mobile and in dark mode', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('./?model=openai%2Fgpt-oss-120b&unit=EUR');
  await expect(page.locator('.comparison-table')).toContainText('€');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const audit = async () => {
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) }))).toEqual([]);
  };
  await audit();
  await page.getByRole('button', { name: 'Switch to dark theme' }).click();
  await audit();
  await page.screenshot({ path: 'test-results/comparison-eur-mobile.png', fullPage: true });
});
