import { defineConfig, devices } from '@playwright/test';

// BASE_URL is the web app under test: a local stack for `journey`, a deployed site for `smoke`.
export default defineConfig({
  testDir: '.',
  timeout: 120_000,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:3200',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  // PW_CHANNEL=chromium runs the full Chromium build headless, for a machine that has it but not the
  // separate headless shell (`npx playwright install chromium` installs both).
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], ...(process.env.PW_CHANNEL ? { channel: process.env.PW_CHANNEL } : {}) } }],
});
