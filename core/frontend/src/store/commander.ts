import Notifier from '@/libs/notifier'
import { ReturnStruct, ShutdownType } from '@/types/commander'
import { commander_service } from '@/types/frontend_services'
import back_axios, { backend_offline_error } from '@/utils/api'

const notifier = new Notifier(commander_service)

class CommanderStore {
  API_URL = '/commander/v1.0'

  private static instance: CommanderStore

  public static getInstance(): CommanderStore {
    if (!CommanderStore.instance) {
      CommanderStore.instance = new CommanderStore()
    }
    return CommanderStore.instance
  }

  async commandHost(command: string): Promise<undefined | ReturnStruct> {
    return back_axios({
      method: 'post',
      url: `${this.API_URL}/command/host`,
      timeout: 5000,
      params: {
        command,
        i_know_what_i_am_doing: true,
      },
    })
      .then((response) => response.data)
      .catch((error) => {
        if (error === backend_offline_error) {
          return undefined
        }
        const message = `Could not send command to host: ${error.response?.data ?? error.message}.`
        notifier.pushError('COMMANDER_COMMAND_HOST_FAIL', message, true)
        return undefined
      })
  }

  async setTime(unixTimeSeconds: number): Promise<void> {
    return back_axios({
      method: 'post',
      url: `${this.API_URL}/set_time`,
      timeout: 5000,
      params: {
        unix_time_seconds: unixTimeSeconds,
        i_know_what_i_am_doing: true,
      },
    })
      .then((response) => response.data)
      .catch((error) => {
        if (error === backend_offline_error) {
          return
        }
        const message = `Could not set time: ${error.response?.data ?? error.message}.`
        notifier.pushError('COMMANDER_SET_TIME_FAIL', message, true)
      })
  }

  async shutdown(shutdownType: ShutdownType): Promise<void> {
    return back_axios({
      method: 'post',
      url: `${this.API_URL}/shutdown`,
      timeout: 5000,
      params: {
        shutdown_type: shutdownType,
        i_know_what_i_am_doing: true,
      },
    })
      .then((response) => response.data)
      .catch((error) => {
        if (error === backend_offline_error) {
          return
        }

        // Connection lost/timeout, normal when we are turning off/rebooting
        if (error.code === 'ECONNABORTED') {
          return
        }

        const message = `Could not execute shutdown: ${error.message ?? error.response?.data}.`
        notifier.pushError('COMMANDER_SHUTDOWN_FAIL', message, true)
      })
  }

  async getRaspiCameraLegacy(): Promise<boolean | undefined> {
    return back_axios({
      method: 'get',
      url: `${this.API_URL}/raspi_config/camera_legacy`,
      timeout: 5000,
    })
      .then((response) => response.data?.enabled)
      .catch((error) => {
        if (error === backend_offline_error) {
          return undefined
        }
        const message = 'Could not get Raspberry legacy camera configuration:'
          + ` ${error.response?.data ?? error.message}.`
        notifier.pushError('COMMANDER_GET_CAMERA_LEGACY_FAIL', message, true)
        return undefined
      })
  }

  async setRaspiCameraLegacy(enable = true): Promise<boolean> {
    return back_axios({
      method: 'post',
      url: `${this.API_URL}/raspi_config/camera_legacy`,
      timeout: 5000,
      params: {
        // eslint-disable-next-line object-shorthand
        enable: enable,
      },
    })
      .then(() => true)
      .catch((error) => {
        if (error === backend_offline_error) {
          return false
        }
        const message = 'Could not set Raspberry legacy camera configuration:'
          + ` ${error.message ?? error.response?.data}.`
        notifier.pushError('COMMANDER_SET_CAMERA_LEGACY_FAIL', message, true)
        return false
      })
  }

  async getVcgencmd(): Promise<undefined | Record<string, ReturnStruct>> {
    return back_axios({
      method: 'get',
      url: `${this.API_URL}/raspi/vcgencmd`,
      timeout: 20000,
      params: {
        i_know_what_i_am_doing: true,
      },
    })
      .then((response) => response.data)
      .catch((error) => {
        if (error === backend_offline_error) {
          return undefined
        }
        const message = `Could not get vcgencmd data: ${error.response?.data ?? error.message}.`
        notifier.pushError('COMMANDER_GET_VC_GEN_CMD_FAIL', message, true)
        return undefined
      })
  }

  async getEnvironmentVariables(): Promise<Record<string, unknown> | undefined> {
    return back_axios({
      method: 'get',
      url: `${this.API_URL}/environment_variables`,
      timeout: 5000,
    })
      .then((response) => response.data)
      .catch((error) => {
        if (error === backend_offline_error) {
          return undefined
        }
        const message = `Could not get environment variables: ${error.response?.data ?? error.message}.`
        notifier.pushError('COMMANDER_GET_ENV_VARS_FAIL', message, true)
        return undefined
      })
  }

  async getRaspiEEPROM(): Promise<ReturnStruct | undefined> {
    return back_axios({
      method: 'get',
      url: `${this.API_URL}/raspi/eeprom_update`,
      timeout: 20000,
      params: {
        i_know_what_i_am_doing: true,
      },
    })
      .then((response) => response.data)
      .catch((error) => {
        if (error === backend_offline_error) {
          return undefined
        }
        const message = `Could not get Raspi EEPROM information: ${error.response?.data ?? error.message}.`
        notifier.pushError('COMMANDER_GET_RASPI_EEPROM_FAIL', message, true)
        return undefined
      })
  }

  async doRaspiEEPROMUpdate(): Promise<ReturnStruct | undefined> {
    return back_axios({
      method: 'post',
      url: `${this.API_URL}/raspi/eeprom_update`,
      timeout: 60000,
      params: {
        i_know_what_i_am_doing: true,
      },
    })
      .then((response) => response.data)
      .catch((error) => {
        if (error === backend_offline_error) {
          return undefined
        }
        const message = `Could not update Raspi EEPROM: ${error.response?.data ?? error.message}.`
        notifier.pushError('COMMANDER_UPDATE_RASPI_EEPROM_FAIL', message, true)
        return undefined
      })
  }
}

const Commander = CommanderStore.getInstance()
export default Commander
