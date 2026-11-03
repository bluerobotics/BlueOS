import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  outputDir: './test-results',
  globalSetup: './global-setup.ts',
  globalTeardown: './global-teardown.ts',
  // One browser hammering an embedded device is enough
  workers: 1,
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [['html', { open: 'never', outputFolder: './playwright-report' }], ['list']],
  use: {
    baseURL: process.env.BLUEOS_URL ?? 'http://192.168.2.2',
    viewport: { width: 1280, height: 800 },
    // No recordVideo / trace here: the fixture records via page.screencast and they fight over the frame size
    screenshot: 'only-on-failure',
  },
})
