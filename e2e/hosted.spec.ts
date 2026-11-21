// A member's journey on a DEPLOYED site. Sign-up is closed there (verification codes cannot be sent),
// so it signs in as the seeded admin.
//
// Unlike smoke.spec.ts this WRITES to that environment: each run leaves one review behind, on the first
// demo product this account has not reviewed yet (the API allows one review per member per product).
// When none is left, the review step reports that and the rest still runs. Run it on purpose, not on
// every deploy.
//
//   BASE_URL=https://<web host> ADMIN_PASSWORD=<from the app secret> npm run hosted
import { expect, test, type Page } from '@playwright/test';

const EMAIL = process.env.ADMIN_EMAIL ?? 'admin@telcron.example.com';
const PASSWORD = process.env.ADMIN_PASSWORD ?? '';
const WALLET_PRODUCT = { slug: 'northwind-chillmate-31', name: /Northwind ChillMate/ };
const REVIEWABLE = ['northwind-chillmate-31', 'acme-powerblend-1000', 'contoso-fastcharge-65w'];
const REVIEW = 'Bought it three months ago and it has worked every day since. Build quality feels solid.';

const passport = (page: Page) => page.locator('section[aria-labelledby=passport]');

async function passportVersion(page: Page): Promise<number> {
  const text = await passport(page).locator('dl').innerText();
  const match = text.match(/v(\d+)/);
  if (!match) throw new Error(`no passport version in: ${text}`);
  return Number(match[1]);
}

test('a signed-in member uses the wallet, reviews a product and is paid, on the live site', async ({ page, baseURL }) => {
  test.skip(!PASSWORD, 'ADMIN_PASSWORD is not set');
  expect(baseURL, 'this spec is for a deployed site').toMatch(/^https:/);
  const serverErrors: string[] = [];
  page.on('response', (r) => { if (r.status() >= 500) serverErrors.push(`${r.status()} ${r.url()}`); });

  await test.step('sign in', async () => {
    await page.goto('/sign-in');
    await page.getByLabel('Email').fill(EMAIL);
    await page.getByLabel('Password').fill(PASSWORD);
    await page.getByRole('button', { name: 'Sign In' }).click();
    await expect(page.locator('header [aria-haspopup=menu]')).toBeVisible();
  });

  await test.step('wallet: save a product, see it listed, remove it', async () => {
    const item = page.locator('li.card').filter({ has: page.getByRole('link', { name: WALLET_PRODUCT.name }) });
    await page.goto('/wallet');
    await expect(page.getByRole('heading', { name: 'Risk alerts' })).toBeVisible();
    if (await item.count()) {
      // Left behind by an earlier, interrupted run.
      await item.getByRole('button', { name: 'Remove' }).click();
      await expect(item).toHaveCount(0);
    }
    await page.goto(`/products/${WALLET_PRODUCT.slug}`);
    await page.getByRole('button', { name: 'Save to wallet' }).click();
    await expect(page.getByText('Saved to your Digital Wallet')).toBeVisible();
    await page.goto('/wallet');
    await expect(item).toHaveCount(1);
    await item.getByRole('button', { name: 'Remove' }).click();
    await expect(item).toHaveCount(0);
  });

  await test.step('a review is re-screened by the Worker into a new passport version', async () => {
    for (const slug of REVIEWABLE) {
      await page.goto(`/products/${slug}`);
      const before = await passportVersion(page);
      await page.getByRole('form', { name: 'Write a review' }).locator('textarea').fill(REVIEW);
      await page.getByRole('button', { name: 'Post review' }).click();
      const outcome = page.getByText(/TelCoins are pending|already reviewed/);
      await expect(outcome).toBeVisible();
      if ((await outcome.innerText()).includes('already reviewed')) continue;

      await expect
        .poll(async () => { await page.reload(); return passportVersion(page); }, { timeout: 60_000 })
        .toBe(before + 1);
      await expect(passport(page).getByText(/(Low|Medium|High) hazard/)).toBeVisible();
      await expect(page.locator('section[aria-labelledby=reviews]').getByText(REVIEW).first()).toBeVisible();
      test.info().annotations.push({ type: 'reviewed', description: `${slug}: v${before} -> v${before + 1}` });
      return;
    }
    test.info().annotations.push({
      type: 'not exercised',
      description: 'this account has already reviewed every demo product; the review step wrote nothing',
    });
  });

  await test.step('coins: earned by a review, confirmed by the database when due', async () => {
    await page.goto('/rewards');
    await expect(page.getByRole('heading', { name: 'History' })).toBeVisible();
    await expect(page.locator('ul.divide-y li').filter({ hasText: /Review|First review/ }).first()).toBeVisible();
    const card = await page.locator('section').first().innerText();
    test.info().annotations.push({ type: 'coins', description: card.replace(/\s+/g, ' ') });
  });

  await test.step('sign out closes the member pages', async () => {
    await page.locator('header [aria-haspopup=menu]').click();
    await page.getByRole('menuitem', { name: 'Sign out' }).click();
    await page.goto('/rewards');
    await expect(page.getByText('Sign in to continue')).toBeVisible();
  });

  expect(serverErrors, 'no request was answered with a server error').toEqual([]);
});
