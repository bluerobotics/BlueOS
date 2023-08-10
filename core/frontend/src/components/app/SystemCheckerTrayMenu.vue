<template>
  <v-menu
    v-if="visible"
    v-model="show_menu"
    :close-on-content-click="false"
    nudge-left="200"
    nudge-bottom="25"
  >
    <template
      #activator="{ on, attrs }"
    >
      <v-card
        class="px-1"
        elevation="0"
        color="transparent"
        v-bind="attrs"
        v-on="on"
      >
        <v-icon
          class="blinking"
        >
          mdi-alert
        </v-icon>
      </v-card>
    </template>

    <v-dialog v-model="show_menu" max-width="700px">
      <v-card class="text-md-center">
        <v-card-title>
          Problems found
        </v-card-title>
        <v-card-text>
          <v-list>
            <v-list-item v-for="result in results" :key="result.human_message">
              <v-list-item-content>
                <v-list-item-title class="text-wrap">
                  {{ result.human_message }}
                </v-list-item-title>
                <v-list-item-subtitle class="text-wrap">
                  {{ result.debug_message }}
                </v-list-item-subtitle>
              </v-list-item-content>
            </v-list-item>
          </v-list>
        </v-card-text>
        <v-card-actions class="justify-center pa-2">
          <v-btn
            color="primary"
            @click="show_menu = false"
          >
            Close
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-menu>
</template>

<script lang="ts">
import Vue from 'vue'

import commander from '@/store/commander'

interface TestOutput {
  human_message: string,
  debug_message: string,
}

export default Vue.extend({
  name: 'VehicleRebootRequiredTrayMenu',
  data: () => ({
    show_menu: false,
    results: [] as TestOutput[],
    visible: false,
  }),
  async mounted() {
    const tests = [
      this.check_host_computer_access(),
    ]
    const results = await Promise.all(tests)
    this.results = results.filter((test) => test !== undefined) as TestOutput[]
    this.visible = this.results.length !== 0
    if (this.visible) {
      console.warn(this.results)
    }
  },
  methods: {
    async check_host_computer_access(): Promise<undefined | TestOutput> {
      const output = await commander.commandHost('uname -a')
      if (output === undefined || output.return_code === 0) {
        return undefined
      }

      // From: https://github.com/kevinburke/sshpass/blob/master/main.c#L43
      let human_message
      switch (output.return_code) {
        case 0: return undefined
        case 1: human_message = 'Invalid arguments were provided'; break
        case 2: human_message = 'Conflicting arguments were provided'; break
        case 3: human_message = 'A runtime error occurred'; break
        case 4: human_message = 'An error occurred while parsing'; break
        case 5: human_message = 'The password provided is incorrect, it should be "raspberry"'; break
        case 6: human_message = 'The host key is unknown'; break
        case 7: human_message = 'The host key has changed'; break
        default: human_message = 'Unknown error'; break
      }

      return {
        human_message: `BlueOS does not have access to the host computer.\n${human_message}.`,
        debug_message: JSON.stringify(output),
      }
    },
  },
})
</script>

<style scoped>
  .blinking {
    animation-name: blinking;
    animation-duration: 2s;
    animation-iteration-count: infinite;
  }

  @keyframes blinking {
    100% {color: red;}
    75% {color: yellow;}
    50% {color: red;}
    25% {color: yellow;}
    0% {color: red;}
  }

  .white-shadow {
    text-shadow: 0 0 3px #FFF;
  }
</style>
