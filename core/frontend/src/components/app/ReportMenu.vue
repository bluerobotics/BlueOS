<template>
  <v-container
    id="feature-request-button"
    class="d-flex justify-center"
  >
    <v-btn
      class="mr-2"
      icon
      large
      elevation="2"
      @click="showDialog(true)"
    >
      <v-icon>mdi-bug</v-icon>
    </v-btn>
    <v-dialog
      width="340"
      :value="show_dialog"
      @input="showDialog"
    >
      <v-card>
        <v-card-title class="align-center">
          Bug report / Feature Request
        </v-card-title>

        <v-divider />

        <v-card-actions
          class="flex-column"
        >
          <v-btn
            class="ma-2"
            block
            @click="openGitHub()"
          >
            <v-icon
              left
              size="24"
            >
              mdi-github
            </v-icon>
            With GitHub
          </v-btn>

          <v-btn
            class="ma-2"
            block
            @click="openDiscuss()"
          >
            <v-icon
              left
              size="24"
            >
              $si-discourse
            </v-icon>
            With Blue Robotics discuss
          </v-btn>

          <v-btn
            class="ma-2"
            block
            @click="openSlack()"
          >
            <v-icon
              left
              size="24"
            >
              mdi-slack
            </v-icon>
            With Blue Robotics slack
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import settings from '@/libs/settings'
import notifications from '@/store/notifications'
import { commander_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const API_URL = '/commander/v1.0'

export default Vue.extend({
  name: 'PowerMenu',
  data() {
    return {
      show_dialog: false,
    }
  },
  methods: {
    showDialog(state: boolean): void {
      this.show_dialog = state
    },
    openGitHub(): void {
      window.open('https://github.com/bluerobotics/blueos-docker/issues/new/choose', '_blank')
    },
    openDiscuss(): void {
      window.open(this.discussUrl(), '_blank')
    },
    discussUrl(): string {
      const url = new URL('https://discuss.bluerobotics.com')
      url.pathname = '/new-topic'

      const parameters = {
        title: 'BlueOS feedback - (Please add a title here)',
        body: 'Blue OS Version: (You can check on the bottom of the main menu)\n- - -\nFeedback content',
        category_id: 85,
        tags: ['frontend'],
      }

      Object.entries(parameters).forEach(([name, value]) => url.searchParams.set(name, value.toString()))

      return url.href
    },
    openSlack(): void {
      window.open('https://bluerobotics.slack.com/archives/blue-os', '_blank')
    },
  },
})
</script>
