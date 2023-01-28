import { Dictionary } from '@/types/common'

// based on https://github.com/ArduPilot/ardupilot/blob/master/Tools/scripts/decode_devid.py

const busTypes = {
  1: 'I2C',
  2: 'SPI',
  3: 'UAVCAN',
  4: 'SITL',
  5: 'MSP',
  6: 'SERIAL',
} as Dictionary<string>

const compassTypes = {
  0x01: 'HMC5883_OLD',
  0x02: 'LSM303D',
  0x04: 'AK8963 ',
  0x05: 'BMM150 ',
  0x06: 'LSM9DS1',
  0x07: 'HMC5883',
  0x08: 'LIS3MDL',
  0x09: 'AK09916',
  0x0A: 'IST8310',
  0x0B: 'ICM20948',
  0x0C: 'MMC3416',
  0x0D: 'QMC5883L',
  0x0E: 'MAG3110',
  0x0F: 'SITL',
  0x10: 'IST8308',
  0x11: 'RM3100',
  0x12: 'RM3100_2',
  0x13: 'MMC5883',
  0x14: 'AK09918',
  0x15: 'AK09915',
} as Dictionary<string>

const imuTypes = {
  0x09: 'BMI160',
  0x10: 'L3G4200D',
  0x11: 'ACC_LSM303D',
  0x12: 'ACC_BMA180',
  0x13: 'ACC_MPU6000',
  0x16: 'ACC_MPU9250',
  0x17: 'ACC_IIS328DQ',
  0x18: 'ACC_LSM9DS1',
  0x21: 'GYR_MPU6000',
  0x22: 'GYR_L3GD20',
  0x24: 'GYR_MPU9250',
  0x25: 'GYR_I3G4250D',
  0x26: 'GYR_LSM9DS1',
  0x27: 'INS_ICM20789',
  0x28: 'INS_ICM20689',
  0x29: 'INS_BMI055',
  0x2A: 'SITL',
  0x2B: 'INS_BMI088',
  0x2C: 'INS_ICM20948',
  0x2D: 'INS_ICM20648',
  0x2E: 'INS_ICM20649',
  0x2F: 'INS_ICM20602',
  0x30: 'INS_ICM20601',
  0x31: 'INS_ADIS1647x',
  0x32: 'INS_SERIAL',
  0x33: 'INS_ICM40609',
  0x34: 'INS_ICM42688',
  0x35: 'INS_ICM42605',
  0x36: 'INS_ICM40605',
  0x37: 'INS_IIM42652',
  0x38: 'INS_BMI270',
  0x39: 'INS_BMI085',
  0x3A: 'INS_ICM42670',
} as Dictionary<string>

const baroTypes = {
  0x01: 'SITL',
  0x02: 'BMP085',
  0x03: 'BMP280',
  0x04: 'BMP388',
  0x05: 'DPS280',
  0x06: 'DPS310',
  0x07: 'FBM320',
  0x08: 'ICM20789',
  0x09: 'KELLERLD',
  0x0A: 'LPS2XH',
  0x0B: 'MS5611',
  0x0C: 'SPL06',
  0x0D: 'UAVCAN',
  0x0E: 'MSP',
  0x0F: 'ICP101XX',
  0x10: 'ICP201XX',
  0x11: 'MS5607',
  0x12: 'MS5837',
  0x13: 'MS5637',
  0x14: 'BMP390',
} as Dictionary<string>

const airspeedTypes = {
  0x01: 'AIRSPEED_SITL',
  0x02: 'AIRSPEED_MS4525',
  0x03: 'AIRSPEED_MS5525',
  0x04: 'AIRSPEED_DLVR',
  0x05: 'AIRSPEED_MSP',
  0x06: 'AIRSPEED_SDP3X',
  0x07: 'AIRSPEED_UAVCAN',
  0x08: 'AIRSPEED_ANALOG',
  0x09: 'AIRSPEED_NMEA',
  0x0A: 'AIRSPEED_ASP5033',
} as Dictionary<string>

function toHex(value: number): string {
  return Number(value).toString(16).padStart(2, '0')
}

export interface deviceId {
    param: string
    deviceName?: string
    busType: string
    bus: number
    address: string
    devtype: number
}

export default function decode(device: string, devid: number): deviceId {
  const busType = busTypes[devid & 0x07]
  const bus = devid >> 3 & 0x1F
  const address = devid >> 8 & 0xFF
  const devtype = devid >> 16
  let decodedDevname = 'UNKNOWN'

  if (device.startsWith('COMPASS')) {
    if (devtype === 1) {
      decodedDevname = 'UAVCAN'
    } else if (devtype === 1) {
      decodedDevname = 'EAHRS'
    } else {
      decodedDevname = compassTypes[devtype] || 'UNKNOWN'
    }
  }
  if (device.startsWith('INS')) {
    decodedDevname = imuTypes[devtype] || 'UNKNOWN'
  }
  if (device.startsWith('GND_BARO') || device.startsWith('BARO')) {
    decodedDevname = baroTypes[devtype] || 'UNKNOWN'
  }
  if (device.startsWith('ARSP')) {
    decodedDevname = airspeedTypes[devtype] || 'UNKNOWN'
  }
  return {
    param: device,
    deviceName: decodedDevname,
    busType,
    bus,
    address: toHex(address),
    devtype,
  }
}
