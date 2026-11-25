import { readFile } from 'node:fs/promises'

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

// Writes through the Load button, the same path as loading a .params file by hand
export async function writeParameters(page: Page, values: Record<string, number>): Promise<void> {
  await openParameters(page)
  const content = Object.entries(values).map(([name, value]) => `${name},${value}`).join('\n')
  await page.getByTestId('parameters-load-button').click()
  await page.getByTestId('parameters-file-input')
    .setInputFiles({ name: 'e2e.params', mimeType: 'text/plain', buffer: Buffer.from(content) })
  const loader = page.getByTestId('parameters-loader')
  await expect(loader, 'the parameters loader should open').toBeVisible()
  const write = page.getByTestId('parameters-write-button')
  if (await write.isEnabled()) {
    await write.click()
    await expect(page.getByTestId('parameters-write-success'), 'the parameters should be written')
      .toBeVisible({ timeout: LOAD_TIMEOUT })
    await page.getByTestId('parameters-loader-close-button').click()
  } else {
    // Nothing to change, Write stays disabled and there is no Close button
    await page.keyboard.press('Escape')
  }
  await expect(loader, 'the parameters loader should close').toBeHidden()
}

export async function writeParameter(page: Page, name: string, value: number): Promise<void> {
  await writeParameters(page, { [name]: value })
}

// Every writable parameter, from the Save button
export async function saveParameters(page: Page): Promise<Record<string, number>> {
  const download = page.waitForEvent('download')
  await page.getByTestId('parameters-download-button').click()
  const content = await readFile(await (await download).path())
  const values: Record<string, number> = {}
  for (const line of content.toString().split('\n')) {
    const [name, value] = line.trim().split(/\s+/)
    if (name && !name.startsWith('#') && value !== undefined) {
      values[name] = Number(value)
    }
  }
  return values
}
