import { expect, Locator, Page } from '@playwright/test'
import { compare } from 'semver'

import { openSelect } from '@/fixtures/ui'

export const COCKPIT = 'bluerobotics.cockpit'
// Installing pulls the image on the vehicle, a slow link takes minutes
export const INSTALL_TIMEOUT = 10 * 60_000

interface ManifestExtension {
  identifier: string
  versions: Record<string, { images: { compatible: boolean }[] }>
}

// The two newest versions this vehicle can run, from the same manifest the page lists
export async function lastVersions(page: Page, identifier: string): Promise<{ latest: string, previous: string }> {
  const response = await page.request.get('/kraken/v2.0/manifest/consolidated', { timeout: 60_000 })
  expect(response.ok(), 'the vehicle should give the extensions manifest').toBe(true)
  const extension = ((await response.json()) as ManifestExtension[]).find((entry) => entry.identifier === identifier)
  expect(extension, `${identifier} should be in the manifest`).toBeDefined()
  const versions = Object.entries(extension!.versions)
    .filter(([, version]) => version.images.some((image) => image.compatible))
    .map(([tag]) => tag)
    .sort((a, b) => compare(b, a))
  expect(versions.length, `${identifier} should have two versions to switch`).toBeGreaterThanOrEqual(2)
  return { latest: versions[0], previous: versions[1] }
}

export function installedCard(page: Page, identifier: string): Locator {
  return page.getByTestId(`installed-extension-${identifier}`)
}

// The pull dialog can flash by when the image is already on the vehicle, so this waits for the request itself
async function pull(page: Page, method: string, click: () => Promise<void>): Promise<void> {
  const request = page.waitForResponse(
    (response) => response.request().method() === method && response.url().includes('/kraken/v2.0/extension/'),
    { timeout: INSTALL_TIMEOUT },
  )
  await click()
  const response = await request
  expect(response.ok(), `the vehicle should accept the ${method}`).toBe(true)
  await response.finished()
  // Kraken answers 200 and streams a failure as a fragment, so the body has to be read too
  const failures = (await response.text()).split('|\n\n|')
    .map((fragment) => { try { return JSON.parse(fragment) } catch { return undefined } })
    .filter((fragment) => fragment && fragment.status !== 200)
    .map((fragment) => fragment.error)
  expect(failures, `the ${method} should finish without errors`).toEqual([])
  await expect(page.getByTestId('pull-progress'), 'the pull should end').toBeHidden()
  await expect(page.getByTestId('extension-error'), 'the page should not show an error').toBeHidden()
}

export async function expectInstalled(page: Page, identifier: string, version: string): Promise<void> {
  await page.getByRole('tab', { name: 'Installed' }).click()
  const card = installedCard(page, identifier)
  // The page asks the vehicle for the extensions and their containers every 10 seconds
  await expect(card.getByTestId('installed-extension-tag'), `${identifier} should be at ${version}`)
    .toHaveText(version, { timeout: 60_000 })
  await expect(card.getByTestId('installed-extension-status'), `${identifier} should be running`)
    .toHaveText(/^\s*Up /, { timeout: 2 * 60_000 })
}

export async function uninstall(page: Page, identifier: string): Promise<void> {
  await page.getByRole('tab', { name: 'Installed' }).click()
  const card = installedCard(page, identifier)
  // The vehicle answers once the container is gone, the card hides before that
  const removal = page.waitForResponse(
    (response) => response.request().method() === 'DELETE'
      && response.url().includes(`/kraken/v2.0/extension/${identifier}`),
    { timeout: 2 * 60_000 },
  )
  await card.getByTestId('installed-extension-uninstall').click()
  const response = await removal
  expect(response.ok(), `the vehicle should remove ${identifier}`).toBe(true)
  await expect(card, `${identifier} should be uninstalled`).toBeHidden({ timeout: 2 * 60_000 })
}

// Installs or switches to the version from the store dialog, the page has no other way to go down
export async function installFromStore(page: Page, identifier: string, version: string): Promise<void> {
  await page.getByRole('tab', { name: 'Store' }).click()
  await page.getByTestId(`store-extension-${identifier}`).getByTestId('store-extension-open')
    .click({ timeout: 60_000 })
  const menu = await openSelect(page, 'extension-version')
  await menu.getByRole('option', { name: version, exact: true }).click()
  const action = page.getByTestId('extension-action')
  await expect(action, `${version} should not be installed yet`).toHaveText('Install')
  await pull(page, 'POST', () => action.click())
}

export async function updateTo(page: Page, identifier: string, version: string): Promise<void> {
  await page.getByRole('tab', { name: 'Installed' }).click()
  const update = installedCard(page, identifier).getByTestId('installed-extension-update')
  await expect(update, `the page should offer ${version}`).toHaveText(`Update to ${version}`, { timeout: 60_000 })
  await pull(page, 'PUT', () => update.click())
}
