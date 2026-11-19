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

const API_URL = '/vehicle-setup/v1.0/command'

function isFinished(session: CalibrationSession | null): boolean {
  return [CalibrationStatus.DONE, CalibrationStatus.FAILED, CalibrationStatus.CANCELLED]
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
    default:
      return undefined
  }
}

// Replies only say accepted or refused; every state shown comes from the websocket
async function command(name: string, data: object): Promise<string | undefined> {
  try {
    await back_axios({
      method: 'post', url: `${API_URL}/${name}`, data, timeout: 10000,
    })
    return undefined
  } catch (error) {
    return errorMessage(error)
  }
}

type Listener = (session: CalibrationSession | null) => void

// One websocket for every watcher on the page, open while any of them listens
const listeners = new Map<string, Set<Listener>>()
let socket: WebSocket | undefined
let retry: ReturnType<typeof setTimeout> | undefined
let backoff_ms = 1000
// The server sends a topic's current value only on subscribe, so watchers joining a subscribed topic replay this
const latest = new Map<string, CalibrationSession | null>()

function send(message: object): void {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(message))
  }
}

function connect(): void {
  retry = undefined
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const current = new WebSocket(`${protocol}://${window.location.host}/vehicle-setup/ws`)
  socket = current
  // The server sends the current value on every subscribe, so a reconnect needs no extra fetch
  current.onopen = () => {
    backoff_ms = 1000
    listeners.forEach((_, topic) => send({ subscribe: topic }))
  }
  current.onmessage = (event: MessageEvent) => {
    try {
      const { topic, payload } = JSON.parse(event.data)
      const topic_listeners = listeners.get(topic)
      if (!topic_listeners) {
        return
      }
      const session = payload as CalibrationSession | null
      latest.set(topic, session)
      topic_listeners.forEach((listener) => {
        try {
          listener(session)
        } catch (error) {
          console.error('Calibration listener failed:', error)
        }
      })
    } catch (error) {
      console.error('Invalid vehicle-setup message:', error)
    }
  }
  current.onclose = () => {
    socket = undefined
    if (listeners.size) {
      retry = setTimeout(connect, backoff_ms)
      backoff_ms = Math.min(backoff_ms * 2, 30000)
    }
  }
}

function listen(topic: string, listener: Listener): () => void {
  const topic_listeners = listeners.get(topic) ?? new Set<Listener>()
  const first = !topic_listeners.size
  topic_listeners.add(listener)
  listeners.set(topic, topic_listeners)
  if (!socket && !retry) {
    connect()
  } else if (first) {
    send({ subscribe: topic })
  } else if (latest.has(topic)) {
    listener(latest.get(topic) as CalibrationSession | null)
  }
  return () => {
    topic_listeners.delete(listener)
    if (topic_listeners.size) {
      return
    }
    listeners.delete(topic)
    latest.delete(topic)
    send({ unsubscribe: topic })
    if (!listeners.size) {
      clearTimeout(retry)
      retry = undefined
      if (socket) {
        socket.onclose = null
        socket.close()
        socket = undefined
      }
    }
  }
}

/**
 * Follows the backend's calibration state for one kind, on that kind's own topic: the current snapshot as soon as
 * the websocket subscribes, then every change.
 */
export class CalibrationWatcher {
  private last: CalibrationSession | null = null

  private readonly unlisten: () => void

  constructor(
    private readonly kind: CalibrationKind,
    private readonly handler: (session: CalibrationSession) => void,
  ) {
    this.unlisten = listen(`vehicle-setup/state/calibration/${kind}`, (session) => this.update(session))
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
