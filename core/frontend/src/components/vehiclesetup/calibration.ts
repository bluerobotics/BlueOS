import mavlink2rest from '@/libs/MAVLink2Rest'
import {
  MavCmd, MAVLinkType, MavResult,
} from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import autopilot_data from '@/store/autopilot'
import { sleep } from '@/utils/helper_functions'

enum PreflightCalibration {
  GYROSCOPE,
  GYROSCOPE_TEMPERATURE,
  MAGNETOMETER,
  PRESSURE,
  RC,
  RC_TRIM,
  ACCELEROMETER,
  BOARD_LEVEL,
  ACCELEROMETER_TEMPERATURE,
  SIMPLE_ACCELEROMETER,
  COMPASS_MOTOR_INTERFERENCE,
  AIRPSEED,
  ESC,
  BAROMETER_TEMPERATURE,
}

class Calibrator {
  private static instance: Calibrator

  private calibrating: PreflightCalibration | undefined

  private calibrationStatus: MavResult | undefined

  constructor() {
    mavlink2rest.startListening(MAVLinkType.COMMAND_ACK).setCallback((content) => {
      const { header, message } = content
      if (header.system_id !== autopilot_data.system_id || header.component_id !== 1) {
        return
      }
      if (message.command.type === MavCmd.MAV_CMD_PREFLIGHT_CALIBRATION) {
        this.calibrationStatus = message.result.type
      }
    }).setFrequency(0)
  }

  /**
   * Singleton access
   * @returns Calibrator
   */
  public static getInstance(): Calibrator {
    if (!Calibrator.instance) {
      Calibrator.instance = new Calibrator()
    }
    return Calibrator.instance
  }

  /**
   * Start calibration process
   * @param {PreflightCalibration} type
   */
  private static start(type: PreflightCalibration): void {
    mavlink2rest.sendMessage({
      header: {
        system_id: 255,
        component_id: 0,
        sequence: 0,
      },
      message: {
        type: MAVLinkType.COMMAND_LONG,
        param1: {
          [PreflightCalibration.GYROSCOPE]: 1,
          [PreflightCalibration.GYROSCOPE_TEMPERATURE]: 3,
        }[type] || 0,
        param2: type === PreflightCalibration.MAGNETOMETER ? 1 : 0,
        param3: type === PreflightCalibration.PRESSURE ? 1 : 0,
        param4: {
          [PreflightCalibration.RC]: 1,
          [PreflightCalibration.RC_TRIM]: 2,
        }[type] || 0,
        param5: {
          [PreflightCalibration.ACCELEROMETER]: 1,
          [PreflightCalibration.BOARD_LEVEL]: 2,
          [PreflightCalibration.ACCELEROMETER_TEMPERATURE]: 3,
          [PreflightCalibration.SIMPLE_ACCELEROMETER]: 4,
        }[type] || 0,
        param6: {
          [PreflightCalibration.COMPASS_MOTOR_INTERFERENCE]: 1,
          [PreflightCalibration.AIRPSEED]: 2,
        }[type] || 0,
        param7: {
          [PreflightCalibration.ESC]: 1,
          [PreflightCalibration.BAROMETER_TEMPERATURE]: 3,
        }[type] || 0,
        command: {
          type: MavCmd.MAV_CMD_PREFLIGHT_CALIBRATION,
        },
        target_system: autopilot_data.system_id,
        target_component: 1,
        confirmation: 0,
      },
    })
  }

  /**
   * Generator function for calibration status with timeout
   * @param {PreflightCaliration} type
   * @param {number} timeout in seconds
   */
  public async* calibrate(type: PreflightCalibration, timeout = 6): AsyncGenerator<MavResult | string> {
    const startTime = Date.now()
    Calibrator.start(type)

    while (true) {
      await sleep(200)

      switch (this.calibrationStatus) {
        case MavResult.MAV_RESULT_ACCEPTED:
          this.calibrationStatus = undefined
          yield 'Calibration done.'
          return

        case MavResult.MAV_RESULT_IN_PROGRESS:
          this.calibrationStatus = undefined
          yield 'In progress..'
          continue

        case MavResult.MAV_RESULT_CANCELLED:
        case MavResult.MAV_RESULT_DENIED:
        case MavResult.MAV_RESULT_FAILED:
        case MavResult.MAV_RESULT_TEMPORARILY_REJECTED:
        case MavResult.MAV_RESULT_UNSUPPORTED:
          yield `Calibration failed with status: ${this.calibrationStatus}`
          this.calibrationStatus = undefined
          return

        default:
          // Handle any other potential cases if needed
          yield 'Waiting for vehicle..'
      }

      // Check for timeout
      if (Date.now() - startTime > timeout * 1000) {
        yield `Calibration timed out after ${timeout} seconds.`
        return
      }
    }
  }
}

const calibrator = Calibrator.getInstance()
export { calibrator, PreflightCalibration }
