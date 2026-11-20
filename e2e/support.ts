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
  const text = await passport(page).locator('dl').innerText();
  const match = text.match(/v(\d+)/);
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
  await page.getByLabel('Mobile number').fill(`+1415${stamp.slice(-7)}`);
  await page.getByLabel('Password').fill(member.password);
  await page.getByRole('button', { name: 'Create account' }).click();
  const notice = await page.getByText('Development build').innerText();
  const codes = notice.match(/Email (\d{6}), phone (\d{6})/);
  expect(codes, 'the local build shows both codes').not.toBeNull();
  const inputs = page.locator('input[inputmode="numeric"]');
  await inputs.nth(0).fill(codes![1]);
  await inputs.nth(1).fill(codes![2]);
  await page.getByRole('button', { name: 'Confirm and continue' }).click();
  await page.waitForURL('**/rewards');
  return member;
}

export async function signIn(page: Page, email: string, password: string): Promise<void> {
  await page.goto('/sign-in');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign In' }).click();
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();
}
