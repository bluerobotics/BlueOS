import { expect, test as base } from '@playwright/test'

export const test = base.extend({
  page: async ({ page }, use) => {
    // Pirate mode and the language are frontend settings stored in the bag of holding, so the answer is
    // patched locally and nothing is written on the vehicle
    await page.route('**/bag/v1.0/get/settings/settings_version', (route) => route.fulfill({ json: 1 }))
    await page.route('**/bag/v1.0/get/settings', async (route) => {
      const response = await route.fetch()
      const settings = response.ok() ? await response.json() : {}
      await route.fulfill({ json: { ...settings, is_pirate_mode: true, language: 'en' } })
    })
    // A fresh vehicle opens the setup wizard on every page load and the guided tour once
    await page.route('**/bag/v1.0/get/wizard', (route) => route.fulfill({ json: { version: 4 } }))
    await page.addLocatorHandler(page.getByRole('button', { name: 'Skip tour' }), (skip) => skip.click())
    await use(page)
  },
})

export { expect }
