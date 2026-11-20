// The member's journey, through the real web app, API, database, queues and Worker.
// Needs a local stack with the demo data (`make app-db`, `make dev`), DEV_EXPOSE_CODES=true, a short
// COIN_CONFIRM_DELAY_SECONDS and SEED_ADMIN_PASSWORD. It creates new members on every run.
import { expect, test } from '@playwright/test';
import { ADMIN_EMAIL, newMember, passport, passportVersion, reportText, setting, signIn, signOut } from './support';

const FRIDGE = '/products/northwind-chillmate-31';
const CHARGER = '/products/contoso-fastcharge-65w';

test('a visitor searches and reads a passport without an account', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('before you buy');
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
  await newMember(page, 'E2E Member');

  // Level 1 pays 100 coins, pending until the fraud-review window has passed.
  await expect(page.getByText('Novice').first()).toBeVisible();
  await expect(page.getByText(/1\d\d pending/)).toBeVisible();

  // Save a product and review it.
  await page.goto(FRIDGE);
  const before = await passportVersion(page);
  await page.getByRole('button', { name: 'Save to wallet' }).click();
  await expect(page.getByText('Saved to your Digital Wallet')).toBeVisible();
  await page
    .getByRole('form', { name: 'Write a review' })
    .locator('textarea')
    .fill('The compressor started to overheat and there was smoke and a burning smell after a week.');
  await page.getByRole('button', { name: 'Post review' }).click();
  await expect(page.getByText('10 TelCoins are pending while we check it.')).toBeVisible();

  // The Worker re-screens the product: a new passport version, now with a hazard band.
  await expect
    .poll(async () => { await page.reload(); return passportVersion(page); }, { timeout: 45_000 })
    .toBe(before + 1);
  await expect(passport(page).getByText(/(Low|Medium|High) hazard/)).toBeVisible();
  // The review is listed, and it is cited as evidence under the hazard scores.
  const reviews = page.locator('section[aria-labelledby=reviews]');
  await expect(reviews.getByText('The compressor started to overheat').first()).toBeVisible();
  await page.getByRole('button', { name: /Health & Safety/ }).click();
  await expect(page.getByRole('listitem').filter({ hasText: 'The compressor started to overheat' }).first()).toBeVisible();

  // The wallet lists it, and says the passport moved on since it was saved.
  await page.goto('/wallet');
  await expect(page.getByRole('link', { name: /Northwind ChillMate/ })).toBeVisible();
  await expect(page.getByText('Passport changed since you saved it')).toBeVisible();

  // The coins are confirmed by the database once they fall due: nothing is left pending.
  await expect
    .poll(async () => { await page.goto('/rewards'); await page.getByRole('heading', { name: 'History' }).waitFor(); return page.getByText('Pending check').count(); },
      { timeout: 90_000, intervals: [3_000] })
    .toBe(0);
  await expect(page.getByText('0 pending')).toBeVisible();
  await expect(page.getByText('Confirmed').first()).toBeVisible();

  // Signing out closes the member's pages again.
  await signOut(page);
  await page.goto('/rewards');
  await expect(page.getByText('Sign in to continue')).toBeVisible();
});

test('a hazard report is confirmed by the safety team, pays the reporter and becomes evidence', async ({ browser, baseURL }) => {
  const adminPassword = setting('SEED_ADMIN_PASSWORD');
  test.skip(!adminPassword, 'SEED_ADMIN_PASSWORD is not set: no admin to act as the safety team');
  const marker = `Ref ${Date.now()}`;

  // A member reports a hazard.
  const member = await (await browser.newContext({ baseURL })).newPage();
  await newMember(member, 'Flag Reporter');
  await member.goto(CHARGER);
  await member.getByRole('button', { name: 'Report hazard' }).click();
  const flag = member.getByRole('form', { name: 'Report a hazard' });
  await flag.getByLabel('Kind of hazard').selectOption({ label: 'Health & Safety' });
  await flag.getByLabel('What happened (at least 20 characters)').fill(`The plug melted and gave me an electric shock. ${marker}`);
  await flag.getByRole('button', { name: 'Send report' }).click();
  await expect(member.getByText('Report sent to the safety team')).toBeVisible();

  // The safety team sees it in the queue and confirms it.
  const staff = await (await browser.newContext({ baseURL })).newPage();
  await signIn(staff, ADMIN_EMAIL, adminPassword!);
  await staff.goto('/review-queue');
  const task = staff.locator('li.card').filter({ hasText: marker });
  await expect(task).toContainText('Flag Reporter');
  await task.getByLabel('Note (optional)').fill('Consistent with the photos.');
  await task.getByRole('button', { name: 'Confirm hazard' }).click();
  await expect(task).toHaveCount(0);

  // The member sees the decision, the reviewer's note and the coins.
  await member.goto('/rewards');
  const mine = member.locator('section[aria-labelledby=contributions] li').filter({ hasText: marker });
  await expect(mine.getByText('Confirmed', { exact: true })).toBeVisible();
  await expect(mine).toContainText('Consistent with the photos.');
  await expect(member.getByText('Hazard flag confirmed')).toBeVisible();

  // The Worker re-screens the product, and the confirmed report is now cited as evidence.
  await expect
    .poll(async () => reportText(member, 'contoso-fastcharge-65w'), { timeout: 45_000 })
    .toContain(marker);

  // A member who is not on the safety team has no queue.
  await member.goto('/review-queue');
  await expect(member.getByText('This page is for the safety team.')).toBeVisible();
});

test('an admin imports recall notices and visitors can search them', async ({ page }) => {
  const adminPassword = setting('SEED_ADMIN_PASSWORD');
  test.skip(!adminPassword, 'SEED_ADMIN_PASSWORD is not set');
  await signIn(page, ADMIN_EMAIL, adminPassword!);
  await page.goto('/data-sources');
  await page.getByRole('button', { name: 'Import recall notices' }).click();
  // The Worker runs the job; the page polls until it finishes.
  const latest = page.locator('li').filter({ hasText: 'by hand' }).first();
  await expect(latest.getByText('succeeded', { exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(latest).toContainText(/\d+ fetched/);

  await signOut(page);
  await page.goto('/recalls');
  await expect(page.getByRole('heading', { name: 'Latest recall notices' })).toBeVisible();
  const first = page.locator('li.card h2').first();
  await expect(first).toBeVisible();
  const word = ((await first.innerText()).match(/[A-Za-z]{6,}/) ?? ['recall'])[0];
  await page.getByLabel('Search recall notices').fill(word);
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: `Recall notices about “${word}”` })).toBeVisible();
  await expect(page.locator('li.card').first()).toContainText(new RegExp(word, 'i'));
  // A member's pages are not an admin's: the data sources page refuses a visitor.
  await page.goto('/data-sources');
  await expect(page.getByText('This page is for administrators.')).toBeVisible();
});


test('a barcode leads straight to the product passport', async ({ page }) => {
  await page.goto('/scan');
  await expect(page.getByRole('button', { name: 'Start camera' })).toBeVisible();
  await page.getByLabel('Barcode number').fill('012345000017');
  await page.getByRole('button', { name: 'Look it up' }).click();
  await page.waitForURL('**/products/acme-powerblend-1000');
  await expect(page.getByText('Product found')).toBeVisible();
  await expect(passport(page).getByText('Recalled', { exact: true })).toBeVisible();
  // A misread scan is refused without a lookup.
  await page.goto('/scan');
  await page.getByLabel('Barcode number').fill('885909950806');
  await page.getByRole('button', { name: 'Look it up' }).click();
  await expect(page.getByText('That is not a valid barcode')).toBeVisible();
});
