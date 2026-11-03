import { expect, test } from '@/fixtures/recorded-test.fixture'

test.describe.configure({ mode: 'serial' })

test.describe('System Information', { tag: '@system-information' }, () => {
  test('System monitor tab shows the resource cards', async ({ page, pageErrors }) => {
    await page.goto('/tools/system-information')
    await expect(page.locator('.v-navigation-drawer').getByRole('link', { name: 'System Information' })).toBeVisible()
    const tabs = ['System Monitor', 'Processes', 'Network', 'USB', 'Kernel', 'Journal', 'Firmware', 'About']
    for (const tab of tabs) {
      await expect(page.getByRole('tab', { name: tab })).toBeVisible()
    }
    for (const card of ['Memory', 'Disk', 'Temperature']) {
      await expect(page.getByRole('main').getByText(card, { exact: true })).toBeVisible()
    }
    expect(pageErrors).toEqual([])
  })

  test('Every tab renders its content', async ({ page, pageErrors }) => {
    await page.goto('/tools/system-information')
    await page.getByRole('tab', { name: 'Processes' }).click()
    await expect(page.getByLabel('Search')).toBeVisible()
    await expect(page.getByRole('columnheader', { name: /^PID/ })).toBeVisible()

    await page.getByRole('tab', { name: 'Network' }).click()
    await expect(page.getByText('MAC:').first()).toBeVisible()

    await page.getByRole('tab', { name: 'USB' }).click()
    await expect(page.getByText(/USB Bus|No USB devices found|Failed to fetch USB devices/).first())
      .toBeVisible({ timeout: 30_000 })

    for (const tab of ['Kernel', 'Journal', 'Firmware']) {
      await page.getByRole('tab', { name: tab }).click()
      await expect(page.getByRole('tab', { name: tab })).toHaveAttribute('aria-selected', 'true')
    }
    // DESTRUCTIVE – not exercised: the Firmware tab "Update" button

    await page.getByRole('tab', { name: 'About' }).click()
    await expect(page.getByText('Hostname')).toBeVisible()
    expect(pageErrors).toEqual([])
  })
})
