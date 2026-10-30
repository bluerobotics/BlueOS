import { SemVer } from 'semver'

export interface Firmware {
    name: string
    url: URL
}

export enum Vehicle {
    Sub = 'Sub',
    Rover = 'Rover',
    Plane = 'Plane',
    Copter = 'Copter',
    Other = 'Other',
}

export enum FirmwareVehicleType {
  ArduSub = 'ArduSub',
  ArduRover = 'ArduRover',
  ArduPlane = 'ArduPlane',
  ArduCopter = 'ArduCopter',
  Other = 'Unknown',
}

export enum Platform {
  Pixhawk1 = 'Pixhawk1',
  Pixhawk4 = 'Pixhawk4',
  GenericSerial = 'GenericSerial',
  Navigator = 'navigator',
  SITL_X86 = 'SITL_x86_64_linux_gnu',
  SITL_ARM = 'SITL_arm_linux_gnueabihf',
}

export enum EndpointType {
    udpin = 'udpin',
    udpout = 'udpout',
    tcpin = 'tcpin',
    tcpout = 'tcpout',
    serial = 'serial',
    zenoh = 'zenoh',
}

export function vehicleTypeFromString(vehicle_type: string): Vehicle {
  switch (vehicle_type) {
    case 'Sub': return Vehicle.Sub
    case 'Surface Boat': return Vehicle.Rover
    default: return Vehicle.Other
  }
}

export function firmwareVehicleTypeFromVehicle(vehicle: Vehicle): FirmwareVehicleType | null {
  switch (vehicle) {
    case Vehicle.Sub: return FirmwareVehicleType.ArduSub
    case Vehicle.Rover: return FirmwareVehicleType.ArduRover
    case Vehicle.Plane: return FirmwareVehicleType.ArduPlane
    case Vehicle.Copter: return FirmwareVehicleType.ArduCopter
    default: return null
  }
}

const VEHICLE_DOCS_URLS: Partial<Record<FirmwareVehicleType, string>> = {
  [FirmwareVehicleType.ArduSub]: 'https://ardupilot.org/sub/docs/introduction.html#swim-features',
  [FirmwareVehicleType.ArduRover]: 'https://ardupilot.org/rover/docs/rover-features.html',
  [FirmwareVehicleType.ArduCopter]: 'https://ardupilot.org/copter/docs/copter-flight-features.html',
  [FirmwareVehicleType.ArduPlane]: 'https://ardupilot.org/plane/docs/flight-features.html',
}

export function vehicleDocsUrl(firmware_vehicle_type: FirmwareVehicleType | null): string | undefined {
  return firmware_vehicle_type ? VEHICLE_DOCS_URLS[firmware_vehicle_type] : undefined
}

export function userFriendlyEndpointType(type: string): string {
  switch (type) {
    case EndpointType.udpin: return 'UDP Server'
    case EndpointType.udpout: return 'UDP Client'
    case EndpointType.tcpin: return 'TCP Server'
    case EndpointType.tcpout: return 'TCP Client'
    case EndpointType.serial: return 'Serial'
    case EndpointType.zenoh: return 'Zenoh'
    default: return type
  }
}

export function isKnownEndpointType(type: string): boolean {
  return (Object.values(EndpointType) as string[]).includes(type)
}

export interface AutopilotEndpoint {
    name: string
    owner: string
    connection_type: string
    place: string
    argument: number
    persistent: boolean
    protected: boolean
    enabled: boolean
}

export enum FlightControllerFlags {
  is_bootloader = 'is_bootloader',
}

export interface FlightController {
  name: string
  manufacturer: string
  platform: Platform
  path: string
  flags: FlightControllerFlags[]
}

export enum FirmwareType {
  DEV = 'DEV',
  ALPHA = 'ALPHA',
  BETA = 'BETA',
  RC = 'RC',
  STABLE = 'STABLE',
}

export interface FirmwareInfo {
  version: SemVer
  type: FirmwareType
}

export interface SerialEndpoint {
  port: string
  endpoint: string
}
