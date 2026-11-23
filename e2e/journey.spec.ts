// The member's journey, through the real web app, API, database, queues and Worker.
// It writes: new members, reviews and a hazard report on demo products, a new product. So locally
// `npm run journey` runs it on a disposable stack (disposable-journey.sh) and never on the shared
// database (DEF-121). `npm run journey:here` (or CI, or BASE_URL) runs it against a stack that is
// already up: it needs the demo data, DEV_EXPOSE_CODES=true, a short COIN_CONFIRM_DELAY_SECONDS and
// SEED_ADMIN_PASSWORD, and should only ever point at a throwaway database.
import { expect, type Locator, test } from '@playwright/test';
import { ADMIN_EMAIL, newMember, passport, passportEvidence, passportVersion, setting, signIn, signOut } from './support';

const FRIDGE = '/products/northwind-chillmate-31';
const CHARGER = '/products/contoso-fastcharge-65w';
// The report gate sends the member to the store with the product already chosen (DEF-119).
const STORE_FOR_CHARGER = '/rewards?product=contoso-fastcharge-65w';

/** Picks a star rating in the radio group named "Rating" (DEF-116). A person clicks the star, which is
    the radio's label; the native radio itself is visually hidden. */
async function rate(form: Locator, stars: number): Promise<void> {
  const group = form.getByRole('radiogroup', { name: 'Rating' });
  const name = `${stars} out of 5`;
  // `has` is matched inside each label, so it starts from the page, not from the form.
  await group.locator('label', { has: form.page().getByRole('radio', { name }) }).click();
  await expect(group.getByRole('radio', { name })).toBeChecked();
}

