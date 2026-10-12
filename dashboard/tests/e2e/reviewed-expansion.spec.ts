import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const selected = [
  'anthropic/claude-opus-5.5', 'anthropic/claude-fable-5', 'anthropic/claude-fable-5.1',
  'openai/gpt-6.1-sol', 'openai/gpt-6-luna', 'openai/gpt-6-astra',
  'google/gemini-3.1-pro-preview', 'google/gemma-4-31b-it', 'qwen/qwen3.8-27b',
  'deepseek/deepseek-v4.1-flash', 'zai/glm-5.3', 'minimax/minimax-m3',
  'moonshotai/kimi-k3', 'nvidia/nemotron-3.5-lightning',
  'meta/llama-4-maverick-17b-128e-instruct', 'xai/grok-4.7',
];

test('requested models and additional recent families have reviewed comparisons', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByLabel('SELECT A MODEL').locator('option')).toHaveCount(45);
  for (const id of selected) {
    await page.getByLabel('SELECT A MODEL').selectOption(id);
    await expect(page.getByTestId('offering-row').first()).toBeVisible();
    await expect(page.locator('.stat-card.accent .stat-value')).not.toContainText('—');
    await expect(page.locator('.provider-cell strong').getByText('Vercel AI Gateway', { exact: true }).first()).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Provider comparison' })).toBeVisible();
  }
  await page.getByLabel('SELECT A MODEL').selectOption('anthropic/claude-mythos-5.1');
  await expect(page.locator('.model-description')).toContainText('Limited availability');
  await expect(page.locator('.provider-cell strong').getByText('Anthropic API', { exact: true })).toBeVisible();
});

test('Haiku 5.5 fully cached requests use the correct 100K prompt band', async ({ page }) => {
  await page.goto('/?model=anthropic%2Fclaude-haiku-5.5');
  await page.getByRole('spinbutton', { name: 'Number of requests' }).fill('1');
  await page.getByRole('spinbutton', { name: 'Output tokens per request' }).fill('0');
  await page.getByRole('slider', { name: 'Cache hit rate' }).fill('100');
  const winners = page.getByTestId('offering-row').filter({ hasText: 'Lowest estimate' });
  await page.getByRole('spinbutton', { name: 'Input tokens per request' }).fill('100000');
  await expect(winners.first()).toContainText('Prompt ≤100K');
  await page.getByRole('spinbutton', { name: 'Input tokens per request' }).fill('100001');
  await expect(winners.first()).toContainText('Prompt >100K');
  await expect(page.getByText('Outside prompt band').first()).toBeVisible();
});

test('gateway prices stay gateway-labeled and preserve service tiers and scope', async ({ page }) => {
  await page.goto('/?model=openai%2Fgpt-6.1-sol');
  const gateway = page.getByTestId('offering-row').filter({ hasText: 'Vercel AI Gateway' });
  await expect(gateway.first()).toContainText('Gateway access');
  await gateway.first().getByRole('button', { name: 'Details for Vercel AI Gateway' }).click();
  await expect(page.getByText('not a direct upstream-provider quote', { exact: false })).toBeVisible();
  await expect(page.getByText('Cache-write TTL is not established', { exact: false })).toBeVisible();
  await page.getByLabel('Service tier').selectOption('priority');
  await expect(page.getByTestId('offering-row')).toHaveCount(2);
  await expect(page.getByTestId('offering-row').first()).toContainText('Vercel AI Gateway');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export comparison as CSV' }).click();
  expect((await download).suggestedFilename()).toBe('gpt-6.1-sol-comparison.csv');
});

test('recent-model comparisons and reviewed explorer stay accessible on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/?model=anthropic%2Fclaude-fable-5.1');
  await expect(page.getByTestId('offering-row').first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(result.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
  await page.screenshot({ path: 'test-results/recent-model-mobile.png', fullPage: true });
  await page.goto('/?view=models');
  await page.getByRole('textbox', { name: 'Search models', exact: true }).fill('Kimi');
  await expect(page.getByRole('button', { name: 'Compare Kimi K3', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Compare Kimi K2.7 Code', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
