import {
    getModule,
  Module, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import autopilot_data from "./autopilot"
import { Dictionary } from "@/types/common"
import decode, { deviceId } from '@/utils/deviceid_decoder'

import { vec3 } from 'gl-matrix'
import { every } from 'lodash'

@Module({
    dynamic: true,
    store,
    name: 'ardupilot_sensors',
  })

class ArdupilotSensorsStore extends VuexModule {

    get accelerometers(): deviceId[]  {
        return autopilot_data.parameterRegex('^INS_ACC.*_ID')
        .filter((param) => param.value !== 0)
        .map((parameter) => decode(parameter.name, parameter.value))
      }
    
      get compasses(): deviceId[] {
        return autopilot_data.parameterRegex('^COMPASS_DEV_ID.*')
          .filter((param) => param.value !== 0)
          .map((parameter) => decode(parameter.name, parameter.value))
      }
    
      get baros(): deviceId[] {
        return autopilot_data.parameterRegex('^BARO.*_DEVID')
          .filter((param) => param.value !== 0)
          .map((parameter) => decode(parameter.name, parameter.value))
      }
    
      get accelerometers_calibrated() {
        const results = {} as Dictionary<boolean>
        for (const imu of ardupilot_sensors.accelerometers) {
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
    
      get accelerometers_temperature_calibrated() {
        const results = {} as Dictionary<{ calibrated: boolean, calibrationTemperature: number }>
        for (const accelerometer of ardupilot_sensors.accelerometers) {

          let param_radix = accelerometer.param.split('_ID')[0]
          // CALTEMP parameters contains ID for the first sensor, _ID does not, so we need to add it
          if (!/\d$/.test(param_radix)) {
            param_radix += '1'
          }
          const name = `${param_radix}_CALTEMP`
          const parameter = autopilot_data.parameter(name)
          results[accelerometer.param] = {
            calibrated: parameter !== undefined && parameter.value !== -300,
            calibrationTemperature: parameter?.value ?? 0,
          }
        }
        return results
      }
    
      get enabled_compasses_ids(): (undefined | number)[] {
        return [1,2,3].map((index) => autopilot_data.parameter(`COMPASS_PRIO${index}_ID`)?.value)
      }
    
      get all_enabled_compasses_calibrated(): Dictionary<boolean> {
        return Object.fromEntries(
          Object.entries(this.compass_calibrated).filter(([key, _]) => {
          const compass_dev_id = autopilot_data.parameter(key)?.value
          return this.enabled_compasses_ids.includes(compass_dev_id)
        }))
      }
    
      get compass_calibrated() {
        const results = {} as Dictionary<boolean>
        for (const compass of ardupilot_sensors.compasses) {
          const compass_number = compass.param.split('COMPASS_DEV_ID')[1]
          const offset_params_names = [
            `COMPASS_OFS${compass_number}_X`,
            `COMPASS_OFS${compass_number}_Y`,
            `COMPASS_OFS${compass_number}_Z`,
          ]
          const diagonal_params_names = [
            `COMPASS_ODI${compass_number}_X`,
            `COMPASS_ODI${compass_number}_Y`,
            `COMPASS_ODI${compass_number}_Z`,
          ]
    
          const offset_params = offset_params_names.map(
            (name) => autopilot_data.parameter(name),
          )
          const diagonal_params = diagonal_params_names.map(
            (name) => autopilot_data.parameter(name),
          )
          if (offset_params.includes(undefined) || diagonal_params.includes(undefined)) {
            results[compass.param] = false
            continue
          }
          const is_at_default_offsets = offset_params.every((param) => param?.value === 0.0)
          const is_at_default_diagonals = diagonal_params.every((param) => param?.value === 0.0)
          results[compass.param] = !offset_params.isEmpty() && !diagonal_params.isEmpty()
            && (!is_at_default_offsets || !is_at_default_diagonals)
        }
        return results
      }
    
      get gyroscope_offsets(): Array<vec3> {
        let all_offsets = [];
        for (let index = 1; index <= 3; index++) {
          const suffix = index === 1 ? '' : index.toString()
    
          const gyrId = autopilot_data.parameter(`INS_GYR${suffix}_ID`)
          if (gyrId?.value === 0) continue;
    
          const offsets = ['X', 'Y', 'Z'].map((axis) => {
            const rawValue = autopilot_data.parameter(`INS_GYR${suffix}OFFS_${axis}`)?.value
            return rawValue ? rawValue * 1000 : null
          }) as vec3
          all_offsets.push(offsets)
        }
        return all_offsets
      }
    
      get gyroscope_calibrated(): boolean[] {
        const results = []
        for (const gyroscope of this.gyroscope_offsets) {
          results.push(gyroscope.every((param) => param !== 0.0))
        }
        return results
      }
    
      get barometer_calibrated() {
        const results = {} as Dictionary<boolean>
          for (const baro of ardupilot_sensors.baros) {
            const radix = baro.param.replace('_DEVID', '')
            const calibration_param = autopilot_data.parameter(`${radix}_GND_PRESS`)
            results[baro.param] = calibration_param?.value !== 0
          }
          return results
      }

      get sensors(): Dictionary<boolean> {
        return {
          compass: every(Object.values(ardupilot_sensors.all_enabled_compasses_calibrated)),
          accelerometer: every(Object.values(ardupilot_sensors.accelerometers_calibrated)),
          gyroscope: every(Object.values(ardupilot_sensors.gyroscope_calibrated)),
          baro: every(Object.values(ardupilot_sensors.barometer_calibrated)),
        }
      }

    get all_sensors_calibrated() : boolean {
      return Object.values(ardupilot_sensors.sensors).every((value) => value)
    }
}

export { ArdupilotSensorsStore }

const ardupilot_sensors: ArdupilotSensorsStore = getModule(ArdupilotSensorsStore)
export default ardupilot_sensors
