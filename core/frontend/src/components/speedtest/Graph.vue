<template>
  <apexchart
    ref="chart"
    type="line"
    :options="options"
    :series="series"
  />
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

type Point = { x: number, y: number }
export type Data = { upload: Point[], download: Point[] }

export default Vue.extend({
  name: 'SpeedChart',
  props: {
    data: {
      type: Object as PropType<Data>,
      required: true,
    },
  },
  data() {
    return {
      options: {
        chart: {
          animations: {
            enabled: false,
          },
          toolbar: {
            show: false,
          },
        },
        animate: false,
        xaxis: {
          type: 'numeric',
          tickPlacement: 'on',
          min: 0,
          max: 100,
          overwriteCategories: [0, 20, 40, 60, 80, 100],
        },
        yaxis: {
          title: {
            text: 'Speed Mb/s',
          },
          decimalsInFloat: 1,
        },
      },
      series: [
        {
          name: 'Download',
          data: [],
        },
        {
          name: 'Upload',
          data: [],
        },
      ],
    }
  },
  computed: {},
  watch: {
    data(series: Data): void {
      this.updateSeries(series)
    },
  },
  methods: {
    updateSeries(series: Data) {
      const chart = this.$refs.chart as any
      chart.series[0].data = series.download
      chart.series[1].data = series.upload
      chart.updateSeries([
        {
          data: series.download,
        },
        {
          data: series.upload,
        },
      ])
      chart.refresh()
    },
  },
})
</script>
