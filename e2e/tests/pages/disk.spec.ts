import { Page } from '@playwright/test'

import {
  DiskNode, expectPath, header, nextUsage, sorted, SPEED_STREAM, SPEED_TIMEOUT, speedPoints, USAGE_TIMEOUT,
} from '@/fixtures/disk'
import { expect, test } from '@/fixtures/vehicle'

// disktest and the page measure in MiB/s
const MIN_SPEED = 10
// Made up by the kernel, they change while du walks them and some parts can not be read
const KERNEL_FOLDERS = ['/proc', '/sys', '/dev']

function names(page: Page) {
  return page.getByTestId('disk-usage-entry').getByTestId('disk-usage-entry-name')
}

test('Disk page lists the vehicle disk from the biggest entry', async ({ page }) => {
  test.setTimeout(USAGE_TIMEOUT + 30_000)
  const listed = nextUsage(page)
  await page.goto('/tools/disk')
  const root = await listed
  const entries = sorted(root)
  expect(entries.length, 'the vehicle root should have entries').toBeGreaterThan(1)

  await expectPath(page, '/')
  expect((await header(page)).size, 'the root should have a size').toBeGreaterThan(0)
  await expect(names(page)).toHaveText(entries.map((entry) => entry.name))
  const shown = (await names(page).allTextContents())
    .map((name) => root.children.find((entry) => entry.name === name.trim()) as DiskNode)
  shown.slice(1).forEach((entry, index) => {
    expect(entry.size_bytes, `${entry.name} should not be bigger than ${shown[index].name}`)
      .toBeLessThanOrEqual(shown[index].size_bytes)
  })
  await expect(page.getByTestId('disk-usage-entry-usage'))
    .toHaveText(entries.map((entry) => `${(entry.size_bytes / root.size_bytes * 100).toFixed(1)}%`))
  await expect(page.getByTestId('disk-usage-error')).toHaveCount(0)
})

test('Disk page goes into a folder and back up', async ({ page }) => {
  test.setTimeout(5 * USAGE_TIMEOUT)
  const asked: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('/disk-usage/v1.0/disk/usage?')) {
      asked.push(new URL(request.url()).searchParams.get('path') as string)
    }
  })
  const up = page.getByTestId('disk-usage-up')

  let listed = nextUsage(page)
  await page.goto('/tools/disk')
  const root = await listed
  const folder = sorted(root).find((entry) => entry.is_dir && !KERNEL_FOLDERS.includes(entry.path))
  if (!folder) {
    throw new Error('the vehicle root should have a folder')
  }
  await expect(up, 'the root has no parent').toBeDisabled()

  const file = root.children.find((entry) => !entry.is_dir)
  if (file) {
    await test.step('a file does not open', async () => {
      // A notification can cover the last row, the click only needs to reach the row
      await names(page).getByText(file.name, { exact: true }).dispatchEvent('click')
      await expectPath(page, '/')
    })
  }

  const open = async (node: DiskNode): Promise<DiskNode> => {
    listed = nextUsage(page)
    await names(page).getByText(node.name, { exact: true }).click()
    const opened = await listed
    await expectPath(page, node.path)
    await expect(names(page)).toHaveText(sorted(opened).map((entry) => entry.name))
    return opened
  }
  const goUp = async (to: string): Promise<void> => {
    listed = nextUsage(page)
    await up.click()
    expect((await listed).path, `up should go to ${to}`).toBe(to)
  }

  const inside = await test.step(`${folder.path} opens`, () => open(folder))
  const subfolder = sorted(inside).find((entry) => entry.is_dir)
  if (!subfolder) {
    throw new Error(`${folder.path} should have a folder`)
  }
  await test.step(`${subfolder.path} opens`, () => open(subfolder))

  await test.step('up goes back to the root', async () => {
    await goUp(folder.path)
    await goUp('/')
    await expectPath(page, '/')
    await expect(up).toBeDisabled()
  })

  expect(asked, 'only folders should be listed').toEqual(['/', folder.path, subfolder.path, folder.path, '/'])
})

test(`Disk speed test is faster than ${MIN_SPEED} MiB/s`, async ({ page }) => {
  test.setTimeout(SPEED_TIMEOUT + 60_000)
  await page.goto('/tools/disk')
  await page.getByRole('tab', { name: 'Speed Test' }).click()
  const start = page.getByTestId('disk-speed-start')

  await expect(page.getByTestId('disk-speed-state')).toHaveText('Click to start')
  const streamed = page.waitForResponse(SPEED_STREAM)
  await start.click()
  await expect(start, 'only one test runs at a time').toBeDisabled()
  const points = speedPoints(await (await streamed).text())
  await expect(page.getByTestId('disk-speed-state')).toHaveText('Test complete', { timeout: SPEED_TIMEOUT })

  expect(points.map((point) => point.size_mb)).toEqual([10, 50, 100, 200])
  for (const { size_mb: size, write_speed: write, read_speed: read } of points) {
    expect(write, `${size} MB should be written at ${MIN_SPEED} MiB/s or more`).toBeGreaterThanOrEqual(MIN_SPEED)
    expect(read, `${size} MB should be read at ${MIN_SPEED} MiB/s or more`).toBeGreaterThanOrEqual(MIN_SPEED)
  }
  const average = (speeds: number[]): string => (speeds.reduce((a, b) => a + b, 0) / speeds.length).toFixed(2)
  await expect(page.getByTestId('disk-speed-progress')).toHaveText('4/4')
  await expect(page.getByTestId('disk-speed-write'))
    .toHaveText(`${average(points.map((point) => point.write_speed as number))} MiB/s`)
  await expect(page.getByTestId('disk-speed-read'))
    .toHaveText(`${average(points.map((point) => point.read_speed as number))} MiB/s`)
  await expect(page.getByTestId('disk-speed-graph').locator('.apexcharts-xaxis-label tspan'))
    .toHaveText(['10 MB', '50 MB', '100 MB', '200 MB'])
  await expect(page.getByTestId('disk-speed-error')).toHaveCount(0)
  await expect(start).toBeEnabled()
})
