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
      width="fit-content"
      :value="show_dialog"
      @input="showDialog"
    >
      <v-card>
        <v-card-title class="align-center">
          Bug report / Feature request
        </v-card-title>

        <v-divider />

        <v-container class="pa-2">
          <v-card-actions class="flex-column">
            <v-btn
              v-tooltip="'Track changes, contribute, and get notified when fixed'"
              class="ma-2"
              @click="openGitHub()"
            >
              <v-icon
                left
                size="20"
              >
                mdi-github
              </v-icon>
              With GitHub
            </v-btn>

            <v-btn
              v-tooltip="'Directly send us a feedback'"
              class="ma-2"
              @click="openSimpleReport"
            >
              <v-icon
                left
                size="20"
              >
                mdi-message-text
              </v-icon>
              With Simple Report
            </v-btn>

            <v-btn
              v-tooltip="'Discuss ideas with the community'"
              class="ma-2"
              @click="openDiscuss()"
            >
              <v-icon
                left
                size="16"
              >
                $si-discourse
              </v-icon>
              On Blue Robotics forum
            </v-btn>
          </v-card-actions>
        </v-container>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script lang="ts">
import * as Sentry from '@sentry/vue'
import Vue from 'vue'

export default Vue.extend({
  name: 'ReportMenu',
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
    async openSimpleReport(): Promise<void> {
      // @ts-expect-error - Theme is not defined in the type
      const { isDark, currentTheme } = this.$vuetify.theme

      const theme = {
        background: currentTheme.sheet_bg,
        foreground: currentTheme.sheet_bg_complement,
        accentBackground: currentTheme.br_blue,
        accentForeground: currentTheme.sheet_bg,
        successColor: currentTheme.success,
        errorColor: currentTheme.error,
        border: `1.5px solid ${currentTheme.sheet_bg_complement}26`, // 15% opacity
        interactiveFilter: `brightness(${isDark ? '150' : '95'}%)`,
      }

      const feedback = Sentry.feedbackIntegration({
        colorScheme: 'system',
        showBranding: false,
        formTitle: 'Send us a simple report',
        submitButtonLabel: 'Send Report',
        messagePlaceholder: 'What\'s the bug? What did you expect? What feedback do you have?',
        themeLight: theme,
        themeDark: theme,
      })

      const form = await feedback.createForm()
      form.appendToDom()

      this.show_dialog = false
      form.open()
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
  },
})
</script>
