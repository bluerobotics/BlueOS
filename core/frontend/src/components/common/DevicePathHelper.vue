<template>
  <v-tooltip>
    <template #activator="{ on, attrs }">
      <v-icon
        class="ml-4"
        v-bind="attrs"
        v-on="on"
      >
        mdi-information
      </v-icon>
    </template>
    <img :src="board_image">
    <div :class="circle_class" />
  </v-tooltip>
</template>

<script lang="ts">
import Vue from 'vue'

import system_information from '@/store/system-information'
import { SerialPortInfo } from '@/types/system-information/serial'

export default Vue.extend({
  name: 'DevicePathHelper',
  props: {
    device: {
      type: String,
      required: true,
    },
  },
  computed: {
    serial_port_path(): string {
      const system_serial_ports: SerialPortInfo[] | undefined = system_information.serial?.ports
      if (system_serial_ports === undefined || system_serial_ports.isEmpty()) {
        return this.device as string
      }
      const port = system_serial_ports.find((a) => a.name === this.device)
      return port && port.by_path ? port.by_path : this.device as string
    },
    board_type() : string {
      const serial_port_path = this.serial_port_path as string // why is it needed?
      if (serial_port_path.indexOf('ttyAMA') > -1 || serial_port_path.indexOf('ttyS0') > -1) {
        return 'navigator'
      }
      return 'rpi4b'
    },
    board_image() : string {
      if (this.board_type === 'navigator') {
        /* eslint-disable */
        return require('../../assets/img/devicePathHelper/navigator.png')
      }
      /* eslint-disable */
      return require('../../assets/img/devicePathHelper/rpi4b.png')
    },
    board_connector () : string {
        const serial_port_path = this.serial_port_path as string // why is it needed?
        if (this.board_type ===  'navigator') {
            // from ArdupilotManager
            if (serial_port_path.endsWith('ttyS0')) {
                return 'serial1'
            }
            if (serial_port_path.endsWith('ttyAMA1')) {
                return 'serial3'
            }
            if (serial_port_path.endsWith('ttyAMA2')) {
                return 'serial4'
            }
            if (serial_port_path.endsWith('ttyAMA3')) {
                return 'serial5'
            }
        }
        if (serial_port_path.endsWith('pcie-pci-0000:01:00.0-usb-0:1.3:1.0-port0')) {
          return 'usbtl'
        }
        if (serial_port_path.endsWith('pcie-pci-0000:01:00.0-usb-0:1.4:1.0-port0')) {
          return 'usbbl'
        }
        if (serial_port_path.endsWith('pcie-pci-0000:01:00.0-usb-0:1.1:1.0-port0')) {
          return 'usbtr'
        }
        if (serial_port_path.endsWith('pcie-pci-0000:01:00.0-usb-0:1.2:1.0-port0')) {
          return 'usbbr'
        }
        return ''
    },
    circle_class () : string {
        return "circle " + this.board_connector
    }
  },
})
</script>

<style scoped>

.circle {
  position: absolute;
  top:0%;
  width: 160px; height: 80px;
  border-radius: 40px;
  border: 5px solid red;
  left: 160px;
}

.serial4 {
    left: 50%;
    top: 52%;
}

.serial1 {
    left: 50%;
    top: 23%;
}

.serial3 {
    left: 50%;
    top: 38%;
}

.usbbl {
    left: 11%;
    top: 44%;
    width: 190px; height: 105px;
}

.usbbr {
    left: 37%;
    top: 44%;
    width: 190px; height: 105px;
}

.usbtr {
    left: 37%;
    top: 20%;
    width: 190px; height: 105px;
}

.usbtl {
    left: 11%;
    top: 20%;
    width: 190px; height: 105px;
}

</style>