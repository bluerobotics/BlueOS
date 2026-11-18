import { Locator, Page } from '@playwright/test'

import { expect, test } from '@/fixtures/vehicle'

// The model loads and decodes on the vehicle, slower than the other cards
const MODEL_TIMEOUT = 30_000

function card(page: Page, title: string): Locator {
  return page.getByTestId('home-card').filter({ has: page.getByText(title, { exact: true }) })
}

test('Dashboard shows the app cards', async ({ page }) => {
  await page.goto('/')
  for (const title of ['Digital Twin', 'System Information', 'Ethernet Status', 'WiFi Status']) {
    await expect(card(page, title)).toBeVisible()
  }
})

test('Digital Twin loads the ROV or boat model', async ({ page }) => {
  await page.goto('/')
  const model = card(page, 'Digital Twin').locator('model-viewer')
  // rover/unknown.glb is the fallback when the vehicle has no model
  await expect(model, 'the model should be a ROV or the boat')
    .toHaveAttribute('src', /\/models\/(sub\/\w+|rover\/BOAT)\.glb$/, { timeout: MODEL_TIMEOUT })
  await expect.poll(() => model.evaluate((viewer: Element & { loaded?: boolean }) => viewer.loaded), {
    message: 'the model should load',
    timeout: MODEL_TIMEOUT,
  }).toBe(true)
})

test('System Information shows the CPU, memory and disk usage between 0 and 100%', async ({ page }) => {
  await page.goto('/')
  const usages = card(page, 'System Information').getByRole('progressbar')
  await expect(usages).toHaveCount(3)
  // The widget shows 0% until the data arrives, a running system always uses some memory and disk
  const [cpu, memory, disk] = await usages.all()
  for (const [usage, minimum] of [[cpu, 0], [memory, 1], [disk, 1]] as const) {
    const value = async (): Promise<number> => Number(await usage.getAttribute('aria-valuenow'))
    await expect.poll(value, { message: 'the usage should arrive' }).toBeGreaterThanOrEqual(minimum)
    expect(await value(), 'the usage should be at most 100%').toBeLessThanOrEqual(100)
  }
})

for (const title of ['Ethernet Status', 'WiFi Status']) {
  test(`${title} shows the received and sent rates`, async ({ page }) => {
    const network = page.waitForResponse('**/system-information/system/network')
    await page.goto('/')
    // The widget shows 0.00Mbps when its interface is missing, so the interface has to be in the data
    const name = (await card(page, title).getByTestId('network-interface').innerText()).trim()
    // The frontend turns the bytes of each probe into the rates
    const interfaces: { name: string, received_B: unknown, transmitted_B: unknown }[] = await (await network).json()
    const data = interfaces.find((iface) => iface.name === name)
    expect(data, `${name} should be in the network data`).toBeDefined()
    expect(typeof data?.received_B, `${name} should have the received bytes`).toBe('number')
    expect(typeof data?.transmitted_B, `${name} should have the sent bytes`).toBe('number')
    for (const rate of ['network-received', 'network-sent']) {
      await expect(card(page, title).getByTestId(rate), 'the rate should be a number in Mbps')
        .toHaveText(/^\s*\d+(\.\d+)?Mbps\s*$/)
    }
  })
}
