<template>
  <v-card
    elevation="0"
    class="pa-2"
  >
    <v-select
      :value="autopilot.sitl_frame"
      :items="sitl_frame_options"
      :disabled="autopilot.restarting || setting"
      :loading="autopilot.restarting || setting"
      label="SITL frame"
      class="ma-1 pa-0"
      @change="changeSitlFrame"
    />
    <v-snackbar
      v-model="show_success"
      color="success"
      timeout="3000"
    >
      SITL frame set, autopilot restarted
      <template #action="{ attrs }">
        <v-btn
          text
          v-bind="attrs"
          @click="show_success = false"
        >
          Close
        </v-btn>
      </template>
    </v-snackbar>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import { fetchSitlFrame, restart } from '@/components/autopilot/AutopilotManagerUpdater'
import Notifier from '@/libs/notifier'
import { OneMoreTime } from '@/one-more-time'
import autopilot from '@/store/autopilot_manager'
import { SITLFrame } from '@/types/autopilot'
import { autopilot_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(autopilot_service)

export default Vue.extend({
  name: 'SitlConfiguration',
  data() {
    return {
      autopilot,
      fetch_sitl_frame_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
      setting: false,
      show_success: false,
    }
  },
  computed: {
    sitl_frame_options(): {value: SITLFrame, text: string}[] {
      return Object.values(SITLFrame)
        .filter((frame) => frame !== SITLFrame.UNDEFINED)
        .map((frame) => ({ value: frame, text: frame }))
        .sort((a, b) => a.text.localeCompare(b.text))
    },
  },
  mounted() {
    this.fetch_sitl_frame_task.setAction(fetchSitlFrame)
  },
  beforeDestroy() {
    autopilot.setSitlFrame(null)
  },
  methods: {
    async changeSitlFrame(frame: SITLFrame): Promise<void> {
      this.setting = true
      try {
        await back_axios({
          method: 'post',
          url: `${autopilot.API_URL}/sitl_frame`,
          params: { frame },
          timeout: 10000,
        })
      } catch (error) {
        notifier.pushBackError('AUTOPILOT_SITL_FRAME_SET_FAIL', error)
        return
      } finally {
        this.setting = false
      }

      // The new frame is only picked up at SITL launch, so restart so it takes effect.
      // The next fetchSitlFrame poll will update the store once SITL is back up.
      // restart() pushes its own error notification on failure.
      try {
        await restart()
        this.show_success = true
      } catch {
        // already surfaced by restart()
      }
    },
  },
})
</script>
