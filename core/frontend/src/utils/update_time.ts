import Vue from 'vue'

import notifications from '@/store/notifications'
import { update_time_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

export default async function run() : Promise<void> {
  await back_axios({
    url: '/commander/v1.0/set_time',
    method: 'post',
    params: {
      unix_time_seconds: Math.round(new Date().getTime() / 1000),
      i_know_what_i_am_doing: true,
    },
    timeout: 10000,
  })
    .catch((error) => {
      // Connection lost/timeout, normal when we are turnning off/rebooting
      if (error.code === 'ECONNABORTED') {
        run()
        return
      }

      const message = error.response.data.detail ?? error.message
      notifications.pushError({ service: update_time_service, type: 'UPDATE_TIME_FAIL', message })
    })
}
