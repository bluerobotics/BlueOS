import mavlink2rest from '@/libs/MAVLink2Rest'
// eslint-disable-next-line import/no-cycle
import ardupilot_data from '@/store/autopilot'
import { AutopilotStore } from '@/store/autopilot'

import ParametersTable from './parameter-table'
import autopilot from '@/store/autopilot_manager'

export default class ParameterFetcher {
  parameter_table = new ParametersTable()

  listener = mavlink2rest.startListening('PARAM_VALUE')

  store = null as (AutopilotStore | null)

  loaded_params_count = 0

  total_params_count = null as null | number

  watchdog_last_count = 0

  last_store_update = performance.now()

  min_update_interval_ms = 300

  constructor() {
    this.setupWs()
  }

  setStore(store: AutopilotStore): void {
    this.store = store
  }

  reset(): void {
    this.loaded_params_count = 0
    this.total_params_count = null
    this.watchdog_last_count = 0
    this.parameter_table.reset()
  }

  updateStore(): void {
    if (!this.store || this.total_params_count === null) {
      return
    }
    const enough_time_passed = performance.now() - this.last_store_update > this.min_update_interval_ms
    const all_parameters_loaded = this.loaded_params_count >= this.total_params_count
    if (enough_time_passed || all_parameters_loaded) {
      this.store.setMetadataLoaded(this.parameter_table.loaded())
      this.store.setParameters(this.parameter_table.parameters())
      this.store.setLoadedParametersCount(this.loaded_params_count)
      this.store.setTotalParametersCount(this.total_params_count ?? 0)
      this.last_store_update = performance.now()
    }
  }

  requestParamsWatchdog(): void {
    if (this.total_params_count !== null
      && this.loaded_params_count > 0
      && this.loaded_params_count >= this.total_params_count) {
      return
    }
    if (autopilot.restarting) {
      return
    }

    if (this.loaded_params_count > this.watchdog_last_count) {
      // We received something since the last watchdog update
      this.watchdog_last_count = this.loaded_params_count
      return
    }
    // we don't have all parameters, and haven't received any for at least 5 seconds
    // let's ask for the parameters again.
    mavlink2rest.sendMessage(
      {
        header: {
          system_id: 255,
          component_id: 0,
          sequence: 0,
        },
        message: {
          type: 'PARAM_REQUEST_LIST',
          target_system: ardupilot_data.system_id,
          target_component: 1,
        },
      },
    )
    this.watchdog_last_count = this.loaded_params_count
  }

  setupWs(): void {
    this.listener.setCallback((receivedMessage) => {
      const param_name = receivedMessage.message.param_id.join('').replace(/\0/g, '')
      const { param_index, param_value, param_type } = receivedMessage.message
      // We need this due to mismatches between js 64-bit floats and REAL32 in MAVLink
      const trimmed_value = Math.round(param_value * 10000) / 10000
      if (param_index === 65535) {
        this.parameter_table.updateParam(param_name, trimmed_value)
      } else {
        this.parameter_table.addParam(
          {
            name: param_name as string,
            id: param_index as number,
            value: trimmed_value as number,
            readonly: false,
            rebootRequired: false,
            description: '',
            shortDescription: '',
            paramType: param_type,
          },
        )
        if (receivedMessage.message.param_count) {
          this.total_params_count = receivedMessage.message.param_count
        }
        this.loaded_params_count = this.parameter_table.size()
      }
      this.updateStore()
    }).setFrequency(0)
    setInterval(() => {
      this.requestParamsWatchdog()

      // Check if store is done, otherwise try to update it
      // The parameter metadata may not be completed or
      // others edge cases
      if (this.store?.finished_loading !== true) {
        this.updateStore()
      }
    }, 2000)
  }
}
