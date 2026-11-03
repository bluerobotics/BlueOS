import { test as base, expect } from '@playwright/test'

import { tameOnboarding } from './vehicle'

// Records every test with page.screencast: a title card with the test name, then a visible cursor
// on each action. The result is attached to the report as recording.webm.
export const test = base.extend<{ pageErrors: string[] }>({
  pageErrors: async ({ page }, use) => {
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    await use(errors)
  },
  page: async ({ page }, use, testInfo) => {
    await tameOnboarding(page)
    const recording = testInfo.outputPath('recording.webm')
    await page.screencast.start({ path: recording, size: testInfo.project.use.viewport ?? undefined })
    await page.screencast.showActions({ cursor: 'pointer', position: 'bottom' })
    await page.screencast.showChapter(testInfo.title, { description: testInfo.titlePath.at(-2), duration: 1500 })
    await use(page)
    await page.screencast.stop()
    await testInfo.attach('recording', { path: recording, contentType: 'video/webm' })
  },
})

export { expect }
export type { Locator, Page } from '@playwright/test'
