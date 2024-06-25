import { StatusCodes } from 'http-status-codes'
import {
  Action, getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import message_manager, { MessageLevel } from '@/libs/message-manager'
import Notifier from '@/libs/notifier'
import store from '@/store'
import { video_manager_service } from '@/types/frontend_services'
import {
  CreatedStream, Device, StreamStatus,
} from '@/types/video'
import back_axios, { backend_offline_error } from '@/utils/api'
import { callPeriodically, stopCallingPeriodically } from '@/utils/helper_functions'

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
        if (error === backend_offline_error) {
          return false
        }
        const message = `Could not create video stream: ${error.response?.data ?? error.message}.`
        notifier.pushError('VIDEO_STREAM_CREATION_FAIL', message, true)
        return false
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
        if (error === backend_offline_error) {
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
        if (error === backend_offline_error) {
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

    this.sources_to_request_thumbnail.forEach(async (source: string) => back_axios({
      method: 'get',
      url: `${this.API_URL}/thumbnail?source=${source}&quality=${quality}&target_height=${target_height}`,
      timeout: 10000,
      responseType: 'blob',
    })
      .then((response) => {
        const old_thumbnail_source = this.thumbnails.get(source)?.source
        if (old_thumbnail_source !== undefined) {
          URL.revokeObjectURL(old_thumbnail_source)
        }
        if (response.status === 200) {
          this.thumbnails.set(source, { source: URL.createObjectURL(response.data), status: response.status })
        }
      })
      .catch((error) => {
        const old_thumbnail_source = this.thumbnails.get(source)?.source
        if (old_thumbnail_source !== undefined) {
          URL.revokeObjectURL(old_thumbnail_source)
        }
        if (error?.response?.status === StatusCodes.SERVICE_UNAVAILABLE) {
          this.thumbnails.set(source, { source: undefined, status: error.response.status })
        } else {
          this.thumbnails.delete(source)
        }
      }))
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
    if (this.sources_to_request_thumbnail.size === 0) {
      callPeriodically(this.fetchThumbnails, 1000)
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
      stopCallingPeriodically(this.fetchThumbnails)
    }
  }
}

export { VideoStore }

const video: VideoStore = getModule(VideoStore)
export default video
