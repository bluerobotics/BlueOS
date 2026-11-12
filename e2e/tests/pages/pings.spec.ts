import { expect, test } from '@/fixtures/vehicle'

test('Pings page lists the devices or says none are available', async ({ page }) => {
  await page.goto('/vehicle/pings')
  const cards = page.getByRole('main').locator('.v-card:has(> .v-card__title)')
  await expect(cards.or(page.getByText('No Ping devices available.')).first()).toBeVisible()
})
