<template>
  <v-dialog
    width="500"
    :value="show"
    @input="showDialog"
  >
    <v-card>
      <v-card-title>
        Change running board
      </v-card-title>

      <v-card-text class="d-flex flex-column">
        <v-form
          ref="form"
          lazy-validation
        >
          <v-select
            v-model="selected_board"
            :items="board_options"
            label="Available boards"
            required
          />

          <v-btn
            color="primary"
            class="mr-4"
            @click="changeBoard"
          >
            Set
          </v-btn>
        </v-form>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import { FlightController, FlightControllerFlags } from '@/types/autopilot'
import { autopilot_service } from '@/types/frontend_services'
import { VForm } from '@/types/vuetify'
import back_axios from '@/utils/api'

const notifier = new Notifier(autopilot_service)

export default Vue.extend({
  name: 'ConnectionDialog',
  model: {
    prop: 'show',
    event: 'change',
  },
  props: {
    show: {
      type: Boolean,
      default: false,
    },
  },

  data() {
    return {
      selected_board: null,
    }
  },
  computed: {
    board_options(): {value: FlightController, text: string}[] {
      return this.available_boards.map(
        (board) => ({
          value: board,
          text: board.name === autopilot.current_board?.name ? `${board.name} (current)` : board.name,
        }),
      )
    },
    available_boards(): FlightController[] {
      return autopilot.available_boards.filter(
        (board: FlightController) => !board.flags.includes(FlightControllerFlags.is_bootloader),
      )
    },
    form(): VForm {
      return this.$refs.form as VForm
    },
  },
  methods: {
    async changeBoard(): Promise<boolean> {
      if (!this.form.validate()) {
        return false
      }
      this.showDialog(false)
      autopilot.setRestarting(true)

      await back_axios({
        method: 'post',
        url: `${autopilot.API_URL}/board`,
        data: this.selected_board,
        timeout: 10000,
      })
        .then(() => {
          this.form.reset()
          autopilot_data.reset()
        })
        .catch((error) => {
          notifier.pushBackError('AUTOPILOT_BOARD_CHANGE_FAIL', error)
          return false
        })
        .finally(() => {
          autopilot.setRestarting(false)
        })
      return true
    },

    showDialog(state: boolean) {
      this.$emit('change', state)
    },
  },
})
</script>
