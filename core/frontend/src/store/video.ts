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
}

const notifier = new Notifier(video_manager_service)

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

  private sources_to_request_thumbnail: Set<string> = new Set()

  private busy_sources: Set<string> = new Set()

  fetchThumbnailsTask = new OneMoreTime(
    { delay: 1000, autostart: false },
  )

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
    const target_height = 150
    const quality = 75

    const requests: Promise<void>[] = []

    this.sources_to_request_thumbnail.forEach(async (source: string) => {
      if (this.busy_sources.has(source)) {
        return
      }
      this.busy_sources.add(source)

      const request = back_axios({
        method: 'get',
        url: `${this.API_URL}/thumbnail?source=${source}&quality=${quality}&target_height=${target_height}`,
        timeout: 10000,
        responseType: 'blob',
      })
        .then((response) => {
          if (response.status === 200) {
            const old_thumbnail_source = this.thumbnails.get(source)?.source
            if (old_thumbnail_source !== undefined) {
              URL.revokeObjectURL(old_thumbnail_source)
            }

            this.thumbnails.set(source, { source: URL.createObjectURL(response.data), status: response.status })
          }
        })
        .catch((error) => {
          if (error?.response?.status === StatusCodes.SERVICE_UNAVAILABLE) {
            this.thumbnails.set(source, { source: undefined, status: error.response.status })
          } else {
            this.thumbnails.delete(source)
          }
        })
        .finally(() => {
          this.busy_sources.delete(source)
        })

      requests.push(request)
    })

    await Promise.allSettled(requests)
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

  @Action
  startGetThumbnailForDevice(source: string): void {
    if (this.sources_to_request_thumbnail.size > 0) {
      this.fetchThumbnailsTask.resume()
    } else {
      this.fetchThumbnailsTask.start()
    }
    this.sources_to_request_thumbnail.add(source)
  }

  @Action
  stopGetThumbnailForDevice(source: string): void {
    const old_thumbnail_source = this.thumbnails.get(source)?.source
    if (old_thumbnail_source !== undefined) {
      URL.revokeObjectURL(old_thumbnail_source)
    }
    this.sources_to_request_thumbnail.delete(source)

    if (this.sources_to_request_thumbnail.size === 0) {
      this.fetchThumbnailsTask.stop()
    }
  }
}

export { VideoStore }

const video: VideoStore = getModule(VideoStore)

video.fetchThumbnailsTask.setAction(video.fetchThumbnails)

export default video
