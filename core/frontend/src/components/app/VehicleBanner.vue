<template>
  <div class="flex pa-1 pr-3 pl-3">
    <v-row id="vehicle-banner" class="align-center">
      <image-picker
        size="35px"
        directory="/userdata/images/vehicle"
        :readonly-files="['/assets/vehicles/images/bluerov2.png', '/assets/vehicles/images/bb120.png']"
        :default-image="require('@/assets/vehicles/images/unknown.svg')"
        :image="vehicle_image"
        @image-selected="save_vehicle_image"
      />
      <p id="vehicle-name" class="pa-0 pl-5 primary--text font-italic" style="max-width: 120px;">
        {{ vehicle_name }}
        <span
          v-if="system_id !== 1"
          :title="`System ID: ${system_id}`"
          class="subtitle-1 text--secondary"
        >
          ({{ system_id }})
        </span>
      </p>
      <div class="action-buttons-container">
        <v-btn
          class="mx-1"
          fab
          dark
          x-small
          @click="openDialog"
        >
          <v-icon>mdi-pencil</v-icon>
        </v-btn>
        <VehiclePicker />
      </div>
      <v-spacer />
      <image-picker
        size="35px"
        directory="/userdata/images/logo"
        :default-image="require('@/assets/img/blue-robotics-logo.svg')"
        :image="logo_image"
        @image-selected="save_logo"
      />
    </v-row>
    <v-dialog v-if="dialog" v-model="dialog" max-width="500px">
      <v-card>
        <v-card-title>Edit Vehicle Details</v-card-title>
        <v-card-text>
          <v-text-field
            v-model="vehicle_name_input"
            label="Vehicle Name"
          />
          <v-text-field
            v-model="mdns_hostname_input"
            label="mDNS Hostname"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="blue darken-1" text @click="dialog = false">
            Cancel
          </v-btn>
          <v-btn color="blue darken-1" text @click="save()">
            Save
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import ardupilot_data from '@/store/autopilot'
import bag from '@/store/bag'
import beacon from '@/store/beacon'

import ImagePicker from './ImagePicker.vue'
import VehiclePicker from './VehiclePicker.vue'

export default Vue.extend({
  name: 'VehicleBanner',
  components: {
    ImagePicker,
    VehiclePicker,
  },
  data() {
    return {
      vehicle_name_input: '',
      vehicle_image: undefined as string | undefined,
      logo_image: null as string | null,
      mdns_hostname_input: '',
      dialog: false,
    }
  },
  computed: {
    vehicle_name() {
      return beacon.vehicle_name
    },
    mdns_hostname() {
      return beacon.hostname
    },
    system_id() {
      return ardupilot_data.system_id
    },
  },
  watch: {
    vehicle_name() {
      this.update_title()
      this.vehicle_name_input = this.vehicle_name
    },
    mdns_hostname() {
      this.mdns_hostname_input = this.mdns_hostname
    },
    system_id() {
      this.update_title()
    },
  },
  mounted() {
    beacon.registerBeaconListener(this)
    this.load_vehicle_image()
    this.vehicle_name_input = this.vehicle_name
    this.mdns_hostname_input = this.mdns_hostname
    this.load_company_logo()
  },
  methods: {
    async load_vehicle_image() {
      this.vehicle_image = (await bag.getData('vehicle.image_path'))?.url as (string | undefined)
      if (this.vehicle_image && !this.vehicle_image.startsWith('/')) {
        this.vehicle_image = `/${this.vehicle_image}`
      }
    },
    async load_company_logo() {
      this.logo_image = (await bag.getData('vehicle.logo_image_path'))?.url as (string | undefined)
      if (this.logo_image && !this.logo_image.startsWith('/')) {
        this.logo_image = `/${this.vehicle_image}`
      }
    },
    update_title() {
      const sysid = this.system_id !== 1 ? `(${this.system_id}) ` : ''
      document.title = `${sysid}${this.vehicle_name} - BlueOS`
    },
    save() {
      this.save_name()
      this.save_mdns()
      this.dialog = false
    },
    save_logo(image: string) {
      this.logo_image = image
      bag.setData('vehicle.logo_image_path', {
        url: image,
      })
    },
    save_vehicle_image(image: string) {
      this.vehicle_image = image
      bag.setData('vehicle.image_path', {
        url: image,
      })
    },
    save_name() {
      beacon.setVehicleName(this.vehicle_name_input)
    },
    save_mdns() {
      beacon.setHostname(this.mdns_hostname_input)
    },
    openDialog() {
      this.dialog = true
    },
  },
})
</script>
<style scoped>
  #vehicle-banner:hover .action-buttons-container{
    display: inline-flex;
  }

  #vehicle-banner {
    margin-bottom: 0 !important;
    margin-top: 3px;
    margin-right: 0 !important;
    margin-left: 0 !important;
  }

  #vehicle-name {
    margin-bottom: 0 !important;
    position: relative;
  }

  .action-buttons-container {
    display: none;
    position: fixed;
    right: 70px;
    z-index: 10;
    align-items: center;
    gap: 4px;
  }
</style>
