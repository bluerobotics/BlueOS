<template>
  <div ref="bar" class="color-bar">
    <span
      ref="display"
      :style="{ left: computed_left + 'px', 'background-color': computed_color }"
      class="signal-quality"
    >
      {{ quality.toFixed(0) }}
    </span>
  </div>
</template>

<script lang="ts">

export default {
  name: 'CalibrationQualityIndicator',
  props: {
    quality: {
      // Fitness value returned from Compass Calibration by the autopilot, in mGauss.
      // Range could be anything from 0 to over 1000
      type: Number,
      required: true,
    },

  },
  data: () => ({
    bar_width: 0,
    display_width: 0,
  }),
  computed: {
    computed_color() {
      // This mimics the color bars in QGroundControl
      // So while we display a gradient, these limits are the same as used by QGC
      // TODO: refactor to have the ranges as variables and use different ranges
      // for onboard and offboard sensors (as qgc currently does)
      if (this.quality < 8) {
        return '#90EE90'
      }
      if (this.quality < 15) {
        return '#F0E68C'
      }
      return '#FFB6C1'
    },
    fitnessAsPercentage() {
      if (this.quality < 8) {
        return Math.floor(this.quality / 8 * 30)
      } if (this.quality < 15) {
        return Math.floor(30 + (this.quality - 8) / 7 * 40)
      }
      return Math.min(100, Math.floor(70 + (this.quality - 15) / 35 * 30))
    },
    computed_left(): number {
      return this.fitnessAsPercentage * 0.01 * (this.bar_width - this.display_width)
    },
  },
  mounted() {
    this.$nextTick(() => {
      const bar = this.$refs.bar as HTMLElement
      this.bar_width = bar.offsetWidth
      const display = this.$refs.display as HTMLElement
      this.display_width = display.offsetWidth
    })
  },
}
</script>

<style scoped>
.color-bar {
    height: 20px;
    background: linear-gradient(to right,
        green 0%,
        yellow 50%,
        red 100%);
        width:100%;
        margin: auto;
        position: relative;
        border-radius: 5px;
}

.signal-quality {
    margin-top: -4px;
    position: absolute;
    border: black 1px solid;
    padding: 3px;
    border-radius: 6px;
}
</style>
