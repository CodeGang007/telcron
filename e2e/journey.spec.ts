// The member's journey, through the real web app, API, database, queues and Worker.
// Needs a local stack with the demo data (`make app-db`, `make dev`), DEV_EXPOSE_CODES=true and a
// short COIN_CONFIRM_DELAY_SECONDS. It creates a new member on every run and never reuses one.
import { expect, test, type Page } from '@playwright/test';

const FRIDGE = '/products/northwind-chillmate-31';
const passport = (page: Page) => page.locator('section[aria-labelledby=passport]');

async function passportVersion(page: Page): Promise<number> {
  const text = await passport(page).locator('dl').innerText();
  const match = text.match(/v(\d+)/);
  if (!match) throw new Error(`no passport version in: ${text}`);
  return Number(match[1]);
}

test('a visitor searches and reads a passport without an account', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('product safety');
  await page.getByLabel('Search by product name, brand or barcode').fill('blender');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('link', { name: /Acme Kitchen PowerBlend 1000/ })).toBeVisible();
  await page.getByRole('link', { name: /Acme Kitchen PowerBlend 1000/ }).click();
  await expect(passport(page).getByText('Recalled', { exact: true })).toBeVisible();
  await expect(passport(page).getByText(/Laceration hazard/)).toBeVisible();
  // A page the server has never heard of still loads: the app is a single page.
  await page.goto('/products/unidentified-desk-lamp');
  await expect(passport(page).getByText('Needs information', { exact: true })).toBeVisible();
});

test('members-only pages offer sign-in instead of failing', async ({ page }) => {
  await page.goto('/wallet');
  await expect(page.getByText('Sign in to continue')).toBeVisible();
});

test('a wrong password is refused with a useful message', async ({ page }) => {
  await page.goto('/sign-in');
  await page.getByLabel('Email').fill('nobody@example.com');
  await page.getByLabel('Password').fill('not-the-password');
  await page.getByRole('button', { name: 'Sign In' }).click();
  await expect(page.getByRole('alert')).toContainText('do not match');
});

test('a member signs up, saves a product, reviews it and is paid', async ({ page }) => {
  const stamp = Date.now();

  // Sign up and confirm both codes.
  await page.goto('/sign-up');
  await page.getByLabel('Name').fill('E2E Member');
  await page.getByLabel('Email').fill(`e2e-${stamp}@example.com`);
  await page.getByLabel('Mobile number').fill(`+1415${String(stamp).slice(-7)}`);
  await page.getByLabel('Password').fill('a-long-password-1');
  await page.getByRole('button', { name: 'Create account' }).click();
  const notice = await page.getByText('Development build').innerText();
  const codes = notice.match(/Email (\d{6}), phone (\d{6})/);
  expect(codes, 'the local build shows both codes').not.toBeNull();
  const inputs = page.locator('input[inputmode="numeric"]');
  await inputs.nth(0).fill(codes![1]);
  await inputs.nth(1).fill(codes![2]);
  await page.getByRole('button', { name: 'Confirm and continue' }).click();

  // Level 1 pays 100 coins, pending until the fraud-review window has passed.
  await page.waitForURL('**/rewards');
  await expect(page.getByText('Novice')).toBeVisible();
  await expect(page.getByText('100 pending')).toBeVisible();

  // Save a product and review it.
  await page.goto(FRIDGE);
  const before = await passportVersion(page);
  await page.getByRole('button', { name: 'Save to wallet' }).click();
  await expect(page.getByText('Saved to your Digital Wallet')).toBeVisible();
  await page
    .locator('textarea')
    .fill('The compressor started to overheat and there was smoke and a burning smell after a week.');
  await page.getByRole('button', { name: 'Post review' }).click();
  await expect(page.getByText(/Review posted\. 10 TelCoins are pending/)).toBeVisible();

  // The Worker re-screens the product: a new passport version, now with a hazard band.
  await expect
    .poll(async () => { await page.reload(); return passportVersion(page); }, { timeout: 45_000 })
    .toBe(before + 1);
  await expect(passport(page).getByText(/(Low|Medium|High) hazard/)).toBeVisible();
  // The review is listed, and it is cited as evidence under the hazard scores.
  const reviews = page.locator('section[aria-labelledby=reviews]');
  await expect(reviews.getByText('The compressor started to overheat').first()).toBeVisible();
  await expect(passport(page).getByText(/Evidence \(\d+\)/).first()).toBeVisible();

  // The wallet lists it, and says the passport moved on since it was saved.
  await page.goto('/wallet');
  await expect(page.getByRole('link', { name: /Northwind ChillMate/ })).toBeVisible();
  await expect(page.getByText('Passport changed since you saved it')).toBeVisible();

  // The coins are confirmed by the database once they fall due: 100 for Level 1, 10 for the review.
  await expect
    .poll(
      async () => { await page.goto('/rewards'); return page.locator('div.bg-brand').innerText(); },
      { timeout: 90_000, intervals: [3_000] },
    )
    .toMatch(/110[\s\S]*0 pending/);
  await expect(page.getByText('Confirmed').first()).toBeVisible();

  // Signing out closes the member's pages again.
  await page.getByRole('button', { name: 'Sign out' }).click();
  await page.goto('/rewards');
  await expect(page.getByText('Sign in to continue')).toBeVisible();
});
