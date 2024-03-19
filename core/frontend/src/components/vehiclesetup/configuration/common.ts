import { AutopilotStore } from "@/store/autopilot"
import { Dictionary } from "@/types/common"
import { deviceId } from "@/utils/deviceid_decoder"

export function imu_is_calibrated(imus: deviceId[], autopilot_data: AutopilotStore) {
  const results = {} as Dictionary<boolean>
  for (const imu of imus) {
    const param_radix = imu.param.split('_ID')[0]
    const offset_params_names = [`${param_radix}OFFS_X`, `${param_radix}OFFS_Y`, `${param_radix}OFFS_Z`]
    const scale_params_names = [`${param_radix}SCAL_X`, `${param_radix}SCAL_Y`, `${param_radix}SCAL_Z`]
    const offset_params = offset_params_names.map(
      (name) => autopilot_data.parameter(name),
    )
    const scale_params = scale_params_names.map(
      (name) => autopilot_data.parameter(name),
    )
    const is_at_default_offsets = offset_params.every((param) => param?.value === 0.0)
    const is_at_default_scale = scale_params.every((param) => param?.value === 1.0)
    results[imu.param] = offset_params.isEmpty() || scale_params.isEmpty()
    || !is_at_default_offsets || !is_at_default_scale
  }
  return results
}

export function imu_temperature_is_calibrated(imus: deviceId[], autopilot_data: AutopilotStore): Dictionary<{ calibrated: boolean, calibrationTemperature: number }> {
  const results = {} as Dictionary<{ calibrated: boolean, calibrationTemperature: number }>
  for (const imu of imus) {
    let param_radix = imu.param.split('_ID')[0]
    // CALTEMP parameters contains ID for the first sensor, _ID does not, so we need to add it
    if (!/\d$/.test(param_radix)) {
      param_radix += '1'
    }
    const name = `${param_radix}_CALTEMP`
    const parameter = autopilot_data.parameter(name)
    results[imu.param] = {
      calibrated: parameter !== undefined && parameter.value !== -300,
      calibrationTemperature: parameter?.value ?? 0,
    }
  }
  return results
}
