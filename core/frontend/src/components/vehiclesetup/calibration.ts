import { Sample } from '@eclipse-zenoh/zenoh-ts'

import zenoh from '@/libs/zenoh'
import autopilot_data from '@/store/autopilot'
import back_axios from '@/utils/api'

export enum CalibrationKind {
  GYROSCOPE = 'gyroscope',
  BAROMETER = 'barometer',
  ACCELEROMETER = 'accelerometer',
  SIMPLE_ACCELEROMETER = 'simple_accelerometer',
  BOARD_LEVEL = 'board_level',
  COMPASS = 'compass',
  LARGE_VEHICLE_COMPASS = 'large_vehicle_compass',
}

export enum CalibrationStatus {
  RUNNING = 'running',
  WAITING_FOR_POSITION = 'waiting_for_position',
  DONE = 'done',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
  // The autopilot answered something the backend doesn't know, e.g. a value a newer firmware added
  UNKNOWN = 'unknown',
}

// Ordered as ArduPilot's ACCELCAL_VEHICLE_POS 1 to 6
export enum PoseKey {
  LEVEL = 'level',
  LEFT = 'left',
  RIGHT = 'right',
  NOSE_DOWN = 'nose_down',
  NOSE_UP = 'nose_up',
  BACK = 'back',
}

export interface CalibrationSession {
  job_id: string
  calibration: CalibrationKind
  status: CalibrationStatus
  position: PoseKey | null
  progress: number | null
  fitness: Record<string, number>
  reason: string | null
  reboot_required: boolean
}

export interface StartCalibration {
  calibration: CalibrationKind
  compass_mask?: number
  latitude?: number
  longitude?: number
}

const API_URL = '/vehicle-setup/v1.0'

function isFinished(session: CalibrationSession | null): boolean {
  return [CalibrationStatus.DONE, CalibrationStatus.FAILED, CalibrationStatus.CANCELLED, CalibrationStatus.UNKNOWN]
    .includes(session?.status as CalibrationStatus)
}

export function isRunning(session: CalibrationSession | null): boolean {
  return session !== null && !isFinished(session)
}

// FastAPI answers refusals with a string detail and validation errors with a list of them
function errorMessage(error: unknown): string {
  const { response, message } = error as { response?: { data?: { detail?: unknown } }, message?: string }
  const detail = response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg ?? `${item}`).join(', ')
  }
  return typeof detail === 'string' ? detail : message ?? `${error}`
}

export function statusText(session: CalibrationSession | null): string {
  switch (session?.status) {
    case CalibrationStatus.RUNNING:
    case CalibrationStatus.WAITING_FOR_POSITION:
      return 'Calibrating...'
    case CalibrationStatus.DONE:
      return 'Calibration done.'
    case CalibrationStatus.FAILED:
      return `Calibration failed: ${session.reason}`
    case CalibrationStatus.CANCELLED:
      return session.reason ? `Calibration cancelled: ${session.reason}` : 'Calibration cancelled'
    case CalibrationStatus.UNKNOWN:
      return `Calibration ended in an unknown state: ${session.reason}`
    default:
      return ''
  }
}

export interface ResultAlert {
  type: string
  text: string
}

export function resultAlert(session: CalibrationSession | null, error: string): ResultAlert | undefined {
  if (error) {
    return { type: 'error', text: `Calibration failed: ${error}` }
  }
  switch (session?.status) {
    case CalibrationStatus.DONE:
      return { type: 'success', text: 'Calibration finished' }
    case CalibrationStatus.FAILED:
      return { type: 'error', text: `Calibration failed: ${session.reason}` }
    case CalibrationStatus.CANCELLED:
      return { type: 'warning', text: 'Calibration cancelled' }
    case CalibrationStatus.UNKNOWN:
      return { type: 'error', text: `Calibration ended in an unknown state: ${session.reason}` }
    default:
      return undefined
  }
}

// Replies only say accepted or refused; every state shown comes from the state topics
async function command(name: string, data: object): Promise<string | undefined> {
  try {
    await back_axios({
      method: 'post', url: `${API_URL}/command/${name}`, data, timeout: 10000,
    })
    return undefined
  } catch (error) {
    return errorMessage(error)
  }
}

type Listener = (session: CalibrationSession | null) => void

async function current(name: string): Promise<CalibrationSession | null> {
  const response = await back_axios({ method: 'get', url: `${API_URL}/state/${name}`, timeout: 10000 })
  return response.data
}

// Subscribes before reading the current value, so a change in between isn't lost: the read only fills in what came
// before. Without zenoh the page still gets the current value, just no updates.
function listen(name: string, listener: Listener): () => void {
  let heard = false
  let stopped = false
  function deliver(session: CalibrationSession | null): void {
    if (!stopped) {
      listener(session)
    }
  }
  const subscriber = zenoh.subscriber(`vehicle-setup/state/${name}`, async (sample: Sample) => {
    try {
      const session = JSON.parse(sample.payload().toString()) as CalibrationSession | null
      heard = true
      deliver(session)
    } catch (error) {
      console.error('Invalid vehicle-setup state:', error)
    }
  }).catch((error) => {
    console.error(`Could not subscribe to vehicle-setup state ${name}:`, error)
    return null
  })
  subscriber
    .then(() => current(name))
    .then((session) => {
      if (!heard) {
        deliver(session)
      }
    })
    .catch((error) => console.error(`Could not read vehicle-setup state ${name}:`, error))
  return () => {
    stopped = true
    subscriber.then((active) => active?.undeclare()).catch(() => undefined)
  }
}

/**
 * Follows the backend's calibration state for one kind, on that kind's own topic: the current snapshot right after
 * subscribing, then every change.
 */
export class CalibrationWatcher {
  private last: CalibrationSession | null = null

  private readonly unlisten: () => void

  constructor(
    private readonly kind: CalibrationKind,
    private readonly handler: (session: CalibrationSession) => void,
  ) {
    this.unlisten = listen(`calibration/${kind}`, (session) => this.update(session))
  }

  start(options: Omit<StartCalibration, 'calibration'> = {}): Promise<string | undefined> {
    return command('calibrate', { ...options, calibration: this.kind })
  }

  confirm(): Promise<string | undefined> {
    return this.signal('confirm_position')
  }

  cancel(): Promise<string | undefined> {
    return this.signal('cancel')
  }

  stop(): void {
    this.unlisten()
  }

  private signal(name: string): Promise<string | undefined> {
    const job_id = this.last?.job_id
    return job_id ? command(name, { job_id }) : Promise.resolve('no calibration is running')
  }

  private update(session: CalibrationSession | null): void {
    // null until the first job of this kind
    if (session === null) {
      return
    }
    if (isRunning(this.last) && isFinished(session) && session.reboot_required) {
      autopilot_data.setRebootRequired(true)
    }
    this.last = session
    this.handler(session)
  }
}
