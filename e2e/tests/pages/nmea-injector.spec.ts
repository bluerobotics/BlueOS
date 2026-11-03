import { expect, test } from '@/fixtures/recorded-test.fixture'
import { activeDialog } from '@/fixtures/vehicle'

test.describe.configure({ mode: 'serial' })

const PARAMETERS_TIMEOUT = 90_000

test.describe('NMEA Injector', { tag: '@nmea-injector' }, () => {
  test('NMEA injector page shows the GPS type warning and the sockets', async ({ page, pageErrors }) => {
    test.setTimeout(PARAMETERS_TIMEOUT + 30_000)
    await page.goto('/tools/nmea-injector')
    await expect(page.locator('.v-navigation-drawer').getByRole('link', { name: 'NMEA Injector' })).toBeVisible()
    await expect(page.getByText('The NMEA Injector receives NMEA via UDP or TCP')).toBeVisible()
    // The e2e vehicle has no NMEA source, so its GPS type is never MAV
    await expect(page.getByRole('alert')).toHaveText(/until GPS1?_TYPE is MAV \(14\)\.\s+It is currently \d+\./, {
      timeout: PARAMETERS_TIMEOUT,
    })
    const sockets = page.locator('.injectors-list .v-list-item')
    const empty = page.getByText('No NMEA sockets available. You can add a connection by clicking the + symbol')
    await expect(sockets.or(empty).first()).toBeVisible()
    expect(pageErrors).toEqual([])
  })

  test('New socket dialog shows the socket fields and is cancelled', async ({ page, pageErrors }) => {
    await page.goto('/tools/nmea-injector')
    await page.locator('button:has(.mdi-plus)').click()
    const dialog = activeDialog(page)
    await expect(dialog.getByText('New NMEA socket')).toBeVisible()
    await expect(dialog.locator('.v-select', { has: page.getByLabel('Socket kind') })).toContainText('UDP')
    await dialog.locator('.v-select', { has: page.getByLabel('Socket kind') }).locator('.v-select__slot').click()
    await expect(page.getByRole('option', { name: 'TCP' })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(dialog.getByLabel('Socket port')).toHaveValue(/^\d+$/)
    await expect(dialog.getByLabel('Mavlink component ID', { exact: true })).toHaveValue(/^\d+$/)
    // DESTRUCTIVE – not exercised
    await expect(dialog.getByRole('button', { name: 'Create' })).toBeEnabled()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toBeHidden()
    expect(pageErrors).toEqual([])
  })
})
