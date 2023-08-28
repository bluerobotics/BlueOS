import Notifier from '@/libs/notifier'
import nmea_injector from '@/store/nmea-injector'
import { nmea_injector_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(nmea_injector_service)

export default async function fetchAvailableNMEASockets(): Promise<void> {
  await back_axios({
    method: 'get',
    url: `${nmea_injector.API_URL}/socks`,
    timeout: 10000,
  })
    .then((response) => {
      const available_nmea_sockets = response.data
      nmea_injector.setAvailableNMEASockets(available_nmea_sockets)
    })
    .catch((error) => {
      nmea_injector.setAvailableNMEASockets([])
      notifier.pushBackError('BRIDGES_FETCH_FAIL', error)
    })
    .finally(() => {
      nmea_injector.setUpdatingNMEASockets(false)
    })
}
