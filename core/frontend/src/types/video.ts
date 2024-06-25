export interface FrameInterval {
  denominator: number
  numerator: number
}

export interface Size {
  height: number
  width: number
  intervals: FrameInterval[]
}

export enum VideoEncodeType {
  H265 = 'H265',
  H264 = 'H264',
  MJPG = 'MJPG',
  YUYV = 'YUYV',
}

export enum StreamType {
  RTSP = 'RTSP',
  UDP = 'UDP',
  RTSPU = 'RTSPU',
  RTSPT = 'RTSPT',
  RTSPH = 'RTSPH',
}

export interface Format {
  encode: VideoEncodeType
  sizes: Size[]
}

export interface ControlOption {
  name: string
  value: number
}

export interface MenuConfigType {
  default: number
  value: number
  options: ControlOption
}

export interface MenuConfig {
  Menu: MenuConfigType
}

export interface BoolConfigType {
  default: number
  value: number
}

export interface BoolConfig {
  Bool: BoolConfigType
}

export interface SliderConfigType {
  default: number
  max: number
  min: number
  step: number
  value: number
}

export interface SliderConfig {
  Slider: SliderConfigType
}

export interface ControlState {
  is_disabled: boolean
  is_inactive: boolean
}

export interface Control {
  configuration: MenuConfig | BoolConfig | SliderConfig
  state: ControlState
  cpp_type: string
  id: number
  name: string
}

export interface Menu extends Control {
  configuration: MenuConfig
}

export interface Bool extends Control {
  configuration: BoolConfig
}

export interface Slider extends Control {
  configuration: SliderConfig
}

export interface Device {
  name: string
  source: string
  formats: Format[]
  controls: Control[]
}

export enum VideoCaptureType {
  Video = 'video',
  Redirect = 'redirect',
}

export interface CaptureConfiguration {
  type?: VideoCaptureType
  encode?: VideoEncodeType
  height?: number
  width?: number
  frame_interval?: FrameInterval
}

export interface ExtendedConfiguration {
  thermal: boolean
  disable_mavlink: boolean
}

export interface StreamInformation {
  endpoints: string[]
  configuration: CaptureConfiguration
  extended_configuration: ExtendedConfiguration | undefined
}

export interface CreatedStream {
  name: string
  source: string
  stream_information: StreamInformation
}

export interface UsbBusType {
  Usb: string
}

export interface IspType {
  Isp: string
}

export interface VideoSourceLocalType {
  name: string
  device_path: string
  type: UsbBusType | IspType
}

export interface VideoSourceLocal {
  Local: VideoSourceLocalType
}

export interface VideoSourceRedirect {
  name: string
  source: {
    Redirect: string
  }
}

export interface VideoSourceFake {
  Fake: string
}

export interface VideoSourceGstType {
  name: string
  source: VideoSourceFake
}

export interface VideoSourceGst {
  Gst: VideoSourceGstType
}

export interface VideoAndStreamInformation {
  name: string
  stream_information: StreamInformation
  video_source: VideoSourceLocal | VideoSourceGst | VideoSourceRedirect
}

export interface StreamStatus {
  running: boolean
  video_and_stream: VideoAndStreamInformation
}

export interface VideoDimensions {
  height: number
  width: number
}

export interface StreamPrototype {
  name: string
  encode?: VideoEncodeType
  dimensions?: VideoDimensions
  interval?: FrameInterval
  endpoints: string[]
  thermal: boolean
  disable_mavlink: boolean
}
