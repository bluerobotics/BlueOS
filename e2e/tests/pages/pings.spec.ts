import { expect, test } from '@/fixtures/recorded-test.fixture'

test.describe.configure({ mode: 'serial' })

interface PingSensor {
  ping_type: string
  device_id: number
  driver_status: { udp_port: number }
}

test.describe('Ping Sonar Devices', { tag: '@pings' }, () => {
  test('Pings page lists the detected devices or says none are available', async ({ page, pageErrors }) => {
    const sensors: PingSensor[] = await (await page.request.get('/ping/v1.0/sensors')).json()
    await page.goto('/vehicle/pings')
    await expect(page.locator('.v-navigation-drawer').getByRole('link', { name: 'Ping Sonar Devices' })).toBeVisible()
    if (!sensors.length) {
      await expect(page.getByText('No Ping devices available.')).toBeVisible()
    }
    const cards = page.getByRole('main').locator('.v-card:has(> .v-card__title)')
    for (const sensor of sensors) {
      const card = cards.filter({ hasText: sensor.ping_type }).filter({ hasText: `UDP ${sensor.driver_status.udp_port}` })
      await expect(card).toBeVisible()
      // DESTRUCTIVE – not exercised: the "MAVLink Distances" switch enables a driver on the vehicle
      await expect(card.getByRole('row', { name: 'MAVLink Distances' }).getByRole('switch')).toBeVisible()
    }
    if (sensors.length) {
      const first = cards.first()
      await first.locator('button:has(.mdi-chevron-down)').click()
      await expect(first.getByRole('row', { name: `ID ${sensors[0].device_id}` })).toBeVisible()
      await expect(first.getByRole('row', { name: /^FW / })).toBeVisible()
    }
    expect(pageErrors).toEqual([])
  })
})
