import {
  Action, getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import notifications from '@/store/notifications'
import { video_manager_service } from '@/types/frontend_services'
import { CreatedStream, Device, StreamStatus } from '@/types/video'
import back_axios, { backend_offline_error } from '@/utils/api'

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

  @Mutation
  setUpdatingStreams(updating: boolean): void { this.updating_streams = updating }

  @Mutation
  setUpdatingDevices(updating: boolean): void { this.updating_devices = updating }

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
    })
      .catch((error) => {
        const message = `Could not delete video stream: ${error.message}.`
        notifications.pushError({ service: video_manager_service, type: 'VIDEO_STREAM_DELETE_FAIL', message })
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
        if (error === backend_offline_error) { return false }
        const message = `Could not create video stream: ${error.message}. ${error.response.data}.`
        notifications.pushError({ service: video_manager_service, type: 'VIDEO_STREAM_CREATION_FAIL', message })
        return false
      })
  }

  @Action
  async fetchDevices(): Promise<void> {
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
        if (error === backend_offline_error) { return }
        const message = `Could not fetch video devices: ${error.message}`
        notifications.pushError({ service: video_manager_service, type: 'VIDEO_DEVICES_FETCH_FAIL', message })
      })
  }

  @Action
  async fetchStreams(): Promise<void> {
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
        if (error === backend_offline_error) { return }
        const message = `Could not fetch video streams: ${error.message}`
        notifications.pushError({ service: video_manager_service, type: 'VIDEO_STREAMS_FETCH_FAIL', message })
      })
  }
}

export { VideoStore }

const video: VideoStore = getModule(VideoStore)
export default video
