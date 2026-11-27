import {
  COCKPIT, expectInstalled, INSTALL_TIMEOUT, installedCard, installFromStore, lastVersions, uninstall, updateTo,
} from '@/fixtures/extensions'
import { expect, test } from '@/fixtures/vehicle'

test('Extensions page lists the installed extensions', async ({ page }) => {
  const installed: { docker: string }[] = await (await page.request.get('/kraken/v1.0/installed_extensions')).json()
  await page.goto('/tools/extensions-manager')
  await page.getByRole('tab', { name: 'Installed' }).click()
  const expected = installed.length ? installed[0].docker : 'No Extensions installed.'
  await expect(page.getByText(expected).first()).toBeVisible({ timeout: 60_000 })
})

test('Cockpit goes through install, downgrade and upgrade', async ({ page }) => {
  // Every step pulls an image on the vehicle
  test.setTimeout(4 * INSTALL_TIMEOUT)
  const { latest, previous } = await lastVersions(page, COCKPIT)
  await page.goto('/tools/extensions-manager')

  await page.getByRole('tab', { name: 'Installed' }).click()
  await expect(installedCard(page, COCKPIT), 'Cockpit should be installed').toBeVisible({ timeout: 60_000 })

  await uninstall(page, COCKPIT)
  await installFromStore(page, COCKPIT, latest)
  await expectInstalled(page, COCKPIT, latest)

  await installFromStore(page, COCKPIT, previous)
  await expectInstalled(page, COCKPIT, previous)

  await uninstall(page, COCKPIT)
  await installFromStore(page, COCKPIT, previous)
  await expectInstalled(page, COCKPIT, previous)

  await updateTo(page, COCKPIT, latest)
  await expectInstalled(page, COCKPIT, latest)
})
