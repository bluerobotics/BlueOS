import { expect, Locator, Page } from '@playwright/test'

export const BACKEND_TIMEOUT = 60_000

export async function openSelect(page: Page, testId: string): Promise<Locator> {
  const select = page.getByTestId(testId)
  await expect(select, `the ${testId} select should be enabled`).toBeEnabled({ timeout: BACKEND_TIMEOUT })
  await select.click()
  const menu = page.locator(`.${testId}-menu`)
  await expect(menu, `the ${testId} list should open`).toBeVisible()
  return menu
}
