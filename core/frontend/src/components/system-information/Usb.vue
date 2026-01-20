<template>
  <v-container
    fluid
    class="pa-4"
  >
    <v-row v-if="loading">
      <v-col class="d-flex justify-center align-center py-16">
        <v-progress-circular
          indeterminate
          color="primary"
          size="64"
        />
      </v-col>
    </v-row>

    <v-row v-else-if="error">
      <v-col>
        <v-alert type="error">
          {{ error }}
        </v-alert>
      </v-col>
    </v-row>

    <v-row v-else>
      <v-col cols="12">
        <v-text-field
          v-model="search"
          clearable
          label="Search devices"
          prepend-inner-icon="mdi-magnify"
          class="mb-2"
          hide-details
          dense
          outlined
        />
      </v-col>

      <v-col
        v-for="bus in filteredBuses"
        :key="bus.busNumber"
        cols="12"
        md="6"
      >
        <v-card
          class="bus-card"
          outlined
        >
          <v-card-title class="bus-header py-2 px-4">
            <v-icon
              class="mr-2"
              color="primary"
            >
              mdi-expansion-card
            </v-icon>
            <div class="d-flex flex-column">
              <span class="bus-title">USB Bus {{ bus.busNumber }}</span>
              <v-tooltip bottom>
                <template #activator="{ on, attrs }">
                  <span
                    class="text-caption text--secondary d-flex align-center"
                    v-bind="attrs"
                    v-on="on"
                  >
                    <v-icon
                      x-small
                      class="mr-1"
                    >mdi-chip</v-icon>
                    {{ bus.rootHub?.manufacturer || 'Host Controller' }}
                  </span>
                </template>
                <span>USB Host Controller driver</span>
              </v-tooltip>
            </div>
            <v-spacer />
            <v-tooltip bottom>
              <template #activator="{ on, attrs }">
                <v-chip
                  small
                  :color="getSpeedColor(bus.rootHub?.speed)"
                  dark
                  v-bind="attrs"
                  v-on="on"
                >
                  {{ getSpeedLabel(bus.rootHub?.speed) }}
                </v-chip>
              </template>
              <span>{{ bus.rootHub?.speed || 'Unknown speed' }}</span>
            </v-tooltip>
          </v-card-title>

          <v-divider />

          <v-treeview
            :items="bus.treeItems"
            :search="search"
            :filter="filterTree"
            :open="getAllNodeIds(bus.treeItems)"
            item-key="id"
            hoverable
            dense
            class="usb-tree"
          >
            <template #prepend="{ item }">
              <v-tooltip bottom>
                <template #activator="{ on, attrs }">
                  <v-icon
                    :color="getDeviceIconColor(item)"
                    v-bind="attrs"
                    v-on="on"
                  >
                    {{ getDeviceIcon(item) }}
                  </v-icon>
                </template>
                <span>{{ getDeviceTypeTooltip(item.deviceClass) }}</span>
              </v-tooltip>
            </template>

            <template #label="{ item }">
              <div
                class="tree-label d-flex align-center py-1"
                :class="{ 'search-match': isSearchMatch(item) }"
              >
                <div class="flex-grow-1">
                  <div class="d-flex align-center">
                    <span class="device-name">{{ item.name }}</span>
                    <v-tooltip bottom>
                      <template #activator="{ on, attrs }">
                        <v-chip
                          x-small
                          class="ml-2"
                          :color="getSpeedColor(item.speed)"
                          dark
                          v-bind="attrs"
                          v-on="on"
                        >
                          {{ item.usbVersion }}
                        </v-chip>
                      </template>
                      <div>
                        <strong>USB {{ item.usbVersion }}</strong><br>
                        {{ item.speed }}
                      </div>
                    </v-tooltip>
                  </div>
                  <div class="device-meta text-caption text--secondary">
                    <v-tooltip bottom>
                      <template #activator="{ on, attrs }">
                        <span
                          class="mr-3"
                          v-bind="attrs"
                          v-on="on"
                        >
                          <v-icon
                            x-small
                            class="mr-1"
                          >mdi-identifier</v-icon>
                          {{ item.vidPid }}
                        </span>
                      </template>
                      <div>
                        <strong>VID:PID</strong> (Vendor:Product ID)<br>
                        Unique USB device identifier
                      </div>
                    </v-tooltip>
                    <v-tooltip
                      v-if="item.manufacturer"
                      bottom
                    >
                      <template #activator="{ on, attrs }">
                        <span
                          class="mr-3"
                          v-bind="attrs"
                          v-on="on"
                        >
                          <v-icon
                            x-small
                            class="mr-1"
                          >mdi-factory</v-icon>
                          {{ item.manufacturer }}
                        </span>
                      </template>
                      <span>Manufacturer / Driver name</span>
                    </v-tooltip>
                    <v-tooltip
                      v-if="item.serial"
                      bottom
                    >
                      <template #activator="{ on, attrs }">
                        <span
                          class="mr-3"
                          v-bind="attrs"
                          v-on="on"
                        >
                          <v-icon
                            x-small
                            class="mr-1"
                          >mdi-pound</v-icon>
                          {{ item.serial }}
                        </span>
                      </template>
                      <span>Serial Number</span>
                    </v-tooltip>
                    <v-tooltip bottom>
                      <template #activator="{ on, attrs }">
                        <span
                          v-bind="attrs"
                          v-on="on"
                        >
                          <v-icon
                            x-small
                            class="mr-1"
                          >mdi-source-branch</v-icon>
                          {{ item.portPath }}
                        </span>
                      </template>
                      <div>
                        <strong>Port Path:</strong> {{ item.portPath }}<br>
                        <strong>Address:</strong> {{ item.address }}
                      </div>
                    </v-tooltip>
                  </div>
                </div>
              </div>
            </template>
          </v-treeview>

          <v-card-actions class="px-4 py-2 text--secondary">
            <v-icon
              small
              class="mr-1"
            >
              mdi-devices
            </v-icon>
            <span class="text-caption">{{ countDevices(bus.treeItems) }} device(s)</span>
          </v-card-actions>
        </v-card>
      </v-col>

      <v-col
        v-if="filteredBuses.length === 0"
        cols="12"
      >
        <v-alert
          type="info"
          text
        >
          No USB devices found{{ search ? ' matching your search' : '' }}
        </v-alert>
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import { UsbDevice } from '@/types/system-information/usb'
import back_axios, { isBackendOffline } from '@/utils/api'

