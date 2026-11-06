import { expect, test } from '@/fixtures/recorded-test.fixture'
import { activeDialog, PIRATE_MODE_BUTTON } from '@/fixtures/vehicle'

test.describe.configure({ mode: 'serial' })

const PAGES = [
  'Autopilot Firmware', 'Autopilot Parameters', 'Available Services', 'Bag Editor', 'BlueOS Version',
  'Extensions Beta', 'File Browser', 'Log Browser', 'MAVLink Endpoints', 'MAVLink Inspector', 'NMEA Injector',
  'Network Test', 'Ping Sonar Devices', 'Serial Bridges', 'System Information', 'Terminal', 'Vehicle Setup',
  'Video Streams',
]

test.describe('App shell', { tag: '@shell' }, () => {
  test('Sidebar lists every page including the pirate mode ones', async ({ page, pageErrors }) => {
    await page.goto('/')
    const drawer = page.locator('.v-navigation-drawer')
    await expect(drawer.getByRole('img', { name: 'Blue Robotics Logo' })).toBeVisible()
    for (const name of PAGES) {
      await expect(drawer.getByRole('link', { name, exact: true })).toBeVisible()
    }
    await drawer.getByRole('link', { name: 'System Information', exact: true }).click()
    await expect(page).toHaveURL('/tools/system-information')
    await drawer.getByRole('img', { name: 'Blue Robotics Logo' }).click()
    await expect(page).toHaveURL('/')
    await expect(drawer.getByText('BlueOS Version:')).toBeVisible()
    await expect(drawer.getByText(/Build:/)).toBeVisible()
    expect(pageErrors).toEqual([])
  })

  test('Power dialog lists the power actions without running them', async ({ page, pageErrors }) => {
    await page.goto('/')
    await page.locator('#power-menu-button button').click()
    const dialog = activeDialog(page)
    await expect(dialog.getByText('Power', { exact: true })).toBeVisible()
    for (const action of ['Restart Autopilot', 'Restart Core container', 'Reboot', 'Power off']) {
      // DESTRUCTIVE – not exercised
      await expect(dialog.getByRole('button', { name: action, exact: true })).toBeVisible()
    }
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    expect(pageErrors).toEqual([])
  })

  test('Report dialog and settings button open their targets', async ({ page, pageErrors }) => {
    await page.goto('/')
    await page.locator('#feature-request-button button').click()
    const dialog = activeDialog(page)
    await expect(dialog.getByText('Bug report / Feature request')).toBeVisible()
    await expect(dialog.getByRole('button', { name: 'With GitHub' })).toBeVisible()
    await expect(dialog.getByRole('button', { name: 'On Blue Robotics forum' })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    await page.locator('#settings-menu-button button').click()
    await expect(page).toHaveURL('/settings')
    expect(pageErrors).toEqual([])
  })

  test('Tray menus open and close', async ({ page, pageErrors }) => {
    await page.goto('/')
    await page.locator('#notifications-tray-menu-button').click()
    await expect(page.getByText('Notifications', { exact: true })).toBeVisible()
    await page.keyboard.press('Escape')

    await page.locator('.mdi-heart-pulse, .mdi-heart-broken').first().click()
    await expect(page.getByText('Core Temperature:')).toBeVisible()
    await page.keyboard.press('Escape')

    await page.locator(PIRATE_MODE_BUTTON).click()
    await expect(page.getByRole('button', { name: 'Disable Pirate Mode' })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('button', { name: 'Disable Pirate Mode' })).toBeHidden()

    await page.locator('#wifi-tray-menu-button').click()
    await expect(page.getByText('Wifi', { exact: true })).toBeVisible()
    // DESTRUCTIVE – not exercised: hotspot toggle, connect, forget, disconnect
    await expect(page.locator('button:has(.mdi-access-point, .mdi-access-point-off)')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByText('Wifi', { exact: true })).toBeHidden()

    await page.locator('#ethernet-tray-menu-button').click()
    const interfaces = page.getByRole('button', { name: /(Not )?connected$/ })
    await expect(interfaces.or(page.getByText(/No ethernet interfaces available|Fetching available ethernet/)).first())
      .toBeVisible()
    // DESTRUCTIVE – not exercised: static IP, dynamic IP, DHCP server, address delete
    await page.keyboard.press('Escape')

    await page.locator('.mdi-web, .mdi-web-off, .mdi-web-minus, .mdi-web-refresh, .mdi-dns').first().click()
    const dialog = activeDialog(page)
    await expect(dialog.getByRole('tab', { name: 'Network Interface Priority' })).toBeVisible()
    await expect(dialog.getByRole('tab', { name: 'Dns Configuration' })).toBeVisible()
    // DESTRUCTIVE – not exercised
    await expect(dialog.getByRole('button', { name: 'Apply' })).toBeVisible()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toBeHidden()
    expect(pageErrors).toEqual([])
  })
})