test('a visitor searches and reads a passport without an account', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('before you buy');
  await page.getByLabel('Search by product name, brand or barcode').fill('blender');
  await page.keyboard.press('Enter');
  // Wait for the results page: the home page's passport card can name the same product (DEF-037).
  await expect(page).toHaveURL(/\/search\?q=blender/);
  await expect(page.getByRole('link', { name: /Acme Kitchen PowerBlend 1000/ })).toBeVisible();
  await page.getByRole('link', { name: /Acme Kitchen PowerBlend 1000/ }).click();
  await expect(passport(page).getByText('Recalled', { exact: true })).toBeVisible();
  await expect(passport(page).getByText('Laceration hazard', { exact: true })).toBeVisible();
  // The verdict says what it means for the owner, before any score.
  await expect(passport(page).getByText('This product is recalled')).toBeVisible();
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
  // The form has no rating until one is picked, and will not post without one (DEF-116).
  const review = page.getByRole('form', { name: 'Write a review' });
  await review.locator('textarea')
    .fill('The compressor started to overheat and there was smoke and a burning smell after a week.');
  await page.getByRole('button', { name: 'Post review' }).click();
  await expect(review.getByRole('alert')).toContainText('Choose a rating');
  // A complaint carries a low rating.
  await rate(review, 2);
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

test('a member redeems the printable hazard report, and only they can open it', async ({ browser, baseURL, page }) => {
  const slug = 'contoso-fastcharge-65w';
  const report = `/products/${slug}/report`;
  await newMember(page, 'Report Buyer');
  await page.goto(CHARGER);
  await page.getByRole('button', { name: 'Save to wallet' }).click();
  await expect(page.getByText('Saved to your Digital Wallet')).toBeVisible();

  // Before redeeming, the member meets the unlock card that points at the coin store (CT-002: 403).
  await page.goto(report);
  await expect(page.getByRole('heading', { name: 'Redeem for 50 TelCoins to unlock' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Open the coin store' })).toHaveAttribute('href', STORE_FOR_CHARGER);
  await expect(page.getByRole('link', { name: 'See the free passport' })).toHaveAttribute('href', CHARGER);
  await expect(page.locator('article')).toHaveCount(0);

  // The store sells it under an honest name, and it unlocks once the sign-up coins are confirmed.
  const item = page.locator('li.card').filter({ hasText: 'Full hazard report' });
  await expect
    .poll(async () => { await page.goto(STORE_FOR_CHARGER); await item.waitFor(); return item.getByRole('button', { name: 'Redeem', exact: true }).count(); },
      { timeout: 90_000, intervals: [3_000] })
    .toBe(1);
  await expect(item).toContainText('Full hazard report (printable)');
  await expect(item).not.toContainText('PDF');
  // Sent from the gate, the store has already chosen the product (DEF-119).
  await expect(item.getByLabel('For')).toHaveValue(slug);
  await item.getByLabel('For').selectOption(slug);
  await item.getByRole('button', { name: 'Redeem', exact: true }).click();
  await expect(page.getByText('Full hazard report (printable) is yours')).toBeVisible();

  // Opened from the toast, the report reads only the gated endpoint: no public product or passport read.
  // Counted from the moment the report page is the document: the store before it reads the product
  // it pre-selects (DEF-119), which is not the report's doing.
  const productReads: string[] = [];
  let onReport = false;
  page.on('framenavigated', (f) => { if (f === page.mainFrame()) onReport = new URL(f.url()).pathname === report; });
  page.on('request', (r) => { if (onReport && /\/api\/v1\/products\//.test(r.url())) productReads.push(new URL(r.url()).pathname); });
  await page.getByRole('button', { name: 'Open', exact: true }).click();
  await page.waitForURL(`**${report}`);
  const article = page.locator('article');
  await expect(article.getByText('Telcron hazard report')).toBeVisible();
  await expect(article.getByRole('heading', { level: 1 })).toContainText('Contoso FastCharge');
  await expect(article).toContainText(/Version \d+/);
  await expect(page.getByRole('button', { name: 'Print or save as PDF' })).toBeVisible();
  await page.reload();
  await expect(article.getByRole('heading', { level: 1 })).toContainText('Contoso FastCharge');
  expect([...new Set(productReads)]).toEqual([`/api/v1${report}`]);

  // Signed out, the same address is locked and offers sign-in and the free passport.
  await signOut(page);
  await page.goto(report);
  await expect(page.getByRole('heading', { name: 'Redeem for 50 TelCoins to unlock' })).toBeVisible();
  await expect(page.getByRole('main').getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/sign-in');
  await expect(page.getByRole('link', { name: 'See the free passport' })).toHaveAttribute('href', CHARGER);
  await expect(page.locator('article')).toHaveCount(0);
  // The free passport is unchanged and needs no account.
  await page.getByRole('link', { name: 'See the free passport' }).click();
  await expect(passport(page)).toContainText(/Version \d+/);

  // Another member gets nothing from the buyer's redemption.
  const other = await (await browser.newContext({ baseURL })).newPage();
  await newMember(other, 'Not A Buyer');
  await other.goto(report);
  await expect(other.getByRole('heading', { name: 'Redeem for 50 TelCoins to unlock' })).toBeVisible();
  await expect(other.getByRole('link', { name: 'Open the coin store' })).toHaveAttribute('href', STORE_FOR_CHARGER);
  await expect(other.locator('article')).toHaveCount(0);
  await other.context().close();
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

  // The Worker re-screens the product, and the confirmed report is now cited as evidence on the free
  // passport (the printable report is a paid page: DEF-035).
  await expect
    .poll(async () => passportEvidence(member, 'contoso-fastcharge-65w'), { timeout: 45_000 })
    .toContain(marker);

  // A member who is not on the safety team has no queue: the admin area is not revealed (WO-055).
  await member.goto('/review-queue');
  await expect(member).toHaveURL(/\/admin\/review-queue$/);
  await expect(member.getByText('That page does not exist.')).toBeVisible();
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
  // The data sources page is in the admin area (WO-055): a visitor is asked to sign in.
  await page.goto('/data-sources');
  await expect(page).toHaveURL(/\/admin\/data-sources$/);
  await expect(page.getByText('Sign in to continue')).toBeVisible();
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

/** An EAN-13 with a correct check digit under an unused prefix, different on every run. */
function freshBarcode(): string {
  const body = `890777${String(Date.now()).slice(-6)}`;
  const sum = [...body].reduce((t, d, i) => t + Number(d) * (i % 2 === 0 ? 1 : 3), 0);
  return body + String((10 - (sum % 10)) % 10);
}

test('a product no database knows is identified by a member and screened', async ({ page }) => {
  await newMember(page, 'Scanner Test');
  await page.goto('/scan');
  // A valid barcode no product database has: an unused company prefix, a fresh number each run.
  const barcode = freshBarcode();
  await page.getByLabel('Barcode number').fill(barcode);
  await page.getByRole('button', { name: 'Look it up' }).click();
  await expect(page.getByRole('heading', { name: 'New to Telcron: tell us what it is' })).toBeVisible({ timeout: 30_000 });
  await page.getByRole('button', { name: 'Type the details instead' }).click();
  const form = page.getByRole('form', { name: 'Confirm the product' });
  const name = `Test Desk Fan ${Date.now()}`;
  await form.getByLabel('Product name').fill(name);
  await form.getByLabel('Brand').fill('Lumina');
  await form.getByLabel('Category').selectOption('appliances');
  await form.getByRole('button', { name: 'Add it and screen it' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toContainText(name);
  await expect(passport(page)).toContainText(/Version \d+/);
  // Scanned again, the barcode now goes straight to it.
  await page.goto('/scan');
  await page.getByLabel('Barcode number').fill(barcode);
  await page.getByRole('button', { name: 'Look it up' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Lumina');
});

