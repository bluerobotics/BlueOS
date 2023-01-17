<template>
  <div v-if="board_connector">
    <template v-if="inline">
      <div :style="`height: ${height}; width:${height}; display: block; position: relative`">
        <img
          :src="board_image"
          :style="`height: ${height};`"
        >
        <div :class="circle_class" />
      </div>
    </template>
    <v-tooltip v-else>
      <template #activator="{ on, attrs }">
        <v-icon
          v-if="board_connector !== null"
          v-bind="attrs"
          v-on="on"
        >
          mdi-eye
        </v-icon>
      </template>
      <div :style="`height: ${height}; width:${height}; display: block; position: relative`">
        <img
          :src="board_image"
          :style="`height: ${height}`"
        >
        <div :class="circle_class" />
      </div>
    </v-tooltip>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import navigator_image from '@/assets/img/devicePathHelper/navigator.jpg'
import raspberry_pi3_image from '@/assets/img/devicePathHelper/rpi3b.jpg'
import raspberry_pi4_image from '@/assets/img/devicePathHelper/rpi4b.png'
import system_information from '@/store/system-information'
import { Dictionary } from '@/types/common'

enum BoardType {
  Rpi4B = 'Rpi4B',
  Rpi3B = 'Rpi3B',
  Navigator = 'Navigator',
  Unknown = 'Unknown'
}

const connector_map: Dictionary<string> = {
  '/dev/ttyS0': 'serial1',
  '/dev/ttyAMA1': 'serial3',
  '/dev/ttyAMA2': 'serial4',
  '/dev/ttyAMA3': 'serial5',
  '/dev/serial/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.3:1.0-port0': 'usb-top-left-pi4',
  '/dev/serial/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.4:1.0-port0': 'usb-bottom-left-pi4',
  '/dev/serial/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.1:1.0-port0': 'usb-top-right-pi4',
  '/dev/serial/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.2:1.0-port0': 'usb-bottom-right-pi4',
  '/dev/serial/by-path/platform-3f980000.usb-usb-0:1.5:1.0-port0': 'usb-bottom-right-pi3',
  '/dev/serial/by-path/platform-3f980000.usb-usb-0:1.4:1.0-port0': 'usb-top-right-pi3',
  '/dev/serial/by-path/platform-3f980000.usb-usb-0:1.3:1.0-port0': 'usb-bottom-left-pi3',
  '/dev/serial/by-path/platform-3f980000.usb-usb-0:1.2:1.0-port0': 'usb-top-left-pi3',
}

export default Vue.extend({
  name: 'DevicePathHelper',
  props: {
    device: {
      type: String,
      required: true,
    },
    inline: {
      type: Boolean,
      required: false,
      default: false,
    },
    height: {
      type: String,
      required: false,
      default: '500px',
    },
  },
  computed: {
    serial_port_path(): string {
      /* returns the by-path path for the serial port if available */
      return system_information.serial?.ports?.find((a) => a.name === this.device)?.by_path ?? this.device as string
    },
    board_type() : BoardType {
      /* Detects board type between navigator and Rpi4 */
      switch (true) {
        case this.serial_port_path.includes('ttyAMA'):
        case this.serial_port_path.includes('ttyS0'):
          return BoardType.Navigator
        case this.serial_port_path.includes('platform-3f980000'):
          return BoardType.Rpi3B
        case this.serial_port_path.includes('platform-fd500000'):
          return BoardType.Rpi4B
        default:
          return BoardType.Unknown
      }
    },
    board_image() : string {
      switch (this.board_type) {
        case BoardType.Navigator:
          return navigator_image
        case BoardType.Rpi4B:
          return raspberry_pi4_image
        case BoardType.Rpi3B:
          return raspberry_pi3_image
        default:
          return ''
      }
    },
    board_connector() : string | null {
      const serial_port_path = this.serial_port_path as string
      try {
        return connector_map[serial_port_path]
      } catch (error) {
        console.error(error)
      }
      return null
    },
    circle_class() : string {
      return this.board_connector ? `circle ${this.board_connector}` : ''
    },
  },
})
</script>

<style scoped>

.circle {
  position: absolute;
  width: 32%; height: 16%;
  border-radius: 20px;
  border: 5px solid red;
}

.serial4 {
    left: 45%;
    top: 52%;
}

.serial5 {
    left: 13%;
    top: 52%;
}

.serial1 {
    left: 45%;
    top: 23%;
}

.serial3 {
    left: 45%;
    top: 38%;
}

.usb-bottom-left-pi4 {
    left: 11%;
    top: 44%;
    width: 57%; height: 23%;
}

.usb-bottom-right-pi4 {
    left: 61%;
    top: 44%;
    width: 57%; height: 23%;
}

.usb-top-right-pi4 {
    left: 61%;
    top: 20%;
    width: 57%; height: 23%;
}

.usb-top-left-pi4 {
    left: 11%;
    top: 20%;
    width: 57%; height: 23%;
}

.usb-top-right-pi3 {
    left: 67%;
    top: 0%;
    width: 150px; height: 70px;
}

.usb-top-left-pi3 {
    left: 37%;
    top: 0%;
    width: 150px; height: 70px;
}

.usb-bottom-left-pi3 {
    left: 37%;
    top: 43%;
    width: 150px; height: 70px;
}

.usb-bottom-right-pi3 {
    left: 67%;
    top: 43%;
    width: 150px; height: 70px;
}

</style>
