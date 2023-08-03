<template>
  <div v-if="board_connector">
    <template v-if="inline">
      <object
        :class="inline_name"
        type="image/svg+xml"
        :data="board_image"
        :style="`height: ${height}`"
      />
    </template>
    <v-tooltip
      v-else
      top
    >
      <template #activator="{ on, attrs }">
        <v-icon
          v-if="board_connector !== null"
          v-bind="attrs"
          v-on="on"
        >
          mdi-eye
        </v-icon>
      </template>
      <object
        :class="svgName"
        type="image/svg+xml"
        :data="board_image"
        :style="`height: ${height}`"
      />
    </v-tooltip>
  </div>
</template>

<script lang="ts">
import { v4 as uuid } from 'uuid'
import Vue from 'vue'

import navigator_image from '@/assets/img/devicePathHelper/navigator.svg'
import raspberry_pi3_image from '@/assets/img/devicePathHelper/rpi3b.svg'
import raspberry_pi4_image from '@/assets/img/devicePathHelper/rpi4b.svg'
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
  // Pi4
  '/dev/serial/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.3:1.0-port0': 'top-left',
  '/dev/serial/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.4:1.0-port0': 'bottom-left',
  '/dev/serial/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.1:1.0-port0': 'top-right',
  '/dev/serial/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.2:1.0-port0': 'bottom-right',
  // Pi3
  '/dev/serial/by-path/platform-3f980000.usb-usb-0:1.5:1.0-port0': 'bottom-right',
  '/dev/serial/by-path/platform-3f980000.usb-usb-0:1.4:1.0-port0': 'top-right',
  '/dev/serial/by-path/platform-3f980000.usb-usb-0:1.3:1.0-port0': 'bottom-left',
  '/dev/serial/by-path/platform-3f980000.usb-usb-0:1.2:1.0-port0': 'top-left',
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
      default: '250px',
    },
  },
  data: () => ({
    imgObject: null as Document | null | undefined,
    svgName: `device-path-helper-img-${uuid()}`,
  }),
  computed: {
    inline_name(): string {
      return `${this.svgName}-inline`
    },
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
    board_connector() : string | undefined {
      const connector = connector_map[this.serial_port_path]
      this.setSvgConnector(connector)
      return connector
    },
  },
  mounted() {
    // Wait for svg element to be loaded to set object
    let id = 0
    const name = `.${this.svgName}${this.inline ? '-inline' : ''}`
    id = setInterval(() => {
      const element = document?.querySelector(name) as HTMLEmbedElement | null
      if (element) {
        this.imgObject = element?.getSVGDocument()
        element!.onload = () => {
          this.imgObject = element?.getSVGDocument()
          const connector = this.board_connector
          if (connector !== undefined) {
            this.setSvgConnector(connector)
          }
        }
        this.updateImgObjectFromElement(element)
        clearInterval(id)
      }
    }, 500)
  },
  methods: {
    updateImgObjectFromElement(element: HTMLEmbedElement) {
      this.imgObject = element?.getSVGDocument()
      const connector = this.board_connector
      if (connector !== undefined) {
        this.setSvgConnector(connector)
      }
    },
    setSvgConnector(connector: string) {
      this.imgObject
        ?.getElementById(connector)
        ?.setAttribute('visibility', 'visible')
    },
  },
})
</script>
