// Shared steps for the browser tests.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, type Page } from '@playwright/test';

/** A setting from the environment, else from the repository's .env file (local stacks). */
export function setting(name: string): string | undefined {
  if (process.env[name]) return process.env[name];
  try {
    const line = readFileSync(join(__dirname, '..', '.env'), 'utf8')
      .split('\n')
      .find((l) => l.startsWith(`${name}=`));
    return line?.slice(name.length + 1).trim() || undefined;
  } catch {
    return undefined;
  }
}

export const ADMIN_EMAIL = 'admin@telcron.example.com';
export const passport = (page: Page) => page.locator('section[aria-labelledby=passport]');

export async function passportVersion(page: Page): Promise<number> {
  await expect(passport(page)).toContainText(/Version \d+/);
  const text = await passport(page).innerText();
  const match = text.match(/Version (\d+)/);
  if (!match) throw new Error(`no passport version in: ${text}`);
  return Number(match[1]);
}

/** Signs up a new member through the screens and confirms both on-screen codes (local stacks only). */
export async function newMember(page: Page, name: string): Promise<{ email: string; password: string }> {
  const stamp = `${Date.now()}${Math.floor(Math.random() * 1000)}`;
  const member = { email: `e2e-${stamp}@example.com`, password: 'a-long-password-1' };
  await page.goto('/sign-up');
  await page.getByLabel('Name').fill(name);
  await page.getByLabel('Email').fill(member.email);
  await page.getByLabel('Mobile number (optional)').fill(`+1415${stamp.slice(-7)}`);
  await page.getByLabel('Password').fill(member.password);
  await page.getByRole('button', { name: 'Create account' }).click();
  // Locally the email code is also shown on the page; deployed, it only arrives by email.
  const notice = await page.getByText('Development build').innerText();
  const code = notice.match(/your code is (\d{6})/);
  expect(code, 'the local build shows the email code').not.toBeNull();
  await page.getByLabel('Code from the email').fill(code![1]);
  await page.getByRole('button', { name: 'Confirm and continue' }).click();
  await page.waitForURL('**/rewards');
  return member;
}

export async function signIn(page: Page, email: string, password: string): Promise<void> {
  await page.goto('/sign-in');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign In' }).click();
  await expect(page.locator('header [aria-haspopup=menu]')).toBeVisible();
}

export async function signOut(page: Page): Promise<void> {
  await page.locator('header [aria-haspopup=menu]').click();
  await page.getByRole('menuitem', { name: 'Sign out' }).click();
  await expect(page.locator('header').getByRole('link', { name: 'Sign in' })).toBeVisible();
}

/** The public passport page's hazard evidence: every score is opened and its citations read. The full
    hazard report is a paid, gated page (DEF-035, CT-002), so evidence checks read the free passport. */
export async function passportEvidence(page: Page, slug: string): Promise<string> {
  await page.goto(`/products/${slug}`);
  await expect(passport(page)).toContainText(/Version \d+/);
  const closed = page.locator('li > button[aria-expanded=false]:not([disabled])');
  for (let n = await closed.count(); n > 0; n = await closed.count()) await closed.first().click();
  return (await page.locator('main').textContent()) ?? '';
}
