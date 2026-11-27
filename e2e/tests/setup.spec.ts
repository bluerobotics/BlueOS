// Runs before the page tests, on the vehicle as it booted: checks that BlueOS detects the board in E2E_BOARD, and
// with E2E_BOARD=none sets up SITL from the frontend, the vehicle the page tests run on
import { changeBoard, expectVehicle } from '@/fixtures/autopilot'
import { BACKEND_TIMEOUT } from '@/fixtures/ui'
import { expect, expectedBoard, test } from '@/fixtures/vehicle'

test.describe.configure({ mode: 'serial' })

test('Autopilot page shows the board connected to the vehicle', async ({ page }) => {
  // The page says there is no board until it gets the current one
  const board = page.waitForResponse('**/ardupilot-manager/v1.0/board')
  await page.goto('/vehicle/autopilot')
  await board
  if (!expectedBoard) {
    await expect(page.getByText('No board running', { exact: true }), 'no board should be running').toBeVisible()
    return
  }
  await expect(page.getByTestId('autopilot-board-name'), `the ${expectedBoard} board should be detected`)
    .toHaveText(expectedBoard)
  await expect(page.getByTestId('autopilot-vehicle-type'), 'the board should run ArduPilot')
    .toContainText(/\(Ardu\w+\)/, { timeout: BACKEND_TIMEOUT })
})

test('SITL can be chosen as the board', async ({ page }) => {
  test.skip(expectedBoard !== undefined, `the vehicle runs its own board, ${expectedBoard}`)
  await page.goto('/vehicle/autopilot')
  await changeBoard(page, /SITL|Software In The Loop/)
  await expect(page.getByTestId('autopilot-board-name'), 'the board should become SITL').toHaveText(/^\s*SITL\s*$/, {
    timeout: BACKEND_TIMEOUT,
  })
  await expectVehicle(page, 'ArduSub')
})
