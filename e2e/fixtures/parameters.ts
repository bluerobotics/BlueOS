import { expect, Locator, Page } from '@playwright/test'

// 5 seconds above the autopilot firmware test, the parameter list is slower to arrive
export const LOAD_TIMEOUT = 65_000

export async function waitParameters(page: Page): Promise<void> {
  // Save is only enabled once every parameter and its metadata are loaded
  await expect(page.getByTestId('parameters-download-button'), 'the parameters should load')
    .toBeEnabled({ timeout: LOAD_TIMEOUT })
}

export async function searchParameter(page: Page, search: string): Promise<void> {
  await page.getByTestId('parameter-search').fill(search)
  await expect(page.getByTestId('parameters-table').locator('mark').first(), `"${search}" should match something`)
    .toBeVisible()
}

export function parameterRow(page: Page, name: string): Locator {
  const cell = page.getByTestId('parameter-name').filter({ hasText: new RegExp(`^\\s*${name}\\s*$`) })
  return page.getByRole('row').filter({ has: cell })
}

export function parameterValue(page: Page, name: string): Locator {
  return parameterRow(page, name).getByTestId('parameter-value')
}

// Only goes to the parameters page when it is somewhere else
async function openParameters(page: Page): Promise<void> {
  if (!page.url().includes('/vehicle/parameters')) {
    await page.goto('/vehicle/parameters')
  }
  await waitParameters(page)
}

export async function readParameters(page: Page, names: string[]): Promise<Record<string, number>> {
  await openParameters(page)
  const values: Record<string, number> = {}
  for (const name of names) {
    await searchParameter(page, name)
    const value = parameterValue(page, name)
    await expect(value, `${name} should be listed`).toBeVisible()
    values[name] = parseFloat(await value.innerText())
  }
  return values
}

export async function readParameter(page: Page, name: string): Promise<number> {
  return (await readParameters(page, [name]))[name]
}