interface TreeItem {
  id: string
  name: string
  children: TreeItem[]
  deviceClass: number
  deviceSubclass: number
  deviceProtocol: number
  manufacturer: string | null
  serial: string | null
  vidPid: string
  usbVersion: string
  speed: string
  portPath: string
  address: number
}

interface UsbBus {
  busNumber: number
  rootHub: UsbDevice | null
  treeItems: TreeItem[]
}

export default Vue.extend({
  name: 'Usb',
  data() {
    return {
      devices: [] as UsbDevice[],
      loading: true,
      error: null as string | null,
      timer: 0,
      search: '',
    }
  },
  computed: {
    buses(): UsbBus[] {
      const busMap = new Map<number, UsbDevice[]>()

      for (const device of this.devices) {
        if (!busMap.has(device.bus_number)) {
          busMap.set(device.bus_number, [])
        }
        busMap.get(device.bus_number)!.push(device)
      }

      const buses: UsbBus[] = []
      for (const [busNumber, devices] of busMap) {
        const rootHub = devices.find((d) => d.port_path.endsWith('-0')) || null
        const treeItems = this.buildTreeItems(devices)
        buses.push({ busNumber, rootHub, treeItems })
      }

      return buses.sort((a, b) => a.busNumber - b.busNumber)
    },
    filteredBuses(): UsbBus[] {
      if (!this.search) return this.buses
      return this.buses.filter((bus) => this.hasMatchingDevice(bus.treeItems))
    },
  },
  mounted() {
    this.fetchUsb()
    this.timer = window.setInterval(() => this.fetchUsb(), 5000)
  },
  beforeDestroy() {
    clearInterval(this.timer)
  },
  methods: {
    async fetchUsb(): Promise<void> {
      try {
        const response = await back_axios({
          method: 'get',
          url: '/system-information/usb',
          timeout: 10000,
        })
        this.devices = response.data.devices
        this.loading = false
        this.error = null
      } catch (err: unknown) {
        if (isBackendOffline(err)) return
        this.error = `Failed to fetch USB devices: ${err instanceof Error ? err.message : 'Unknown error'}`
        this.loading = false
      }
    },
    deviceToTreeItem(device: UsbDevice): TreeItem {
      return {
        id: device.port_path,
        name: device.product || device.manufacturer || `Device ${device.vid.toString(16)}:${device.pid.toString(16)}`,
        children: [],
        deviceClass: device.device_class,
        deviceSubclass: device.device_subclass,
        deviceProtocol: device.device_protocol,
        manufacturer: device.manufacturer,
        serial: device.serial_number,
        vidPid: `${device.vid.toString(16).padStart(4, '0')}:${device.pid.toString(16).padStart(4, '0')}`,
        usbVersion: device.usb_version,
        speed: device.speed,
        portPath: device.port_path,
        address: device.device_address,
      }
    },
    buildTreeItems(devices: UsbDevice[]): TreeItem[] {
      const rootDevice = devices.find((d) => d.port_path.endsWith('-0'))
      if (!rootDevice) return []

      const nodeMap = new Map<string, TreeItem>()

      for (const device of devices) {
        nodeMap.set(device.port_path, this.deviceToTreeItem(device))
      }

      for (const device of devices) {
        if (device.port_path.endsWith('-0')) continue

        const parentPath = this.getParentPath(device.port_path)
        const parentNode = nodeMap.get(parentPath)
        const currentNode = nodeMap.get(device.port_path)

        if (parentNode && currentNode) {
          parentNode.children.push(currentNode)
        }
      }

      for (const node of nodeMap.values()) {
        node.children.sort((a, b) => a.portPath.localeCompare(b.portPath))
      }

      const rootNode = nodeMap.get(rootDevice.port_path)
      return rootNode ? [rootNode] : []
    },
    getParentPath(portPath: string): string {
      const parts = portPath.split('.')
      if (parts.length === 1) {
        const busMatch = portPath.match(/^(\d+)-\d+$/)
        if (busMatch) {
          return `${busMatch[1]}-0`
        }
        return portPath
      }
      parts.pop()
      return parts.join('.')
    },
    countDevices(items: TreeItem[]): number {
      let count = 0
      for (const item of items) {
        count += 1 + this.countDevices(item.children)
      }
      return count
    },
    hasMatchingDevice(items: TreeItem[]): boolean {
      const searchLower = this.search.toLowerCase()
      for (const item of items) {
        if (
          item.name.toLowerCase().includes(searchLower)
          || item.manufacturer?.toLowerCase().includes(searchLower)
          || item.serial?.toLowerCase().includes(searchLower)
          || item.vidPid.toLowerCase().includes(searchLower)
          || item.portPath.toLowerCase().includes(searchLower)
        ) {
          return true
        }
        if (this.hasMatchingDevice(item.children)) return true
      }
      return false
    },
    isSearchMatch(item: TreeItem): boolean {
      if (!this.search) return false
      const searchLower = this.search.toLowerCase()
      return (
        item.name.toLowerCase().includes(searchLower)
        || item.manufacturer?.toLowerCase().includes(searchLower)
        || item.serial?.toLowerCase().includes(searchLower)
        || item.vidPid.toLowerCase().includes(searchLower)
      )
    },
    filterTree(item: TreeItem, search: string): boolean {
      const searchLower = search.toLowerCase()
      return (
        item.name.toLowerCase().includes(searchLower)
        || item.manufacturer?.toLowerCase().includes(searchLower)
        || item.serial?.toLowerCase().includes(searchLower)
        || item.vidPid.toLowerCase().includes(searchLower)
        || item.portPath.toLowerCase().includes(searchLower)
      )
    },
    getDeviceIcon(item: TreeItem): string {
      const {
        deviceClass, deviceSubclass, deviceProtocol, name,
      } = item

      // Known device classes, check getDeviceTypeTooltip for more information
      switch (deviceClass) {
        case 0x01: return 'mdi-volume-high'
        case 0x02: return 'mdi-serial-port'
        case 0x03: return 'mdi-keyboard'
        case 0x05: return 'mdi-ruler'
        case 0x06: return 'mdi-image'
        case 0x07: return 'mdi-printer'
        case 0x08: return 'mdi-harddisk'
        case 0x09: return 'mdi-hub'
        case 0x0a: return 'mdi-source-branch'
        case 0x0b: return 'mdi-credit-card-chip'
        case 0x0d: return 'mdi-shield-key'
        case 0x0e: return 'mdi-video'
        case 0x0f: return 'mdi-heart-pulse'
        case 0x10: return 'mdi-movie'
        case 0x11: return 'mdi-billboard'
        case 0x12: return 'mdi-usb-c-port'
        case 0x13: return 'mdi-monitor-eye'
        case 0x14: return 'mdi-ethernet'
        case 0x3c: return 'mdi-vector-link'
        case 0xdc: return 'mdi-stethoscope'
        case 0xe0: return 'mdi-bluetooth'
        case 0xfe: return 'mdi-apps-box'
        case 0xff: return 'mdi-cogs'
        default: break
      }

      // For class 0 (interface-defined) and 0xef (miscellaneous), use subclass/protocol and name heuristics
      if (deviceClass === 0x00 || deviceClass === 0xef) {
        // Check subclass/protocol combinations
        // deviceSubclass 0x01: CDC subclass, deviceProtocol 0x01: AT commands (CDC ACM, serial)
        if (deviceSubclass === 0x01 && deviceProtocol === 0x01) return 'mdi-sync'
        // deviceSubclass 0x02: Networking Control Model, deviceProtocol 0x01: Ethernet Control Model
        if (deviceSubclass === 0x02 && deviceProtocol === 0x01) return 'mdi-video'
        // deviceSubclass 0x02: Networking Control Model, deviceProtocol 0x02: Ethernet Emulation
        if (deviceSubclass === 0x02 && deviceProtocol === 0x02) return 'mdi-lan-connect'

        // Use product name heuristics for common device types
        const nameLower = name.toLowerCase()
        const namePatterns: Array<{ keywords: string[], icon: string }> = [
          {
            keywords: ['webcam', 'camera'],
            icon: 'mdi-webcam',
          },
          {
            keywords: ['keyboard'],
            icon: 'mdi-keyboard',
          },
          {
            keywords: ['mouse'],
            icon: 'mdi-mouse',
          },
          {
            keywords: ['audio', 'speaker', 'headphone', 'earphone', 'microphone'],
            icon: 'mdi-volume-high',
          },
          {
            keywords: ['bluetooth'],
            icon: 'mdi-bluetooth',
          },
          {
            keywords: ['wifi', 'wireless', 'wlan', '802.11', 'nic'],
            icon: 'mdi-wifi',
          },
          { keywords: ['ethernet', 'lan'], icon: 'mdi-ethernet' },
          {
            keywords: ['serial', 'uart', 'ftdi', 'ch340', 'cp210'],
            icon: 'mdi-serial-port',
          },
          {
            keywords: ['storage', 'disk', 'flash'],
            icon: 'mdi-harddisk',
          },
          { keywords: ['printer'], icon: 'mdi-printer' },
          {
            keywords: ['gamepad', 'joystick', 'controller'],
            icon: 'mdi-gamepad-variant',
          },
          {
            keywords: ['gps', 'gnss'],
            icon: 'mdi-crosshairs-gps',
          },
        ]

        for (const pattern of namePatterns) {
          if (pattern.keywords.some((keyword) => nameLower.includes(keyword))) {
            return pattern.icon
          }
        }

        // The USB Miscellaneous device class (covers devices that do not fit in other classes)
        return deviceClass === 0xef ? 'mdi-swap-horizontal' : 'mdi-chip'
      }

      return 'mdi-usb'
    },
    getDeviceIconColor(item: TreeItem): string {
      if (item.deviceClass === 9) return 'primary'
      return 'grey darken-1'
    },
    getDeviceTypeTooltip(deviceClass: number): string {
      // From: https://www.usb.org/defined-class-codes
      const classNames: Record<number, string> = {
        0x00: 'Device (Use class information in the Interface Descriptors)',
        0x01: 'Audio',
        0x02: 'Communications and CDC Control',
        0x03: 'Human Interface Device',
        0x05: 'Physical',
        0x06: 'Image',
        0x07: 'Printer',
        0x08: 'Mass Storage',
        0x09: 'USB Hub',
        0x0a: 'CDC-Data',
        0x0b: 'Smart Card',
        0x0d: 'Content Security',
        0x0e: 'Video',
        0x0f: 'Personal Healthcare',
        0x10: 'Audio/Video Devices',
        0x11: 'Billboard Device Class',
        0x12: 'USB Type-C Bridge Class',
        0x13: 'USB Bulk Display Protocol Device Class',
        0x14: 'MCTP over USB Protocol Endpoint Device Class',
        0x3c: 'I3C Device Class',
        0xdc: 'Diagnostic Device',
        0xe0: 'Wireless Controller',
        0xef: 'Miscellaneous',
        0xfe: 'Application Specific',
        0xff: 'Vendor Specific',
      }
      return classNames[deviceClass] || `Device Class ${deviceClass}`
    },
    getSpeedColor(speed: string | undefined): string {
      if (speed?.includes('SuperPlus')) return 'secondary'
      if (speed?.includes('Super')) return 'info'
      if (speed?.includes('High')) return 'success'
      if (speed?.includes('Full')) return 'warning'
      if (speed?.includes('Low')) return 'error'
      return 'grey'
    },
    getSpeedLabel(speed: string | undefined): string {
      if (speed?.includes('SuperPlus')) return '10 Gbps'
      if (speed?.includes('Super')) return '5 Gbps'
      if (speed?.includes('High')) return '480 Mbps'
      if (speed?.includes('Full')) return '12 Mbps'
      if (speed?.includes('Low')) return '1.5 Mbps'
      return 'Unknown'
    },
    getAllNodeIds(items: TreeItem[]): string[] {
      const ids: string[] = []
      for (const item of items) {
        ids.push(item.id)
        if (item.children.length > 0) {
          ids.push(...this.getAllNodeIds(item.children))
        }
      }
      return ids
    },
  },
})
</script>

<style scoped>
.bus-card {
  border-radius: 8px;
  overflow: hidden;
}

.bus-header {
  background: transparent;
}

.bus-title {
  font-weight: 600;
  font-size: 1rem;
}

.usb-tree {
  padding: 8px 0;
}

.usb-tree >>> .v-treeview-node__root {
  min-height: 48px;
}

.usb-tree >>> .v-treeview-node__content {
  margin-left: 4px;
}

.tree-label {
  width: 100%;
}

.tree-label.search-match {
  background: var(--v-warning-lighten4);
  border-radius: 4px;
  padding-left: 8px;
  padding-right: 8px;
  margin-left: -8px;
}

.device-name {
  font-weight: 500;
  font-size: 0.9rem;
}

.device-meta {
  margin-top: 2px;
  font-size: 0.75rem;
  opacity: 0.85;
}
</style>
