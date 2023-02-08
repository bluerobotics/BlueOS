<template>
  <v-card width="400">
    <v-sheet
      class="v-sheet--offset mx-auto"
      color="primary"
      elevation="12"
      max-width="calc(100% - 10px)"
    >
      <v-row class="ma-5 d-flex justify-center">
        <v-icon>
          {{ icon }}
        </v-icon>

        <div
          class="transition-swing text-h4 pa-3 white--text"
          align="center"
          v-text="value"
        />
      </v-row>
    </v-sheet>

    <v-card-text class="pt-0">
      <div class="text-h6 font-weight-light mb-2">
        {{ title }}
      </div>
      <!-- eslint-disable vue/no-v-html -->
      <div
        class="subheading font-weight-light grey--text"
        v-html="text"
      />
      <v-divider class="my-2" />
      <v-icon
        class="mr-2"
        small
      >
        mdi-clock
      </v-icon>
      <span class="text-caption grey--text font-weight-light">{{ time }}</span>
    </v-card-text>
  </v-card>
</template>

<script>
export default {
  name: 'SystemConditionCard',
  props: {
    title: {
      type: String,
      required: true,
    },
    icon: {
      type: String,
      required: true,
    },
    text: {
      type: String,
      required: true,
    },
    time: {
      type: String,
      required: true,
    },
    value: {
      type: String,
      required: true,
    },
  },
}
</script>

<style>
  .v-sheet--offset {
    top: -24px;
    position: relative;
  }
</style>
