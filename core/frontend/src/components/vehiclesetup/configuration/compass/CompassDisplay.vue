<template>
  <div ref="compassRoot" class="compass">
    <reboot-required-overlay />
    <canvas
      ref="canvasRef"
      class="rounded-[15%] bg-slate-950/70"
    />
  </div>
</template>

<script lang="ts">
// based on https://github.com/bluerobotics/cockpit/blob/master/src/components/widgets/Compass.vue

import { glMatrix, vec3 } from 'gl-matrix'
import gsap from 'gsap'
import Vue, { PropType } from 'vue'

import RebootRequiredOverlay from '@/components/common/rebootRequiredOverlay.vue'
import autopilot_data from '@/store/autopilot'
import mavlink from '@/store/mavlink'
import { Dictionary } from '@/types/common'
import { deviceId } from '@/utils/deviceid_decoder'
import mavlink_store_get from '@/utils/mavlink'
import mag_heading from '@/utils/mavlink_math'

function sequentialArray(length: number): number[] {
  return Array.from({ length }, (_, i) => i)
}

const mainAngles = {
  0: 'N',
  45: 'NE',
  90: 'E',
  135: 'SE',
  180: 'S',
  225: 'SW',
  270: 'W',
  315: 'NW',
}

export default Vue.extend({
  name: 'CompassDisplay',
  components: {
    RebootRequiredOverlay,
  },
  props: {
    compasses: {
      type: Array as PropType<deviceId[]>,
      required: true,
    },
    colors: {
      type: Object as PropType<Dictionary<string>>,
      default: () => ({} as Dictionary<string>),
    },
  },
  data() {
    return {
      canvasSize: 300,
      renderVariables: {
        yawAngleDegrees: [0, 0, 0, 0, 0, 0],
      },
    }
  },
  computed: {
    canvas(): HTMLCanvasElement {
      return this.$refs.canvasRef as HTMLCanvasElement
    },
    attitude(): vec3 | null {
      const msg = mavlink_store_get(mavlink, 'ATTITUDE.messageData.message') as Dictionary<number>
      if (!msg) return vec3.fromValues(0, 0, 0)
      return vec3.fromValues(msg.roll, msg.pitch, msg.yaw)
    },
    imu1(): vec3 | null {
      const msg = mavlink_store_get(mavlink, 'RAW_IMU.messageData.message') as Dictionary<number>
      if (!msg) return null
      return vec3.fromValues(msg.xmag, msg.ymag, msg.zmag)
    },
    imu2(): vec3 | null {
      const msg = mavlink_store_get(mavlink, 'SCALED_IMU2.messageData.message') as Dictionary<number>
      if (!msg) return null
      return vec3.fromValues(msg.xmag, msg.ymag, msg.zmag)
    },
    imu3(): vec3 | null {
      const msg = mavlink_store_get(mavlink, 'SCALED_IMU3.messageData.message') as Dictionary<number>
      if (!msg) return null
      return vec3.fromValues(msg.xmag, msg.ymag, msg.zmag)
    },
    yaw(): number {
      if (this.attitude === null) {
        return 0
      }
      return glMatrix.toDegree(this.attitude[2])
    },
    mag_headings(): (number | null)[] {
      if (!this.attitude) {
        return []
      }
      const ret = []
      for (const imu of [this.imu1, this.imu2, this.imu3]) {
        if (imu === null) {
          ret.push(null)
          continue
        }
        const heading = mag_heading(imu, this.attitude, this.declinationDegs)
        ret.push(heading)
      }
      return ret
    },
    gps_yaws(): (number | null)[] {
      const yaws = []
      const msg = mavlink_store_get(mavlink, 'GPS_RAW_INT.messageData.message') as Dictionary<number>
      yaws.push(msg?.yaw ? msg.yaw / 100 : null)
      const msg2 = mavlink_store_get(mavlink, 'GPS2_RAW.messageData.message') as Dictionary<number>
      yaws.push(msg2?.yaw ? msg2.yaw / 100 : null)
      return yaws
    },
    headings(): (number | null)[] {
      return [...this.mag_headings, ...this.gps_yaws, this.yaw]
    },
    primaryBaseColor(): string {
      return getComputedStyle(document.documentElement).getPropertyValue('--v-primary-base').trim()
    },
    declinationDegs(): number {
      return glMatrix.toDegree(autopilot_data.parameter('COMPASS_DEC')?.value ?? 0)
    },
  },
  mounted() {
    this.$nextTick(() => {
      if (!this.$refs.canvasRef) return
      this.canvas.width = this.canvasSize
      this.canvas.height = this.canvasSize
    })
    this.initializeCanvas()
    for (const msg of ['ATTITUDE', 'RAW_IMU', 'SCALED_IMU2', 'SCALED_IMU3', 'GPS_RAW_INT', 'GPS2_RAW']) {
      mavlink.setMessageRefreshRate({ messageName: msg, refreshRate: 10 })
    }
  },
  methods: {
    resetCanvas(ctx: CanvasRenderingContext2D) {
      ctx.setTransform(1, 0, 0, 1, 0, 0)
      ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)
      ctx.globalCompositeOperation = 'source-over'
    },
    renderCanvas() {
      const canvasRef = this.$refs.canvasRef as HTMLCanvasElement
      if (canvasRef === undefined) {
        return
      }
      const ctx = canvasRef.getContext('2d')
      if (ctx === null) {
        return
      }
      this.resetCanvas(ctx)

      const halfCanvasSize = 0.5 * this.canvasSize

      // Set canvas general properties
      const fontSize = 0.13 * this.canvasSize
      const baseLineWidth = 0.03 * halfCanvasSize
      ctx.textAlign = 'center'
      ctx.strokeStyle = this.primaryBaseColor
      ctx.font = `bold ${fontSize}px Arial`
      ctx.fillStyle = this.primaryBaseColor
      ctx.lineWidth = baseLineWidth
      ctx.textBaseline = 'middle'

      const outerCircleRadius = 0.7 * halfCanvasSize
      const innerIndicatorRadius = 0.45 * halfCanvasSize
      const outerIndicatorRadius = 0.55 * halfCanvasSize

      // Start drawing from the center
      ctx.translate(halfCanvasSize, halfCanvasSize)

      ctx.save()
      ctx.font = 'bold 16px Arial'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'

      const verticalOffset = 0.2 * this.renderVariables.yawAngleDegrees.length * 10
      // Iterate over the devices and draw the legend
      for (const [index, device] of this.compasses.slice(0, 3).entries()) {
        // check if our device is in the colors dict
        const paramValue = `${device.paramValue}`
        if (paramValue in this.colors) {
          // if it is, set the color to the color in the dict
          ctx.fillStyle = this.colors[paramValue]
        } else {
          // if it is not, set the color to black
          ctx.fillStyle = 'black'
        }
        const text = device.deviceName ?? 'Unknown'
        ctx.fillText(text, 0, +verticalOffset + index * 20 - this.renderVariables.yawAngleDegrees.length * 10)
      }
      // add a new line that says "EKF yaw using the primary color
      ctx.fillStyle = this.primaryBaseColor
      ctx.fillText(
        'EKF',
        0,
        verticalOffset + this.compasses.slice(0, 3).length * 20 - this.renderVariables.yawAngleDegrees.length * 10,
      )
      ctx.fillStyle = this.colors.GPS1
      ctx.fillText(
        'GPS1',
        0,
        verticalOffset + this.compasses.slice(0, 3).length * 20 - this.renderVariables.yawAngleDegrees.length * 10 + 20,
      )
      ctx.fillStyle = this.colors.GPS2
      ctx.fillText(
        'GPS2',
        0,
        verticalOffset + this.compasses.slice(0, 3).length * 20 - this.renderVariables.yawAngleDegrees.length * 10 + 40,
      )
      ctx.restore()

      ctx.rotate(glMatrix.toRadian(-90))

      for (const [angleDegrees, angleName] of Object.entries(mainAngles)) {
        ctx.save()

        ctx.rotate(glMatrix.toRadian(Number(angleDegrees)))
        ctx.beginPath()
        ctx.moveTo(outerIndicatorRadius, 0)
        ctx.lineTo(outerCircleRadius, 0)

        // Draw angle text
        ctx.textBaseline = 'bottom'
        ctx.font = `bold ${0.7 * fontSize}px Arial`
        ctx.translate(outerCircleRadius * 1.025, 0)
        ctx.rotate(glMatrix.toRadian(90))
        ctx.fillText(angleName, 0, 0)

        ctx.stroke()
        ctx.restore()
      }

      // Draw line for each smaller angle, with 9 degree steps
      for (const angleDegrees of sequentialArray(360)) {
        if (angleDegrees % 9 !== 0) continue
        ctx.save()
        ctx.lineWidth = 0.25 * baseLineWidth
        ctx.rotate(glMatrix.toRadian(Number(angleDegrees)))
        ctx.beginPath()
        ctx.moveTo(1.1 * outerIndicatorRadius, 0)
        ctx.lineTo(outerCircleRadius, 0)
        ctx.stroke()
        ctx.restore()
      }

      // Draw outer circle
      ctx.beginPath()
      ctx.arc(0, 0, outerCircleRadius, 0, glMatrix.toRadian(360))
      ctx.stroke()

      // Draw central indicator
      let usedIndex = 0
      for (const [index, angleDegrees] of this.headings.entries()) {
        if (angleDegrees === null) continue
        const paramValue = this.compasses?.[index]?.paramValue

        let color = this.primaryBaseColor
        if (index <= 2 && this.colors[paramValue]) {
          color = this.colors[paramValue]
        } else if (index === 3) {
          color = this.colors.GPS1
        } else if (index === 4) {
          color = this.colors.GPS2
        } else if (index === 5) {
          color = this.primaryBaseColor
        }
        ctx.save()
        this.renderVariables.yawAngleDegrees[index] = angleDegrees
        ctx.rotate(glMatrix.toRadian(angleDegrees))
        ctx.beginPath()
        ctx.lineWidth = 1
        ctx.strokeStyle = color
        ctx.fillStyle = color
        const triangleBaseSize = 0.03 * halfCanvasSize
        const inner_position = 1.3 * innerIndicatorRadius - usedIndex * (outerIndicatorRadius - innerIndicatorRadius)
        const outer_position = 1.3 * outerIndicatorRadius - usedIndex * (outerIndicatorRadius - innerIndicatorRadius)
        ctx.moveTo(inner_position, triangleBaseSize)
        ctx.lineTo(outer_position - triangleBaseSize, 0)
        ctx.lineTo(inner_position, -triangleBaseSize)
        ctx.lineTo(inner_position, triangleBaseSize)
        ctx.closePath()
        ctx.fill()
        ctx.stroke()
        ctx.restore()
        usedIndex += 1
      }
    },
    initializeCanvas() {
      setInterval(() => {
        for (const [index, _value] of this.renderVariables.yawAngleDegrees.entries()) {
          const angle = this.headings[index]
          const angleDegrees = this.headings[index]
          if (!angle || !angleDegrees) {
            continue
          }
          const fullRangeAngleDegrees = angleDegrees < 0 ? angleDegrees + 360 : angleDegrees

          const fromWestToEast = angle > 270 && fullRangeAngleDegrees < 90
          const fromEastToWest = angle < 90 && fullRangeAngleDegrees > 270
          // If cruising 0 degrees, use a chained animation, so the pointer does not turn 360
          // degrees to the other side (visual artifact)
          if (fromWestToEast) {
            gsap.to(this.renderVariables.yawAngleDegrees, 0.05, { [index]: 0 })
            gsap.fromTo(this.renderVariables.yawAngleDegrees, 0.05, { [index]: 0 }, { [index]: fullRangeAngleDegrees })
          } else if (fromEastToWest) {
            gsap.to(this.renderVariables.yawAngleDegrees, 0.05, { [index]: 360 })
            gsap.fromTo(this.renderVariables.yawAngleDegrees, 0.05, { [index]: 360 }, {
              [index]: fullRangeAngleDegrees,
            })
          } else {
            gsap.to(this.renderVariables.yawAngleDegrees, 0.1, { [index]: fullRangeAngleDegrees })
          }
        }
        this.renderCanvas()
      }, 1000 / 10)
    },
  },
})
</script>

<style scoped>
.compass {
  display: block;
  align-items: center;
  justify-content: center;
  width: 100%;
  margin-top: 30px;
  position: relative;
}

.compass canvas {
  border-radius: 15%;
  border: 1px solid var(--v-primary-base);
  background-color: white;
}
</style>
