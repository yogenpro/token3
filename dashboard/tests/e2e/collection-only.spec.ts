import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

const status = JSON.parse(readFileSync(new URL('../../../data/status.json', import.meta.url), 'utf8'));

test('collection-only providers are visible without inventing comparisons', async ({ page }) => {
  await page.goto('/?view=methodology');
  const row = page.locator('.collector-table tbody tr').filter({ hasText: 'OpenRouter' });
  await expect(row).toHaveCount(1);
  await expect(row).toContainText('Inventory only');
  await expect(row.locator('td').nth(3)).toHaveText('0');
  await expect(row.getByRole('link', { name: 'Official source' })).toHaveAttribute('href', 'https://openrouter.ai/api/v1/models');
  await page.goto('/');
  await expect(page.locator('.provider-cell strong').getByText('OpenRouter', { exact: true })).toHaveCount(0);
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
  await page.goto('/?view=methodology');
  const row = page.locator('.collector-table tbody tr').filter({ hasText: 'Snowflake Cortex' });
  await expect(row).toContainText('Limited source');
  await expect(row).toContainText('billing-guide coverage only');
  await expect(row).toContainText('Inventory only');
});
