import { expect, test } from '@/fixtures/recorded-test.fixture'
import { activeDialog } from '@/fixtures/vehicle'

test.describe.configure({ mode: 'serial' })

test.describe('BlueOS Version', { tag: '@version-chooser' }, () => {
  test('Version chooser lists the running, local and remote versions', async ({ page, pageErrors }) => {
    const current: { repository: string, tag: string, sha: string } =
      await (await page.request.get('/version-chooser/v1.0/version/current')).json()
    await page.goto('/tools/version-chooser')
    await expect(page.locator('.v-navigation-drawer').getByRole('link', { name: 'BlueOS Version' })).toBeVisible()
    // Global setup turns pirate mode on, which shows every section
    for (const heading of ['Local Versions', 'Remote Versions', 'Manual Upload']) {
      await expect(page.getByRole('heading', { name: heading })).toBeVisible({ timeout: 30_000 })
    }
    const shortSha = current.sha.replace('sha256:', '').slice(0, 8)
    const running = page.locator('.v-card', { hasText: 'Running' }).filter({ hasText: shortSha }).last()
    await expect(running).toContainText(current.tag)
    await expect(running).toContainText(current.repository)
    const local = page.locator('.v-card', { has: page.getByRole('heading', { name: 'Local Versions' }) })
    await expect(local.getByText(/^[0-9a-f]{8} - /).first()).toBeVisible()
    // DESTRUCTIVE – not exercised
    await expect(page.getByRole('button', { name: 'Apply', exact: true }).first()).toBeVisible()
    // DESTRUCTIVE – not exercised
    await expect(page.getByRole('button', { name: 'Delete', exact: true }).first()).toBeVisible()
    const remote = page.locator('.v-card', { has: page.getByRole('heading', { name: 'Remote Versions' }) })
    await expect(remote.getByLabel('Remote repository')).toHaveValue(/^[\w-]+\/[\w-]+$/)
    await expect(remote.getByText('Loading remote images...')).toBeHidden({ timeout: 60_000 })
    // DockerHub rate limits anonymous pulls, the page reports it instead of listing the tags
    await expect(remote.locator('.mdi-earth').or(remote.getByRole('alert')).first()).toBeVisible()
    // DESTRUCTIVE – not exercised
    await expect(page.getByRole('button', { name: 'Upload', exact: true })).toBeVisible()
    expect(pageErrors).toEqual([])
  })

  test('Docker login dialog opens and is cancelled', async ({ page, pageErrors }) => {
    await page.goto('/tools/version-chooser')
    await page.getByRole('button', { name: 'Docker Login' }).click({ timeout: 30_000 })
    const dialog = activeDialog(page)
    await expect(dialog.getByRole('tab', { name: 'Login' })).toBeVisible()
    await expect(dialog.getByRole('tab', { name: 'Accounts' })).toBeVisible()
    await expect(dialog.getByLabel('Docker Username')).toBeVisible()
    await expect(dialog.getByLabel('Docker Password or PAT')).toBeVisible()
    // DESTRUCTIVE – not exercised
    await expect(dialog.getByRole('button', { name: 'Login', exact: true })).toBeVisible()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toBeHidden()
    expect(pageErrors).toEqual([])
  })
})
