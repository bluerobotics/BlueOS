import autopilot_data from '@/store/autopilot'
import { deviceId } from '@/utils/deviceid_decoder'

// COMPASS_USEn, calibration masks (MAV_CMD_DO_START/ACCEPT/CANCEL_MAG_CAL,
// MAV_CMD_FIXED_MAG_CAL_YAW), and MAG_CAL_PROGRESS/MAG_CAL_REPORT compass_id
// are indexed by priority slot (COMPASS_PRIOn_ID), not by DEV_ID slot:
// see _use_for_yaw in libraries/AP_Compass/AP_Compass.h / AP_Compass.cpp,
// and _start_calibration_mask, _accept_calibration_mask, send_mag_cal_report
// and mag_cal_fixed_yaw in libraries/AP_Compass/AP_Compass_Calibration.cpp.
// Firmwares older than 4.1 and single-compass builds have no COMPASS_PRIOn_ID,
// so COMPASS_USEn and calibration follow the DEV_ID slot.
export function compassPrioritySlot(compass: deviceId): number | undefined {
  const prio_params = [1, 2, 3].map((i) => autopilot_data.parameter(`COMPASS_PRIO${i}_ID`))
  if (prio_params.some((param) => param !== undefined)) {
    const index = prio_params.findIndex((param) => param?.value === compass.paramValue)
    return index === -1 ? undefined : index
  }
  return compass.deviceIdNumber >= 1 && compass.deviceIdNumber <= 3 ? compass.deviceIdNumber - 1 : undefined
}

// Kept as aliases so calibration call sites stay explicit about their domain.
export const compassCalibrationSlot = compassPrioritySlot

export function compassFromPrioritySlot(compasses: deviceId[], slot: number): deviceId | undefined {
  return compasses.find((compass) => compassPrioritySlot(compass) === slot)
}

export const compassFromCalibrationSlot = compassFromPrioritySlot
