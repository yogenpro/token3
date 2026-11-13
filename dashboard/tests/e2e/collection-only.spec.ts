import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

const status = JSON.parse(readFileSync(new URL('../../../data/status.json', import.meta.url), 'utf8'));

test('paused document-only collection stays visible without re-enabling Together comparisons', async ({ page }) => {
  await page.goto('./?view=methodology');
  const row = page.locator('.collector-table tbody tr').filter({ hasText: 'Together AI' });
  await expect(row).toHaveCount(1);
  await expect(row).toContainText('Inventory only');
  await expect(row.locator('td').nth(3)).toHaveText('Comparisons paused · docs inventory only');
  await expect(row.getByRole('link', { name: 'Official source' })).toHaveAttribute('href', status.providers.find((p: { id: string }) => p.id === 'together').source_url);
  await page.goto('./');
  await expect(page.locator('.provider-cell strong').getByText('Together AI', { exact: true })).toHaveCount(0);
});

test('an unavailable optional consumption table is visibly limited, not full coverage', async ({ page }) => {
  const limited = structuredClone(status);
  const provider = limited.providers.find((p: { id: string }) => p.id === 'snowflake');
  provider.state = 'ok';
  provider.last_success_at = new Date().toISOString();
  provider.coverage_state = 'limited';
  provider.collection_scope = 'inventory_only';
  provider.fallback_reason = 'Model-rate PDF unavailable; billing-guide coverage only.';
  await page.route('**/status.json', (route) => route.fulfill({ json: limited }));
  await page.goto('./?view=methodology');
  const row = page.locator('.collector-table tbody tr').filter({ hasText: 'Snowflake Cortex' });
  await expect(row).toContainText('Limited source');
  await expect(row).toContainText('billing-guide coverage only');
  await expect(row).toContainText('Inventory only');
});

test('stopped Castform collection is explicit and retained token prices cannot enter comparisons', async ({ page }) => {
  await page.goto('./?view=methodology');
  const row = page.locator('.collector-table tbody tr').filter({ hasText: 'Castform' });
  await expect(row).toContainText('Collection stopped · retained');
  await expect(row.locator('td').nth(3)).toHaveText('Comparisons paused · collection stopped');
  const priorError = status.providers.find((p: { id: string }) => p.id === 'castform').error;
  if (priorError) await expect(row).toContainText(priorError);
  await page.goto('./?model=qwen%2Fqwen3.5-4b');
  await expect(page.getByRole('note').filter({ hasText: 'Castform collection and current comparisons are stopped by operator decision' })).toBeVisible();
  await expect(page.getByTestId('offering-row')).toHaveCount(0);
  await page.goto('./?model=openai%2Fgpt-5.4');
  await expect(page.getByTestId('offering-row').filter({ hasText: 'Castform' })).toHaveCount(0);
  await expect(page.getByTestId('offering-row').filter({ hasText: 'OpenAI API' }).first()).toBeVisible();
});

test('Arcee exclusions are exact, preserve other offers and explain the operator decision', async ({ page }) => {
  await page.goto('./?model=zai%2Fglm-5.2');
  await expect(page.getByRole('note').filter({ hasText: 'Possible retirement is unconfirmed' })).toBeVisible();
  await expect(page.getByTestId('offering-row').filter({ hasText: 'Arcee AI' })).toHaveCount(0);
  await expect(page.getByTestId('offering-row').filter({ hasText: 'Z.ai' })).toBeVisible();
  await page.goto('./?model=zai%2Fglm-5.3-flash');
  await expect(page.getByTestId('offering-row').filter({ hasText: 'Arcee AI' })).toBeVisible();
});
