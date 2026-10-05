import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const models = [
  ['openai/gpt-5.4', ['OpenAI API', 'Azure OpenAI']],
  ['openai/gpt-5.4-mini', ['OpenAI API', 'Azure OpenAI']],
  ['anthropic/claude-sonnet-4.6', ['Anthropic API', 'Google Vertex AI', 'Amazon Bedrock']],
  ['anthropic/claude-opus-4.6', ['Anthropic API', 'Google Vertex AI', 'Amazon Bedrock']],
  ['anthropic/claude-haiku-4.5', ['Anthropic API', 'Google Vertex AI', 'Amazon Bedrock']],
  ['google/gemini-3.8-flash', ['Google Gemini API', 'Google Vertex AI']],
  ['google/gemini-3.5-flash-lite', ['Google Gemini API', 'Google Vertex AI']],
] as const;

test('all new models have real native and cloud comparisons, not open-weight badges', async ({ page }) => {
  await page.goto('/');
  for (const [id, providers] of models) {
    await page.getByLabel('SELECT A MODEL').selectOption(id);
    await expect(page.locator('.model-meta')).toContainText('Proprietary');
    await expect(page.locator('.model-meta')).not.toContainText('Open weights');
    for (const provider of providers) await expect(page.locator('.provider-cell strong').getByText(provider, { exact: true }).first()).toBeVisible();
    await expect(page.locator('.stat-card.accent .stat-value')).not.toContainText('—');
    const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(accessibility.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
  }
  await page.getByLabel('SELECT A MODEL').selectOption('anthropic/claude-sonnet-4.6');
  await expect(page.getByText('Legacy release', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Details for Anthropic API standard standard' }).click();
  await expect(page.getByText('5-minute TTL', { exact: false }).first()).toBeVisible();
});

test('long prompts and fully cached prompts cannot win at a short-context price', async ({ page }) => {
  await page.goto('/?model=openai%2Fgpt-5.4');
  await page.getByRole('spinbutton', { name: 'Input tokens per request' }).fill('300000');
  await page.getByRole('spinbutton', { name: 'Number of requests' }).fill('1');
  await page.getByRole('slider', { name: 'Cache hit rate' }).fill('100');
  await expect(page.locator('.stat-card.accent .stat-value')).toContainText('$0.159');
  await expect(page.getByText('Outside prompt band').first()).toBeVisible();
  const winners = page.getByTestId('offering-row').filter({ hasText: 'Lowest estimate' });
  await expect(winners.first()).toContainText('Prompt >272K');
  await page.getByRole('spinbutton', { name: 'Input tokens per request' }).fill('272000');
  await expect(winners.first()).toContainText('Prompt ≤272K');
});

test('mobile proprietary comparisons stay readable and accessible', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/?model=google%2Fgemini-3.8-flash');
  await expect(page.getByTestId('offering-row').first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByLabel('Service tier').selectOption('priority');
  await expect(page.getByTestId('offering-row')).toHaveCount(3);
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(result.violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
  await page.screenshot({ path: 'test-results/cloud-mobile.png', fullPage: true });
});
