import { expect, test } from '@playwright/test';

test('browser checks serve the compiled production artifact at its actual base', async ({ page, baseURL }) => {
  const requests: string[] = [];
  page.on('request', (request) => requests.push(request.url()));
  await page.goto('./');
  await expect(page.locator('script[type="module"]')).toHaveAttribute('src', /\/assets\/[^/]+\.js$/);
  expect(page.url().startsWith(baseURL!)).toBe(true);
  expect(requests.some((url) => /\/@vite\/client|\/src\//.test(url))).toBe(false);
  const response = await page.request.get('./publication.json');
  expect(response.ok()).toBe(true);
  expect((await response.json()).mode).not.toBe('development');
});
