import { StatusCodes } from 'http-status-codes'
import {
  Action, getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import message_manager, { MessageLevel } from '@/libs/message-manager'
import Notifier from '@/libs/notifier'
import { OneMoreTime } from '@/one-more-time'
import store from '@/store'
import { video_manager_service } from '@/types/frontend_services'
import {
  CreatedStream, Device, StreamStatus,
} from '@/types/video'
import back_axios, { isBackendOffline } from '@/utils/api'

export interface Thumbnail {
  source: string | undefined
  status: number | undefined
  roundtripMs: number | undefined
}

const notifier = new Notifier(video_manager_service)

interface ThumbnailFetchState {
  task: OneMoreTime
  sources: Set<string>
  busy: Set<string>
  inProgress: boolean
}

const THUMBNAIL_STATE_KEY = '__blueos_video_thumbnail_state__'
const thumbnailState: ThumbnailFetchState = (window as any)[THUMBNAIL_STATE_KEY] ??= {
  task: new OneMoreTime({ delay: 1000, autostart: false }),
  sources: new Set<string>(),
  busy: new Set<string>(),
  inProgress: false,
}
;(window as any)[THUMBNAIL_STATE_KEY] = thumbnailState
thumbnailState.task.setDelay(1000)

@Module({
  dynamic: true,
  store,
  name: 'video',
})
@Module
class VideoStore extends VuexModule {
  API_URL = '/mavlink-camera-manager'

  available_streams: StreamStatus[] = []

  available_devices: Device[] = []

  updating_streams = true

  updating_devices = true

  fetch_streams_error: string | null = null

  fetch_devices_error: string | null = null

  thumbnails: Map<string, Thumbnail> = new Map()

  @Mutation
  setUpdatingStreams(updating: boolean): void {
    this.updating_streams = updating
  }

  @Mutation
  setUpdatingDevices(updating: boolean): void {
    this.updating_devices = updating
  }

  @Mutation
  setFetchStreamsError(error: string | null): void {
    this.fetch_streams_error = error
  }

  @Mutation
  setFetchDevicesError(error: string | null): void {
    this.fetch_devices_error = error
  }

  @Mutation
  setAvailableStreams(available_streams: StreamStatus[]): void {
    this.available_streams = available_streams
    this.updating_streams = false
  }

  @Mutation
  setAvailableDevices(available_devices: Device[]): void {
    this.available_devices = available_devices
    this.updating_devices = false
  }

  @Action
  async deleteStream(stream: StreamStatus): Promise<void> {
    this.setUpdatingStreams(true)

    await back_axios({
      method: 'delete',
      url: `${this.API_URL}/delete_stream`,
      timeout: 10000,
      params: { name: stream.video_and_stream.name },
    }).catch((error) => {
      const message = `Could not delete video stream: ${error.message}.`
      notifier.pushError('VIDEO_STREAM_DELETE_FAIL', message)
    })
      .finally(() => {
        this.setUpdatingStreams(false)
      })
  }

  @Action
  async createStream(stream: CreatedStream): Promise<boolean> {
    this.setUpdatingStreams(true)

    return back_axios({
      method: 'post',
      url: `${this.API_URL}/streams`,
      timeout: 10000,
      data: stream,
    })
      .then(() => true)
      .catch((error) => {
        if (isBackendOffline(error)) {
          return false
        }
        const message = `Could not create video stream: ${error.response?.data ?? error.message}.`
        notifier.pushError('VIDEO_STREAM_CREATION_FAIL', message, true)
        return false
      })
      .finally(() => {
        this.setUpdatingStreams(false)
      })
  }

  @Action
  async fetchDevices(): Promise<void> {
    this.setFetchDevicesError(null)

    await back_axios({
      method: 'get',
      url: `${this.API_URL}/v4l`,
      timeout: 10000,
    })
      .then((response) => {
        this.setAvailableDevices(response.data)
      })
      .catch((error) => {
        this.setAvailableDevices([])
        if (isBackendOffline(error)) {
          return
        }

        const message = `Could not fetch video devices: ${error.message}`
        this.setFetchDevicesError(message)
        notifier.pushError('VIDEO_DEVICES_FETCH_FAIL', message)
      })
  }

  @Action
  async fetchStreams(): Promise<void> {
    this.setFetchStreamsError(null)

    await back_axios({
      method: 'get',
      url: `${this.API_URL}/streams`,
      timeout: 10000,
    })
      .then((response) => {
        this.setAvailableStreams(response.data)
      })
      .catch((error) => {
        this.setAvailableStreams([])
        if (isBackendOffline(error)) {
          return
        }
        const message = `Could not fetch video streams: ${error.message}`
        this.setFetchStreamsError(message)
        notifier.pushError('VIDEO_STREAMS_FETCH_FAIL', message)
      })
  }

  @Action
  async fetchThumbnails(): Promise<void> {
    if (thumbnailState.inProgress) return
    thumbnailState.inProgress = true

    const target_height = 150
    const quality = 75

    const requests: Promise<void>[] = []

    thumbnailState.sources.forEach(async (source: string) => {
      if (thumbnailState.busy.has(source)) {
        return
      }
      thumbnailState.busy.add(source)

      const requestStart = Date.now()
      const request = back_axios({
        method: 'get',
        url: `${this.API_URL}/thumbnail?source=${source}&quality=${quality}&target_height=${target_height}`,
        timeout: 10000,
        responseType: 'blob',
      })
        .then((response) => {
          if (response.status === 200) {
            const roundtripMs = Date.now() - requestStart
            const old_thumbnail_source = this.thumbnails.get(source)?.source
            if (old_thumbnail_source !== undefined) {
              URL.revokeObjectURL(old_thumbnail_source)
            }

            this.thumbnails.set(source, {
              source: URL.createObjectURL(response.data), status: response.status, roundtripMs,
            })
          }
        })
        .catch((error) => {
          const roundtripMs = Date.now() - requestStart
          if (error?.response?.status === StatusCodes.SERVICE_UNAVAILABLE) {
            const existing = this.thumbnails.get(source)
            if (existing?.source) {
              this.thumbnails.set(source, { source: existing.source, status: error.response.status, roundtripMs })
            } else {
              this.thumbnails.set(source, { source: undefined, status: error.response.status, roundtripMs })
            }
          } else {
            this.thumbnails.delete(source)
          }
        })
        .finally(() => {
          thumbnailState.busy.delete(source)
        })

      requests.push(request)
    })

    try {
      await Promise.allSettled(requests)
    } finally {
      thumbnailState.inProgress = false
    }
  }

  @Action
  async blockSource(source: string): Promise<void> {
    await back_axios({
      method: 'post',
      url: `${this.API_URL}/block_source`,
      timeout: 10000,
      params: { source_string: source },
    })
      .then(() => {
        this.fetchDevices()
        this.fetchStreams()
      })
      .catch((error) => {
        const message = `Could not block video source: ${error.message}.`
        notifier.pushError('VIDEO_SOURCE_BLOCK_FAIL', message)
      })
  }

  @Action
  async unblockSource(source: string): Promise<void> {
    await back_axios({
      method: 'post',
      url: `${this.API_URL}/unblock_source`,
      timeout: 10000,
      params: { source_string: source },
    })
      .then(() => {
        this.fetchDevices()
        this.fetchStreams()
      })
      .catch((error) => {
        const message = `Could not unblock video source: ${error.message}.`
        notifier.pushError('VIDEO_SOURCE_UNBLOCK_FAIL', message)
      })
  }

  @Action
  async resetSettings(): Promise<void> {
    await back_axios({
      url: `${this.API_URL}/reset_settings`,
      method: 'post',
      params: {
        all: true,
      },
      timeout: 5000,
    })
      .then(() => {
        message_manager.emitMessage(MessageLevel.Success, 'Stream configuration set to factory default')
      })
      .catch((error) => {
        notifier.pushBackError('RESET_VIDEO_SETTINGS_FAIL', error, true)
      })
  }

  // eslint-disable-next-line class-methods-use-this
  @Action
  startGetThumbnailForDevice(source: string): void {
    thumbnailState.sources.add(source)
    const task = thumbnailState.task as any
    if (task.isPaused) {
      thumbnailState.task.resume()
    } else if (!task.isRunning && !task.timeoutId) {
      thumbnailState.task.start()
    }
  }

  // eslint-disable-next-line class-methods-use-this
  @Action
  stopGetThumbnailForDevice(source: string): void {
    thumbnailState.sources.delete(source)

    if (thumbnailState.sources.size === 0) {
      thumbnailState.task.stop()
    }
  }
}

export { VideoStore }

const video: VideoStore = getModule(VideoStore)

thumbnailState.task.setAction(video.fetchThumbnails)

export default video
