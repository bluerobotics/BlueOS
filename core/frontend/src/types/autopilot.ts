import { SemVer } from 'semver'

export interface Firmware {
    name: string
    url: URL
    platform: string
    board_id?: number
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

export interface Platform {
  name: string
  platform_type: PlatformType
  board_id?: number
}

export enum PlatformType {
  Serial = 'Serial',
  Linux = 'Linux',
  SITL = 'SITL',
  Unknown = 'Unknown',
  Manual = 'Manual',
}

// Mirrors the SITLFrame enum from
// core/services/ardupilot_manager/typedefs.py
export enum SITLFrame {
  QUADPLANE = 'quadplane',
  XPLANE = 'xplane',
  FIREFLY = 'firefly',
  PLUS_CONFIG = '+',
  QUAD = 'quad',
  COPTER = 'copter',
  X_CONFIG = 'x',
  BFXREV = 'bfxrev',
  BFX = 'bfx',
  DJIX = 'djix',
  CWX = 'cwx',
  HEXA = 'hexa',
  HEXA_CWX = 'hexa-cwx',
  HEXA_DJI = 'hexa-dji',
  OCTA = 'octa',
  OCTA_CWX = 'octa-cwx',
  OCTA_DJI = 'octa-dji',
  OCTA_QUAD_CWX = 'octa-quad-cwx',
  DODECA_HEXA = 'dodeca-hexa',
  TRI = 'tri',
  Y_SIX = 'y6',
  HELI = 'heli',
  HELI_DUAL = 'heli-dual',
  HELI_COMPOUND = 'heli-compound',
  SINGLECOPTER = 'singlecopter',
  COAXCOPTER = 'coaxcopter',
  ROVER = 'rover',
  ROVER_SKID = 'rover-skid',
  ROVER_VECTORED = 'rover-vectored',
  BALANCEBOT = 'balancebot',
  SAILBOAT = 'sailboat',
  MOTORBOAT = 'motorboat',
  MOTORBOAT_SKID = 'motorboat-skid',
  CRRCSIM = 'crrcsim',
  JSBSIM = 'jsbsim',
  FLIGHTAXIS = 'flightaxis',
  GAZEBO = 'gazebo',
  LAST_LETTER = 'last_letter',
  TRACKER = 'tracker',
  BALLOON = 'balloon',
  PLANE = 'plane',
  CALIBRATION = 'calibration',
  VECTORED = 'vectored',
  VECTORED_6DOF = 'vectored_6dof',
  SILENTWINGS = 'silentwings',
  MORSE = 'morse',
  AIRSIM = 'airsim',
  SCRIMMAGE = 'scrimmage',
  WEBOTS = 'webots',
  JSON = 'JSON',
  UNDEFINED = 'undefined',
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

export function userFriendlyEndpointType(type: EndpointType): string {
  switch (type) {
    case EndpointType.udpin: return 'UDP Server'
    case EndpointType.udpout: return 'UDP Client'
    case EndpointType.tcpin: return 'TCP Server'
    case EndpointType.tcpout: return 'TCP Client'
    case EndpointType.serial: return 'Serial'
    case EndpointType.zenoh: return 'Zenoh'
    default: return 'Undefined type'
  }
}
export interface AutopilotEndpoint {
    name: string
    owner: string
    connection_type: EndpointType
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
