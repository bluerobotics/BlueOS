import Notifier from '@/libs/notifier'
import { update_time_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(update_time_service)

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

      notifier.pushBackError('UPDATE_TIME_FAIL', error)
    })
}
