import { Module, Mutation, VuexModule } from 'vuex-module-decorators'

import store from '@/store'
import { Device, StreamStatus } from '@/types/video'

@Module({
  dynamic: true,
  store,
  name: 'video_store',
})

@Module
export default class VideoStore extends VuexModule {
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
}
