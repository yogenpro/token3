import { expect, test } from '@playwright/test';

for (const width of [1440, 390, 320]) {
  test(`Token³ branding and readable typography at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/');
    await expect(page.getByTestId('offering-row').first()).toBeVisible();
    await expect(page).toHaveTitle('TokenTokenToken (Token³) — LLM inference price watch');
    await expect(page.locator('.brand small')).toHaveText('TokenTokenToken');
    await expect(page.locator('.brand-wordmark sup')).toHaveText('3');
    const sizes = await page.evaluate(() => Object.fromEntries([
      '.page-heading > p', '.nav-item', '.numeric-field input', '.price-cell',
      '.provider-cell strong', '.section-heading h2', '.table-note', '.page-footer',
    ].map((selector) => [selector, parseFloat(getComputedStyle(document.querySelector(selector)!).fontSize)])));
    expect(sizes).toEqual({
      '.page-heading > p': 16, '.nav-item': 14, '.numeric-field input': 16, '.price-cell': 14,
      '.provider-cell strong': 16, '.section-heading h2': 20, '.table-note': 12, '.page-footer': 12,
    });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    if (width === 390) {
      for (const name of ['Model explorer', 'Recent changes', 'Methodology']) {
        await page.getByRole('button', { name, exact: true }).click();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      }
    }
  });
}

test('rebranded dataset and history exports use the new site name', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByTestId('offering-row').first()).toBeVisible();
  const fullExport = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export data', exact: true }).click();
  expect((await fullExport).suggestedFilename()).toBe('tokentokentoken-dataset.json');
  await page.getByRole('button', { name: 'Methodology', exact: true }).click();
  const historyExport = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download append-only history CSV' }).click();
  expect((await historyExport).suggestedFilename()).toBe('tokentokentoken-price-history.csv');
});

test('preserves existing theme preferences after the rename', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('token-ledger-theme', 'dark'));
  await page.goto('/');
  await expect(page.getByTestId('offering-row').first()).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  expect(await page.evaluate(() => localStorage.getItem('tokentokentoken-theme'))).toBe('dark');
});
