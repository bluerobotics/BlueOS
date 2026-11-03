import { FullConfig } from '@playwright/test'

import { setPirateMode, withBrowser } from './fixtures/vehicle'

export default async function globalTeardown(config: FullConfig): Promise<void> {
  await withBrowser(config, (page) => setPirateMode(page, false))
}
