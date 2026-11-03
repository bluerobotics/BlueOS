import { expect, test } from '@/fixtures/recorded-test.fixture'

test.describe.configure({ mode: 'serial' })

test.describe('Network Test', { tag: '@network-test' }, () => {
  test('Local network test measures the latency and the speed', async ({ page, pageErrors }) => {
    test.setTimeout(120_000)
    await page.goto('/tools/network-test')
    await expect(page.locator('.v-navigation-drawer').getByRole('link', { name: 'Network Test' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Local network test' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Internet speed test' })).toBeVisible()
    const local = page.locator('.v-card', { hasText: 'Local Network Speed and Latency Test' }).last()
    // The latency is probed over a websocket as soon as the page opens
    await expect(local.getByText(/\d+ ms/)).toBeVisible()
    await expect(local.getByText('Click to start')).toBeVisible()
    // Both requests time out after 20 s and still land on "Test done", so watch for the failure log
    const speedTestErrors: string[] = []
    page.on('console', (message) => {
      if (message.text().startsWith('Failed to do speed test')) speedTestErrors.push(message.text())
    })
    // Moves 100 MB each way
    await local.locator('button:has(.mdi-play)').click()
    await expect(local.getByText('Test done')).toBeVisible({ timeout: 60_000 })
    await expect(local.getByText(/\d+\.\d{2} Mbps/)).toHaveCount(3)
    expect(speedTestErrors).toEqual([])
    expect(pageErrors).toEqual([])
  })

  test('Internet speed test shows the test or waits for internet', async ({ page, pageErrors }) => {
    await page.goto('/tools/network-test')
    await page.getByRole('tab', { name: 'Internet speed test' }).click()
    await expect(page.getByText(/Internet Speed and Latency Test|Waiting for internet connection/).first()).toBeVisible()
    const internet = page.locator('.v-card', { hasText: 'Internet Speed and Latency Test' }).last()
    await expect(internet.locator('.mdi-server-network')).toBeVisible()
    await expect(internet.locator('.mdi-download')).toBeVisible()
    await expect(internet.locator('.mdi-upload')).toBeVisible()
    // Not exercised: pulls from a public server over the vehicle uplink
    await expect(internet.locator('button:has(.mdi-play)')).toBeVisible()
    expect(pageErrors).toEqual([])
  })
})
