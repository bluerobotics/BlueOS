<template>
  <v-card
    max-width="400"
    min-width="300"
  >
    <v-sheet
      class="v-sheet--offset mx-auto"
      color="primary"
      elevation="12"
      max-width="calc(100% - 10px)"
    >
      <div
        class="transition-swing text-h4 pa-3 white--text"
        align="center"
        v-text="value"
      />
    </v-sheet>

    <v-card-text class="pt-0">
      <div class="text-h6 font-weight-light mb-2">
        {{ title }}
      </div>
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
