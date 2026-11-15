// Read-only checks of a DEPLOYED site: the web host, the API behind it and the database behind that.
// It changes nothing, so it is safe to run against the dev environment after every deploy.
//   BASE_URL=https://<web host> API_URL=https://<api host> [EXPECT_VERSION=<commit>] npm run smoke
import { expect, test } from '@playwright/test';

const API = process.env.API_URL;
const VERSION = process.env.EXPECT_VERSION;

test('the API is healthy and is the expected build', async ({ request }) => {
  test.skip(!API, 'API_URL is not set');
  const health = await request.get(`${API}/health`);
  expect(health.ok()).toBe(true);
  const body = await health.json();
  expect(body.status).toBe('ok');
  if (VERSION) expect(body.version).toBe(VERSION);
});

test('the web host serves the expected build over HTTPS', async ({ request, baseURL }) => {
  expect(baseURL).toMatch(/^https:/);
  if (VERSION) {
    const served = await request.get('/version.txt');
    expect((await served.text()).trim()).toBe(VERSION);
  }
});

test('home, search and a passport work for a visitor', async ({ page }) => {
  const failed: string[] = [];
  page.on('response', (r) => { if (r.status() >= 500) failed.push(`${r.status()} ${r.url()}`); });
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('product safety');
  await expect(page.getByRole('heading', { name: 'Recently screened' })).toBeVisible();
  await page.getByLabel('Search by product name, brand or barcode').fill('blender');
  await page.keyboard.press('Enter');
  await page.getByRole('link', { name: /Blender/ }).first().click();
  await expect(page.locator('section[aria-labelledby=passport]')).toContainText('Trust score', {
    ignoreCase: true,
  });
  expect(failed).toEqual([]);
});

test('a deep link loads, and members-only pages ask for sign-in', async ({ page }) => {
  const response = await page.goto('/wallet');
  expect(response?.status()).toBe(200);
  await expect(page.getByText('Sign in to continue')).toBeVisible();
});

test('sign-up on a deployed site never shows verification codes', async ({ request }) => {
  test.skip(!API, 'API_URL is not set');
  // Validation fails before anything is written: this checks the route is up without creating a user.
  const refused = await request.post(`${API}/api/v1/auth/register`, { data: { email: 'not-an-email' } });
  expect(refused.status()).toBe(422);
  expect(JSON.stringify(await refused.json())).not.toContain('dev_codes');
});
