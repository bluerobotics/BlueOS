<template>
  <v-card
    elevation="0"
    class="mx-auto my-12 px-1 py-6 text-center"
    min-width="370"
    max-width="720"
  >
    <v-card>
      <v-card-title>Cloud Registration</v-card-title>
      <v-card-text>
        <p>
          In order to register your vehicle, access <a href="https://app.blueos.cloud/vehicle/register/" taget="_blank">
            BlueOS Cloud
          </a>
          And create a new vehicle, then paste the token below.
        </p>
      </v-card-text>

      <v-card-text>
        <strong>Cloud Token:</strong>
        <v-text-field v-model="cloud_token" outlined />
      </v-card-text>
      <v-btn @click="join">
        Save
      </v-btn>
      <v-card-text />
    </v-card>
  </v-card>
</template>
<script>
import axios from 'axios'
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import bag from '@/store/bag'
import { cloud_service } from '@/types/frontend_services'

const notifier = new Notifier(cloud_service)

export default Vue.extend({
  name: 'CloudView',
  data() {
    return {
      cloud_token: '',
    }
  },
  methods: {
    async join() {
      axios.put(
        'https://app.blueos.cloud/api/agent/join/',
        {},
        {
          headers:
          {
            Authorization: `Token ${this.cloud_token}`,
          },
        },
      ).catch((error) => {
        if (error.response.status === StatusCodes.UNAUTHORIZED) {
          notifier.pushError(
            'CLOUD_REGISTRATION_ERROR',
            'Invalid token. Failed to link your vehicle to BlueOS Cloud ',
            true,
          )
        }
        if (error.response.status === StatusCodes.BAD_REQUEST) {
          notifier.pushSuccess(
            'CLOUD_REGISTRATION_SUCCESS',
            'Token is valid, your vehicle is now linked to BlueOS Cloud',
            true,
          )
          // TODO: save this securely on a backend or file instead of bag
          bag.setData('vehicle.cloud', { token: this.cloud_token })
        } else {
          notifier.pushError('CLOUD_REGISTRATION_ERROR', 'Failed to link your vehicle to BlueOS Cloud ', true)
        }
      })
    },
  },
})
</script>
