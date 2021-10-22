import axios from 'axios'
import {
  Action, getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import notifications from '@/store/notifications'
import { video_manager_service } from '@/types/frontend_services'
import { CreatedStream, Device, StreamStatus } from '@/types/video'

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

    await axios({
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

    return axios({
      method: 'post',
      url: `${this.API_URL}/streams`,
      timeout: 10000,
      data: stream,
    })
      .then(() => true)
      .catch((error) => {
        const message = `Could not create video stream: ${error.message}.`
        notifications.pushError({ service: video_manager_service, type: 'VIDEO_STREAM_CREATION_FAIL', message })
        return false
      })
  }
}

export { VideoStore }

const video: VideoStore = getModule(VideoStore)
export default video
