import { FullConfig } from '@playwright/test'

import { setPirateMode, withBrowser } from './fixtures/vehicle'

export default async function globalSetup(config: FullConfig): Promise<void> {
  await withBrowser(config, (page) => setPirateMode(page, true))
}
