import { expect, Page } from '@playwright/test'

const API = '/disk-usage/v1.0/disk'
const USAGE = `**${API}/usage?*`
export const SPEED_STREAM = `**${API}/speed/stream`
// du on the whole vehicle disk is slow, the page gives it 2 minutes
export const USAGE_TIMEOUT = 120_000
// The page writes and reads 10, 50, 100 and 200 MB, 360 MB at the slowest speed allowed is about a minute
export const SPEED_TIMEOUT = 5 * 60_000

export interface DiskNode {
  name: string
  path: string
  size_bytes: number
  is_dir: boolean
  children: DiskNode[]
}

export interface SpeedPoint {
  size_mb: number
  write_speed: number | null
  read_speed: number | null
  total_tests: number
}

// Header reads "<path>  (<number> <unit>)", e.g. "/var  (1000.0 MB)", the units come from prettifySize
const HEADER = /^(?<path>\/.*?)\s+\((?<size>\d+(\.\d+)?) (?<unit>kB|MB|GB)\)$/

// Does not wait for the header, it is gone while the page lists a folder
async function headerText(page: Page): Promise<string> {
  return (await page.getByTestId('disk-usage-path').allTextContents()).join('').trim()
}

export async function header(page: Page): Promise<{ path: string, size: number, unit: string }> {
  const text = await headerText(page)
  const groups = HEADER.exec(text)?.groups
  expect(groups, `"${text}" should be a disk header`).toBeDefined()
  const { path, size, unit } = groups as Record<string, string>
  expect(Number.isFinite(Number(size)), `${size} should be a number`).toBe(true)
  return { path, size: Number(size), unit }
}

export async function expectPath(page: Page, path: string): Promise<void> {
  await expect.poll(async () => HEADER.exec(await headerText(page))?.groups?.path, {
    message: `the page should show ${path}`, timeout: USAGE_TIMEOUT,
  }).toBe(path)
}

// What the page asks the vehicle next, to compare the page with it
export async function nextUsage(page: Page): Promise<DiskNode> {
  const response = await page.waitForResponse(USAGE, { timeout: USAGE_TIMEOUT })
  expect(response.ok(), 'the vehicle should list the folder').toBe(true)
  return (await response.json()).root
}

// Same order as the page, the biggest first
export function sorted(node: DiskNode): DiskNode[] {
  return [...node.children].sort((a, b) => b.size_bytes - a.size_bytes)
}

// The stream uses the commonwealth streamer framing, base64 JSON fragments split by |\n\n|, heartbeats are fragment -1
export function speedPoints(body: string): SpeedPoint[] {
  const fragments = body.split('|\n\n|').filter(Boolean).map((line) => JSON.parse(line))
  expect(fragments.filter((fragment) => fragment.error), 'the speed test should not fail').toEqual([])
  return fragments
    .filter((fragment) => fragment.fragment >= 0)
    .map((fragment) => JSON.parse(Buffer.from(fragment.data, 'base64').toString()))
}
